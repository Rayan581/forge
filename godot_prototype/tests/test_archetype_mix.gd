# tests/test_archetype_mix.gd
# Verifies contract section 3: archetype-mix reference vectors, sums to 1, sampling frequencies,
# 7/8-dim apply_ppo_action, calibration mixes, static baseline mix, stat multipliers.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_archetype_mix.gd
extends SceneTree

var failures: Array[String] = []

const REF := {
	-1.0: [0.564138, 0.102288, 0.044595, 0.062481, 0.226498],
	-0.5: [0.188301, 0.188301, 0.061960, 0.101129, 0.460308],
	0.0: [0.083394, 0.424534, 0.109655, 0.207276, 0.175141],
	0.5: [0.052035, 0.192817, 0.272895, 0.392356, 0.089897],
	1.0: [0.043250, 0.127906, 0.514932, 0.247894, 0.066018],
}
const CAL := {
	1: [0.70, 0.0, 0.0, 0.0, 0.30],
	2: [0.50, 0.0, 0.0, 0.0, 0.50],
	3: [0.0, 0.75, 0.0, 0.25, 0.0],
	4: [0.25, 0.25, 0.0, 0.30, 0.20],
	5: [0.15, 0.25, 0.30, 0.20, 0.10],
}

func _fail(msg: String) -> void:
	failures.append(msg)

