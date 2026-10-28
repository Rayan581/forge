# tests/test_telemetry_logger.gd
# Tests TelemetryLogger session deduplication, floor telemetry (Judge training data),
# and CR0 calibration baseline computation.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_telemetry_logger.gd
extends SceneTree

func _init() -> void:
	var failures: Array[String] = []
	var tl = TelemetryLogger.new()
	
	# 1. Test session deduplication on save_to_file
	tl.record_room_cleared()
	tl.record_damage_dealt(100.0)
	tl.save_to_file()
	
	tl.record_room_cleared()
	tl.record_damage_taken(25.0)
	tl.save_to_file()
	
	var summary = tl.get_summary()
	if summary.rooms_cleared != 2:
		failures.append("rooms_cleared expected 2, got %s" % summary.rooms_cleared)
	if summary.damage_dealt != 100.0:
		failures.append("damage_dealt expected 100.0, got %s" % summary.damage_dealt)
	if summary.damage_taken != 25.0:
		failures.append("damage_taken expected 25.0, got %s" % summary.damage_taken)
		
	# 2. Test per-floor telemetry for Judge model
	var diff_params = {
		"enemy_health": 55.0,
		"enemy_damage": 18.0,
		"enemy_speed": 120.0,
		"enemy_aggro": 220.0,
		"hazard_density": 0.35,
		"resource_scarcity": 0.50,
		"room_count": 7.0,
		"enemy_count_scale": 1.1
	}
	var floor_rec = tl.record_floor_telemetry(
		1, 45.2, 0, 320.0, 30.0, 6, 8, 1, 2,
		diff_params, 0.6, 0.4, [0.5, 0.0], [0.1, 0.2]
	)
	if floor_rec.floor_number != 1:
		failures.append("floor_number expected 1, got %s" % floor_rec.floor_number)
	if floor_rec.enemy_health != 55.0:
		failures.append("enemy_health expected 55.0, got %s" % floor_rec.enemy_health)
	if floor_rec.damage_exchange_ratio < 10.0:
		failures.append("damage_exchange_ratio expected > 10.0, got %s" % floor_rec.damage_exchange_ratio)
		
	# 3. Test CR0 calibration calculation
	tl.record_calibration_floor(1, 35.0, 0, 20.0, 5, 20)
	tl.record_calibration_floor(2, 40.0, 0, 30.0, 5, 30)
	tl.record_calibration_floor(3, 45.0, 1, 50.0, 6, 45)
	tl.record_calibration_floor(4, 50.0, 1, 60.0, 6, 60)
	tl.record_calibration_floor(5, 60.0, 2, 90.0, 7, 80)
	var cr0 = tl.compute_cr0_baseline(100.0)
	if cr0.cr0_score <= 0.0 or cr0.cr0_score > 100.0:
		failures.append("cr0_score out of range: %s" % cr0.cr0_score)
		
	if failures.is_empty():
		print("[FORGE TEST] TelemetryLogger unit tests: PASS")
		quit(0)
	else:
		for f in failures:
			printerr("[FORGE TEST] FAIL: " + f)
		quit(1)
