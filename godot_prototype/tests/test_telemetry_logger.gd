# tests/test_telemetry_logger.gd
# TelemetryLogger: session deduplication ON DISK, per-floor Judge rows (all 8 difficulty params +
# 5-archetype mix captured from the DifficultyManager, missing values stay null instead of being
# invented), and the CR0 calibration baseline.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_telemetry_logger.gd
extends SceneTree

const JSON_PATH := "user://test_tl_logger.json"

var failures: Array[String] = []

func _check(cond: bool, msg: String) -> void:
	if not cond:
		failures.append(msg)

func _cleanup() -> void:
	for p in [JSON_PATH, "user://test_tl_logger_install.txt"]:
		var abs_path: String = ProjectSettings.globalize_path(p)
		if FileAccess.file_exists(abs_path):
			DirAccess.remove_absolute(abs_path)

func _new_logger() -> TelemetryLogger:
	var tl := TelemetryLogger.new()
	tl.backend_preference = "json"  # deterministic in CI with or without godot-sqlite
	tl.json_path = JSON_PATH
	tl.install_id_path = "user://test_tl_logger_install.txt"
	return tl

func _init() -> void:
	_cleanup()
	var tl := _new_logger()

	# 1. Repeated save_to_file() calls must update ONE session entry on disk, not append snapshots.
	tl.record_room_cleared()
	tl.record_damage_dealt(100.0)
	tl.save_to_file()
	tl.record_room_cleared()
	tl.record_damage_taken(25.0)
	tl.save_to_file()
	tl.close()
	var f := FileAccess.open(JSON_PATH, FileAccess.READ)
	var data = JSON.parse_string(f.get_as_text()) if f else null
	if f:
		f.close()
	_check(data is Array, "telemetry JSON is not an array")
	if data is Array:
		var matches: Array = data.filter(func(s): return s is Dictionary and s.get("session_id", "") == tl.session_id)
		_check(matches.size() == 1, "expected 1 stored entry for the session, got %d" % matches.size())
		if matches.size() == 1:
			_check(int(matches[0].get("rooms_cleared", -1)) == 2, "stored rooms_cleared != 2")
			_check(absf(float(matches[0].get("damage_taken", -1)) - 25.0) < 1e-4, "stored damage_taken != 25")

	# 2. Per-floor row for the Judge model: every parameter comes from the DifficultyManager.
	var dm := DifficultyManager.new()
	dm.apply_ppo_action(PackedFloat32Array([0.2, -0.3, 0.1, 0.4, -0.2, 0.0, 0.5, 0.6]))
	tl = _new_logger()
	tl.begin_floor(7, 6)
	tl.record_room_visited(Vector2i(0, 0))
	tl.record_room_visited(Vector2i(1, 0))
	tl.record_enemy_defeated_by_archetype(2)
	tl.record_enemy_defeated_by_archetype(2)
	tl.record_enemy_defeated_by_archetype(4)
	_check(tl.record_floor(dm, {"floor_num": 7, "completion_time": 45.2, "deaths": 1,
		"damage_taken": 30.0, "player_max_hp": 100.0}), "record_floor returned false")
	var hist: Array = tl.get_floor_history()
	_check(hist.size() == 1, "expected 1 floor in history, got %d" % hist.size())
	if hist.size() == 1:
		var row: Dictionary = hist[0]
		for k in ["enemy_health", "enemy_damage", "enemy_speed", "enemy_aggro", "hazard_density", "resource_scarcity"]:
			_check(absf(float(row.get(k, -999.0)) - float(dm.get(k))) < 1e-3, "floor %s != DifficultyManager value" % k)
		_check(int(row.get("room_count", -1)) == dm.room_count_target, "room_count mismatch")
		_check(absf(float(row.get("archetype_complexity", -1.0)) - dm.archetype_complexity) < 1e-4, "archetype_complexity mismatch")
		for i in 5:
			_check(absf(float(row.get("archetype_mix_%d" % i, -1.0)) - dm.archetype_mix[i]) < 1e-4, "archetype_mix_%d mismatch" % i)
		_check(row.get("phase", "") == "adaptive", "phase should be adaptive, got %s" % row.get("phase", ""))
		_check(int(row.get("rooms_visited", -1)) == 2 and int(row.get("rooms_total", -1)) == 6, "room visit counts wrong")
		var kills: Dictionary = row.get("kills", {})
		_check(int(kills.get(2, 0)) == 2 and int(kills.get(4, 0)) == 1, "kills_by_archetype wrong: %s" % str(kills))
		# No policy step was noted for this floor -> action columns must be null, not invented.
		_check(row.get("action_0") == null, "action_0 should be null when no policy step was recorded")
	tl.close()

	# 3. CR0 calibration baseline stays in range.
	var tl3 := _new_logger()
	tl3.record_calibration_floor(1, 35.0, 0, 20.0, 5, 20)
	tl3.record_calibration_floor(2, 40.0, 0, 30.0, 5, 30)
	tl3.record_calibration_floor(3, 45.0, 1, 50.0, 6, 45)
	tl3.record_calibration_floor(4, 50.0, 1, 60.0, 6, 60)
	tl3.record_calibration_floor(5, 60.0, 2, 90.0, 7, 80)
	var cr0: Dictionary = tl3.compute_cr0_baseline(100.0)
	_check(cr0.cr0_score > 0.0 and cr0.cr0_score <= 100.0, "cr0_score out of range: %s" % cr0.cr0_score)

	_cleanup()
	if failures.is_empty():
		print("[FORGE TEST] TelemetryLogger unit tests: PASS")
		quit(0)
	else:
		for msg in failures:
			printerr("[FORGE TEST] FAIL: " + msg)
		print("[FORGE TEST] TelemetryLogger unit tests: FAIL")
		quit(1)