func _init() -> void:
	var DM = load("res://scripts/DifficultyManager.gd")

	# (a) reference vectors + sum to one + enum order
	if int(Enemy.Archetype.HEAVY_BRUTE) != 2 or int(Enemy.Archetype.AGILE_SKIRMISHER) != 3 or int(Enemy.Archetype.SWARMER) != 4:
		_fail("Archetype enum order violates contract")
	for a7 in REF.keys():
		var p: PackedFloat32Array = DM.compute_archetype_mix(a7)
		var s := 0.0
		for i in range(5):
			s += p[i]
			if absf(p[i] - REF[a7][i]) > 1e-5:
				_fail("mix(a7=%.1f)[%d] = %.6f, want %.6f" % [a7, i, p[i], REF[a7][i]])
			if p[i] < 0.03 - 1e-6:
				_fail("mix(a7=%.1f)[%d] below 3%% floor" % [a7, i])
		if absf(s - 1.0) > 1e-5:
			_fail("mix(a7=%.1f) sums to %.6f" % [a7, s])
	for a7 in [-3.0, 3.0]:  # clamped
		var p2: PackedFloat32Array = DM.compute_archetype_mix(a7)
		var ref: Array = REF[-1.0] if a7 < 0 else REF[1.0]
		if absf(p2[0] - ref[0]) > 1e-5:
			_fail("a7 not clamped to [-1, 1]")
	print("[FORGE TEST] (a) mix reference vectors checked")

	# (b) sampling frequencies: 10,000 slots per mix within +-2 percentage points
	var dm = DM.new()
	seed(12345)
	var mixes: Array = []
	for a7 in REF.keys():
		mixes.append(Array(DM.compute_archetype_mix(a7)))
	for k in CAL.keys():
		mixes.append(CAL[k])
	for m in mixes:
		dm.set_archetype_mix(m)
		var counts := [0, 0, 0, 0, 0]
		for n in range(10000):
			counts[dm.sample_archetype(randf())] += 1
		for i in range(5):
			var freq: float = counts[i] / 10000.0
			if absf(freq - m[i]) > 0.02:
				_fail("sampling mix %s: archetype %d freq %.4f vs %.4f" % [str(m), i, freq, m[i]])
	print("[FORGE TEST] (b) sampling within +-2pp for %d mixes" % mixes.size())

	# (d) apply_ppo_action with 8- and 7-length vectors
	var dm8 = DM.new()
	dm8.apply_ppo_action(PackedFloat32Array([0, 0, 0, 0, 0, 0, 0, 1.0]))
	for i in range(5):
		if absf(dm8.archetype_mix[i] - REF[1.0][i]) > 1e-5:
			_fail("8-dim action a7=1 mix[%d] wrong" % i)
	if absf(dm8.archetype_complexity - 1.0) > 1e-6:
		_fail("8-dim action complexity != 1")
	if absf(dm8.ranged_enemy_ratio - dm8.archetype_mix[1]) > 1e-6:
		_fail("ranged_enemy_ratio not derived from p[pyromancer]")
	var dm7 = DM.new()
	dm7.apply_ppo_action(PackedFloat32Array([0.5, 0.5, 0.5, 0.5, 0, 0, 0]))
	var score: float = dm7.calculate_difficulty_score().score
	var want_a7: float = 2.0 * score / 100.0 - 1.0
	var want7: PackedFloat32Array = DM.compute_archetype_mix(want_a7)
	for i in range(5):
		if absf(dm7.archetype_mix[i] - want7[i]) > 1e-5:
			_fail("7-dim legacy fallback mix[%d] wrong" % i)
	if absf(dm7.archetype_complexity - score / 100.0) > 1e-5:
		_fail("7-dim legacy complexity != score/100")
	var dm_short = DM.new()
	var before: float = dm_short.enemy_health
	dm_short.apply_ppo_action(PackedFloat32Array([0, 0, 0]))  # too short: ignored
	if dm_short.enemy_health != before:
		_fail("too-short action must be ignored")
	print("[FORGE TEST] (d) apply_ppo_action 7/8-dim ok (legacy score %d)" % int(score))

	# calibration + static baseline
	for lvl in CAL.keys():
		var dmc = DM.new()
		var cal: Dictionary = dmc.apply_calibration_level(lvl)
		for i in range(5):
			if absf(cal.archetype_mix[i] - CAL[lvl][i]) > 1e-9 or absf(dmc.archetype_mix[i] - CAL[lvl][i]) > 1e-6:
				_fail("calibration L%d mix[%d] mismatch" % [lvl, i])
		if absf(dmc.ranged_enemy_ratio - CAL[lvl][1]) > 1e-6:
			_fail("calibration L%d ranged ratio not derived" % lvl)
	var dms = DM.new()
	dms.static_baseline_mode = true
	for fl in [1, 4, 9]:
		dms.apply_static_baseline(fl)
		var ps: PackedFloat32Array = DM.compute_archetype_mix(-0.1)
		for i in range(5):
			if absf(dms.archetype_mix[i] - ps[i]) > 1e-6:
				_fail("static baseline floor %d mix[%d] != mix(a7=-0.1)" % [fl, i])
		if absf(dms.archetype_complexity - 0.45) > 1e-6:
			_fail("static baseline complexity != 0.45")
	print("[FORGE TEST] calibration L1-L5 and static baseline mixes ok")

	# stat multipliers (contract section 1)
	var mult := {
		0: [1.0, 1.0, 1.0, 1.0], 1: [0.75, 0.9, 0.92, 420.0],
		2: [2.0, 1.4, 0.55, 0.8], 3: [0.8, 0.8, 1.3, 1.2], 4: [0.35, 0.45, 1.15, 1.0]}
	for a in mult.keys():
		var e = load("res://scenes/Enemy.tscn").instantiate()
		e.set_archetype(a)
		e.configure_parameters(60.0, 20.0, 125.0, 240.0)
		var m: Array = mult[a]
		var want_aggro: float = 240.0 * m[3] if a != 1 else 420.0
		if absf(e.max_health - 60.0 * m[0]) > 1e-4 or absf(e.attack_damage - 20.0 * m[1]) > 1e-4 \
				or absf(e.move_speed - 125.0 * m[2]) > 1e-4 or absf(e.aggro_radius - want_aggro) > 1e-4:
			_fail("stat multipliers wrong for archetype %d" % a)
		e.free()
	print("[FORGE TEST] stat multipliers ok")

	if failures.is_empty():
		print("[FORGE TEST] test_archetype_mix: PASS")
		quit(0)
	else:
		for f in failures:
			printerr("[FORGE TEST] FAIL: " + f)
		quit(1)
