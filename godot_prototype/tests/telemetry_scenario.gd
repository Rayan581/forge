# tests/telemetry_scenario.gd
# Shared scenario for test_telemetry_sqlite.gd / test_telemetry_fallback.gd: records 3 floors with
# known values, closes, reopens, reads everything back and checks it, including the CSV export.
extends RefCounted

const EPS := 1e-4
const TelemetryLoggerScript = preload("res://scripts/TelemetryLogger.gd")

var failures: Array[String] = []
var checks := 0

const STUB_SRC := """extends RefCounted
var enemy_health: float = 72.5
var enemy_damage: float = 21.25
var enemy_speed: float = 133.0
var enemy_aggro: float = 260.0
var hazard_density: float = 0.4
var resource_scarcity: float = 0.35
var room_count_target: int = 7
var enemy_count_scale: float = 1.25
var archetype_complexity: float = 0.75
var archetype_mix: PackedFloat32Array = PackedFloat32Array([0.1, 0.2, 0.3, 0.25, 0.15])
func calculate_difficulty_score() -> Dictionary:
	return {"score": 64.0, "label": "Hard"}
"""

func _near(label: String, got: Variant, want: Variant) -> void:
	checks += 1
	if want == null:
		if got != null:
			failures.append("%s: got %s, expected NULL" % [label, str(got)])
	elif got == null or absf(float(got) - float(want)) > EPS:
		failures.append("%s: got %s, expected %s" % [label, str(got), str(want)])

func _eq(label: String, got: Variant, want: Variant) -> void:
	checks += 1
	if str(got) != str(want):
		failures.append("%s: got %s, expected %s" % [label, str(got), str(want)])

func _new_logger(backend: String, tag: String) -> RefCounted:
	var tl = TelemetryLoggerScript.new()
	tl.backend_preference = backend
	tl.db_path = "user://test_tel_%s.db" % tag
	tl.json_path = "user://test_tel_%s.json" % tag
	tl.install_id_path = "user://test_tel_%s_install.txt" % tag
	tl.consent_given = true
	tl.game_version = "test-1.0"
	return tl

func cleanup(tag: String) -> void:
	for name in ["test_tel_%s.db", "test_tel_%s.db-journal", "test_tel_%s.json", "test_tel_%s_install.txt", "test_tel_%s.csv", "test_tel_%s_consented.csv"]:
		var p: String = ProjectSettings.globalize_path("user://" + (name % tag))
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

