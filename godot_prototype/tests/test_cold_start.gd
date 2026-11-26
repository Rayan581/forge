# tests/test_cold_start.gd
# Verifies TC-02: the cold-start CR0 score and the Floor-6 seed observation s0.
# Plays back three scripted calibration profiles through TelemetryLogger and
# DifficultyManager (no rendering) and checks
#   (1) CR0 against values worked out by hand from Eq. 6.1-6.5, and
#   (2) that s0[0..2] uses the training observation scales:
#       floor time / 90 s for a 6-room floor, deaths / 3, damage / max HP.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_cold_start.gd
extends SceneTree

const EPS: float = 0.01
const ROOMS := [3, 4, 4, 5, 5]
const W := [1.0, 1.5, 2.0, 2.5, 3.0]
const MAX_HP: float = 100.0

var failures: Array[String] = []
var checks_run: int = 0
const CHECKS_EXPECTED: int = 15  # 3 profiles x (CR0 + 3 s0 dims + count-scale check)

func _check(label: String, got: float, want: float) -> void:
	checks_run += 1
	if absf(got - want) > EPS:
		failures.append("%s: got %.4f, expected %.4f" % [label, got, want])
	else:
		print("[FORGE TEST]   %s = %.3f (ok)" % [label, got])

func _expected_obs(spr: Array, deaths: Array, dmg: Array) -> Array:
	var t := 0.0
	var d := 0.0
	var m := 0.0
	for i in range(5):
		t += clampf(spr[i] * 6.0 / 90.0, 0.0, 1.0) * W[i]
		d += clampf(deaths[i] / 3.0, 0.0, 1.0) * W[i]
		m += clampf(dmg[i] / MAX_HP, 0.0, 1.0) * W[i]
	return [t / 10.0, d / 10.0, m / 10.0]

func _run_profile(name: String, spr: Array, deaths: Array, dmg: Array, want_cr0: float) -> void:
	print("[FORGE TEST] Profile: %s" % name)
	var tl = load("res://scripts/TelemetryLogger.gd").new()
	for i in range(5):
		tl.record_calibration_floor(i + 1, spr[i] * ROOMS[i], deaths[i], dmg[i], ROOMS[i], 0)
	var prof: Dictionary = tl.compute_cr0_baseline(MAX_HP)
	_check(name + " CR0", prof.cr0_score, want_cr0)

	var dm = load("res://scripts/DifficultyManager.gd").new()
	dm.apply_calibration_level(5)
	var s0: PackedFloat32Array = dm.build_observation_from_cr0(prof, 6)
	var expd := _expected_obs(spr, deaths, dmg)
	_check(name + " s0[time]", s0[0], expd[0])
	_check(name + " s0[deaths]", s0[1], expd[1])
	_check(name + " s0[damage]", s0[2], expd[2])
	if s0.size() != 8:
		failures.append(name + ": s0 has %d dims" % s0.size())

	# The PPO step that follows must not keep the calibration-only enemy count multiplier.
	var pol = load("res://scripts/PPOPolicy.gd").new()
	pol.load_weights("res://ai/policy_weights.json")
	dm.apply_ppo_action(pol.predict(s0))
	checks_run += 1
	if absf(dm.enemy_count_scale - 1.0) > 0.0001:
		failures.append(name + ": enemy_count_scale %.2f carried into PPO floors" % dm.enemy_count_scale)

func _init() -> void:
	# Same three profiles as Section 7.4 of the report.
	_run_profile("Novice", [10.0, 12.0, 15.0, 15.0, 15.0], [0, 0, 2, 2, 2], [60.0, 80.0, 120.0, 120.0, 120.0], 19.65)
	_run_profile("Intermediate", [9.0, 9.0, 9.0, 9.0, 9.0], [0, 0, 0, 1, 1], [70.0, 70.0, 70.0, 70.0, 70.0], 60.25)
	_run_profile("Expert", [4.5, 4.5, 4.5, 4.5, 4.5], [0, 0, 0, 0, 0], [0.0, 0.0, 0.0, 0.0, 0.0], 95.0)

	if checks_run != CHECKS_EXPECTED:
		failures.append("only %d of %d checks ran (script error?)" % [checks_run, CHECKS_EXPECTED])
	if failures.is_empty():
		print("[FORGE TEST] TC-02 cold start: PASS")
		quit(0)
	else:
		for f in failures:
			printerr("[FORGE TEST] FAIL: " + f)
		quit(1)
