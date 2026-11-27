# tests/test_difficulty_upgrades.gd
# Checks the difficulty upgrades of 2026-11-27:
#   (1) PPO floors scale the enemy count with their score (1.0 up to 40 -> 1.3 at 70+),
#   (2) the exit-room champion appears on FORGE floors scoring >= 60 (and still at health >= 85),
#       but the baselines keep the old rule,
#   (3) the Apex Trial: unlocked only by a clean Floor 5, makes Floor 6 a calibration floor with
#       the trial settings, is reset per run, and is left out of the CR0 / PPO seed summary,
#   (4) a new session clears the calibration records of the previous run.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_difficulty_upgrades.gd
extends SceneTree

var failures: Array[String] = []
var checks: int = 0

func _ok(label: String, cond: bool) -> void:
	checks += 1
	if not cond:
		failures.append(label)

func _near(label: String, got: float, want: float) -> void:
	_ok("%s (got %.3f, want %.3f)" % [label, got, want], absf(got - want) < 0.001)

func _init() -> void:
	var DM = load("res://scripts/DifficultyManager.gd")
	# (1) count scale rule
	_near("count scale at 20", DM.adaptive_count_scale(20.0), 1.0)
	_near("count scale at 40", DM.adaptive_count_scale(40.0), 1.0)
	_near("count scale at 55", DM.adaptive_count_scale(55.0), 1.15)
	_near("count scale at 70", DM.adaptive_count_scale(70.0), 1.3)
	_near("count scale at 95", DM.adaptive_count_scale(95.0), 1.3)
	var dm = DM.new()
	var hard := PackedFloat32Array([0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.0, 0.5])
	dm.apply_ppo_action(hard)
	var sc: int = dm.calculate_difficulty_score().score
	_ok("hard PPO action scores >= 70 (got %d)" % sc, sc >= 70)
	_near("hard PPO floor count scale", dm.enemy_count_scale, 1.3)
	var easy := PackedFloat32Array([-0.8, -0.8, -0.8, -0.8, -0.8, -0.8, 0.0, -0.5])
	dm.apply_ppo_action(easy)
	_near("easy PPO floor count scale", dm.enemy_count_scale, 1.0)

	# (2) champion rule
	dm.apply_ppo_action(hard)
	_ok("champion on a hard FORGE floor (health %.0f)" % dm.enemy_health, dm.champion_enabled())
	dm.apply_ppo_action(easy)
	_ok("no champion on an easy FORGE floor", not dm.champion_enabled())
	dm.apply_calibration_level(5)
	_ok("champion on Floor 5 (health 90)", dm.champion_enabled())
	var st = DM.new()
	st.set_generator_mode("static")
	st.apply_static_baseline(1)
	st.enemy_speed = 220.0
	st.enemy_aggro = 450.0
	st.hazard_density = 0.8
	st.resource_scarcity = 0.9
	_ok("baseline keeps the health >= 85 rule (score %d)" % st.calculate_difficulty_score().score,
		not st.champion_enabled())

	# (3) Apex Trial
	var a = DM.new()
	_ok("Floor 6 is adaptive by default", not a.is_in_calibration(6))
	_ok("a death on Floor 5 does not unlock it", not a.qualifies_for_apex_trial(1, 20.0, 100.0))
	_ok("losing max HP on Floor 5 does not unlock it", not a.qualifies_for_apex_trial(0, 100.0, 100.0))
	_ok("a clean Floor 5 unlocks it", a.qualifies_for_apex_trial(0, 60.0, 100.0))
	a.begin_apex_trial()
	_ok("Floor 6 is calibration during the trial", a.is_in_calibration(6))
	_ok("Floor 7 is not", not a.is_in_calibration(7))
	var cal: Dictionary = a.apply_calibration_level(6)
	_ok("trial settings applied", cal.get("title", "") == "Level 6: Apex Trial" and a.enemy_health == 110.0)
	_near("trial count scale", a.enemy_count_scale, 1.4)
	var tsc: int = a.calculate_difficulty_score().score
	_ok("trial scores above Floor 5's 68 (got %d)" % tsc, tsc > 68)
	a.reset_run_state()
	_ok("trial reset for a new run", not a.is_in_calibration(6))
	var b = DM.new()
	b.set_generator_mode("bsp")
	_ok("baselines never get the trial", not b.qualifies_for_apex_trial(0, 0.0, 100.0))
	var off = DM.new()
	off.apex_trial_enabled = false
	_ok("switch turns it off", not off.qualifies_for_apex_trial(0, 0.0, 100.0))

	# CR0 / s0 ignore the trial floor
	var tl = load("res://scripts/TelemetryLogger.gd").new()
	var rooms := [3, 4, 4, 5, 5]
	for i in range(5):
		tl.record_calibration_floor(i + 1, 30.0, 0, 50.0, rooms[i], 0)
	var p5: Dictionary = tl.compute_cr0_baseline(100.0)
	tl.record_calibration_floor(6, 300.0, 3, 300.0, 6, 86)
	var p6: Dictionary = tl.compute_cr0_baseline(100.0)
	_near("s0 time ignores the trial", p6.obs_time, p5.obs_time)
	_near("s0 damage ignores the trial", p6.obs_dmg_ratio, p5.obs_dmg_ratio)
	_near("s0 time = mean time / 90", p5.obs_time, 30.0 / 90.0)
	_near("CR0 ignores the trial", p6.cr0_score, p5.cr0_score)

	# (4) new session clears calibration records
	tl.start_new_session()
	_ok("records cleared by a new session", tl.calibration_records.is_empty())

	if checks != 29:
		failures.append("ran %d checks, expected 29 (script error?)" % checks)
	if failures.is_empty():
		print("[FORGE TEST] difficulty upgrades: PASS (%d checks)" % checks)
		quit(0)
	else:
		for f in failures:
			printerr("[FORGE TEST] FAIL: " + f)
		quit(1)