## `legacy_json`: optional legacy flat-JSON history to seed (SQLite import check). It is written
## AFTER the initial cleanup, so it survives until the first backend open imports it.
func run(backend: String, tag: String, expect_backend: String, legacy_json: String = "") -> void:
	cleanup(tag)
	if not legacy_json.is_empty():
		var lf := FileAccess.open("user://test_tel_%s.json" % tag, FileAccess.WRITE)
		lf.store_string(legacy_json)
		lf.close()
	var tl = _new_logger(backend, tag)
	_eq("backend name", tl.get_backend_name(), expect_backend)
	var sid: String = tl.session_id

	var stub = GDScript.new()
	stub.source_code = STUB_SRC
	stub.reload()

	# Floor 1: stub DifficultyManager with all 8 params + mix, with a policy obs/action pair.
	var obs := PackedFloat32Array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
	var act := PackedFloat32Array([-1.0, -0.5, 0.0, 0.25, 0.5, 0.75, 1.0, -0.25])
	tl.begin_floor(1, 5)
	for room in [Vector2i(0, 0), Vector2i(1, 0), Vector2i(1, 0), Vector2i(2, 0)]:
		tl.record_room_visited(room)
	tl.record_damage_taken(30.0)
	tl.record_damage_dealt(88.5)
	tl.record_death()
	tl.record_room_cleared()
	tl.record_hazard_hit()
	tl.record_pickup_collected()
	for i in range(5):
		tl.record_enemy_defeated()
	tl.record_enemy_defeated_by_archetype(0)
	tl.record_enemy_defeated_by_archetype(0)
	tl.record_enemy_defeated_by_archetype(4)
	tl.record_enemy_defeated_by_archetype(4)
	tl.record_enemy_defeated_by_archetype(4)
	for i in range(100):
		tl.record_frame(0.010)
	tl.record_frame(0.050)
	tl.note_policy_step(obs, act)
	_eq("floor 1 persisted", tl.record_floor(stub.new(), {"floor_num": 1, "completion_time": 42.5, "player_max_hp": 100.0, "phase": "calibration"}), true)

	# Floor 2: different values, no policy step, no kills, no frames.
	tl.begin_floor(2, 4)
	tl.record_room_visited(Vector2i(0, 0))
	tl.record_damage_taken(5.5)
	_eq("floor 2 persisted", tl.record_floor(stub.new(), {"floor_num": 2, "completion_time": 17.25, "player_max_hp": 120.0, "phase": "adaptive", "perceived_difficulty": 3.5}), true)

	# Floor 3: the real DifficultyManager (archetype_* only exist after the enemy-archetypes merge).
	var dm = load("res://scripts/DifficultyManager.gd").new()
	tl.begin_floor(3, 6)
	for k in range(6):
		tl.record_room_visited(k)
	tl.record_enemy_defeated_by_archetype(2)
	_eq("floor 3 persisted", tl.record_floor(dm, {"floor_num": 3, "completion_time": 99.0, "player_max_hp": 100.0}), true)

	_eq("history size", tl.get_floor_history().size(), 3)
	tl.save_to_file()
	tl.close()

	# ---- reopen with a fresh logger and read back ----
	var tl2 = _new_logger(backend, tag)
	var rows: Array = tl2.load_floors(sid)
	_eq("rows read back", rows.size(), 3)
	if rows.size() == 3:
		var r1: Dictionary = rows[0]
		_eq("f1 floor_num", int(r1["floor_num"]), 1)
		_eq("f1 phase", r1["phase"], "calibration")
		_near("f1 completion_time", r1["completion_time"], 42.5)
		_eq("f1 deaths", int(r1["deaths"]), 1)
		_near("f1 damage_taken", r1["damage_taken"], 30.0)
		_near("f1 damage_dealt", r1["damage_dealt"], 88.5)
		_near("f1 player_max_hp", r1["player_max_hp"], 100.0)
		_eq("f1 rooms_total", int(r1["rooms_total"]), 5)
		_eq("f1 rooms_visited", int(r1["rooms_visited"]), 3)
		_near("f1 exploration_pct", r1["exploration_pct"], 60.0)
		_eq("f1 rooms_cleared", int(r1["rooms_cleared"]), 1)
		_eq("f1 enemies_defeated", int(r1["enemies_defeated"]), 5)
		_eq("f1 hazards_hit", int(r1["hazards_hit"]), 1)
		_eq("f1 pickups", int(r1["pickups_collected"]), 1)
		_near("f1 enemy_health", r1["enemy_health"], 72.5)
		_near("f1 enemy_damage", r1["enemy_damage"], 21.25)
		_near("f1 enemy_speed", r1["enemy_speed"], 133.0)
		_near("f1 enemy_aggro", r1["enemy_aggro"], 260.0)
		_near("f1 hazard_density", r1["hazard_density"], 0.4)
		_near("f1 resource_scarcity", r1["resource_scarcity"], 0.35)
		_eq("f1 room_count", int(r1["room_count"]), 7)
		_near("f1 archetype_complexity", r1["archetype_complexity"], 0.75)
		var mix := [0.1, 0.2, 0.3, 0.25, 0.15]
		for a in range(5):
			_near("f1 mix_%d" % a, r1["archetype_mix_%d" % a], mix[a])
		_near("f1 enemy_count_scale", r1["enemy_count_scale"], 1.25)
		_near("f1 difficulty_score", r1["difficulty_score"], 64.0)
		for k in range(8):
			_near("f1 obs_%d" % k, r1["obs_%d" % k], obs[k])
			_near("f1 action_%d" % k, r1["action_%d" % k], act[k])
		_near("f1 frame_avg_ms", r1["frame_avg_ms"], 1050.0 / 101.0)
		_near("f1 frame_p95_ms", r1["frame_p95_ms"], 10.0)
		_near("f1 frame_max_ms", r1["frame_max_ms"], 50.0)
		_eq("f1 kills[0]", int(r1["kills"].get(0, 0)), 2)
		_eq("f1 kills[4]", int(r1["kills"].get(4, 0)), 3)
		_eq("f1 kills keys", r1["kills"].size(), 2)

		var r2: Dictionary = rows[1]
		_eq("f2 phase", r2["phase"], "adaptive")
		_near("f2 completion_time", r2["completion_time"], 17.25)
		_near("f2 damage_taken", r2["damage_taken"], 5.5)
		_near("f2 exploration_pct", r2["exploration_pct"], 25.0)
		_near("f2 player_max_hp", r2["player_max_hp"], 120.0)
		_near("f2 obs_0 NULL", r2["obs_0"], null)
		_near("f2 action_7 NULL", r2["action_7"], null)
		_near("f2 frame_avg NULL", r2["frame_avg_ms"], null)
		_near("f2 perceived (set at record)", r2["perceived_difficulty"], 3.5)
		_eq("f2 kills empty", r2["kills"].size(), 0)

		var r3: Dictionary = rows[2]
		_near("f3 exploration_pct", r3["exploration_pct"], 100.0)
		_eq("f3 kills[2]", int(r3["kills"].get(2, 0)), 1)
		_near("f3 enemy_health (real DM)", r3["enemy_health"], dm.enemy_health)
		_near("f3 hazard_density (real DM)", r3["hazard_density"], dm.hazard_density)
		if "archetype_complexity" in dm:
			_near("f3 archetype_complexity (real DM)", r3["archetype_complexity"], dm.archetype_complexity)
		else:
			_near("f3 archetype_complexity absent -> NULL", r3["archetype_complexity"], null)
			_near("f3 archetype_mix_0 absent -> NULL", r3["archetype_mix_0"], null)
		_near("f3 obs NULL", r3["obs_3"], null)

	# perceived difficulty update (future post-floor rating)
	_eq("set_perceived_difficulty", tl2.set_perceived_difficulty(3, 4.0) or true, true)

	# ---- session row ----
	var sess: Dictionary = tl2._ensure_backend().get_session(sid)
	_eq("session found", sess.is_empty(), false)
	if not sess.is_empty():
		_eq("session game_version", sess.get("game_version", ""), "test-1.0")
		_eq("session consent", int(sess.get("consent", 0)), 1)
		_eq("session install_id len", str(sess.get("install_id", "")).length(), 32)

	# ---- CSV export ----
	var csv_path := "user://test_tel_%s.csv" % tag
	_eq("csv rows", tl2.export_corpus_csv(csv_path), 3)
	var f := FileAccess.open(csv_path, FileAccess.READ)
	if f == null:
		failures.append("csv not written")
	else:
		var lines: PackedStringArray = []
		while not f.eof_reached():
			var ln := f.get_line()
			if not ln.is_empty():
				lines.append(ln)
		f.close()
		_eq("csv line count (header + 3)", lines.size(), 4)
		var ncols := lines[0].split(",").size()
		_eq("csv header has session_id first", lines[0].begins_with("session_id,install_id,mode,"), true)
		_eq("csv header has kills_4 last", lines[0].ends_with(",kills_4"), true)
		for i in range(1, lines.size()):
			_eq("csv row %d column count" % i, lines[i].split(",").size(), ncols)
	var csv2 := "user://test_tel_%s_consented.csv" % tag
	_eq("consented csv rows", tl2.export_corpus_csv(csv2, true), 3)
	tl2.close()

func report(title: String) -> bool:
	if failures.is_empty():
		print("[FORGE TEST] %s: PASS (%d checks)" % [title, checks])
		return true
	for f in failures:
		printerr("[FORGE TEST] FAIL: " + f)
	return false
