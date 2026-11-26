# tests/test_static_baseline.gd
# Verifies TC-10: the static baseline scales enemy health and damage by exactly
# +8 % of the Intermediate preset per floor and leaves all other parameters fixed.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_static_baseline.gd
extends SceneTree

const EPS: float = 0.0001

func _init() -> void:
	var dm = load("res://scripts/DifficultyManager.gd").new()
	var p = dm.PRESETS[dm.ProfileTier.INTERMEDIATE]
	var failures: Array[String] = []

	dm.static_baseline_mode = true
	if dm.is_in_calibration(3):
		failures.append("calibration must be disabled in static mode")

	var prev_hp: float = 0.0
	var prev_dmg: float = 0.0
	for floor_num in range(1, 11):
		dm.apply_static_baseline(floor_num)
		var exp_hp: float = p.health * (1.0 + 0.08 * float(floor_num - 1))
		var exp_dmg: float = p.damage * (1.0 + 0.08 * float(floor_num - 1))
		if absf(dm.enemy_health - exp_hp) > EPS:
			failures.append("floor %d health %.4f != %.4f" % [floor_num, dm.enemy_health, exp_hp])
		if absf(dm.enemy_damage - exp_dmg) > EPS:
			failures.append("floor %d damage %.4f != %.4f" % [floor_num, dm.enemy_damage, exp_dmg])
		if floor_num > 1:
			if absf((dm.enemy_health - prev_hp) - p.health * 0.08) > EPS:
				failures.append("floor %d health step is not +8%% of base" % floor_num)
			if absf((dm.enemy_damage - prev_dmg) - p.damage * 0.08) > EPS:
				failures.append("floor %d damage step is not +8%% of base" % floor_num)
		if dm.enemy_speed != p.speed or dm.enemy_aggro != p.aggro or dm.hazard_density != p.hazard:
			failures.append("floor %d: non-scaled parameters changed" % floor_num)
		prev_hp = dm.enemy_health
		prev_dmg = dm.enemy_damage

	dm.static_baseline_mode = false
	if not dm.is_in_calibration(3):
		failures.append("calibration must be re-enabled when static mode is off")

	if failures.is_empty():
		print("[FORGE TEST] TC-10 static baseline: PASS (floors 1-10, exactly +8% per floor)")
		quit(0)
	else:
		for f in failures:
			printerr("[FORGE TEST] FAIL: " + f)
		quit(1)
