# tests/benchmark_inference.gd
# Headless Godot 4.3 benchmark of the pure-GDScript PPO forward pass
# (PPOPolicy.predict). Measures wall-clock time per call with
# Time.get_ticks_usec() and reports mean / median / p95 / p99 / min / max.
#
# Run from the repository root:
#   godot --headless --path godot_prototype --script tests/benchmark_inference.gd
#
# Optional arguments (after "--"):
#   godot --headless --path godot_prototype --script tests/benchmark_inference.gd -- --runs=5000 --warmup=500
#
# Results are printed and also written to user://inference_benchmark.json
# (the absolute path is printed at the end). Exit code is 1 if the MEDIAN
# forward-pass time exceeds the NFR-06 requirement (1.0 ms), otherwise 0.
# Single-call maxima are reported but not gated: they are dominated by OS
# scheduling noise on shared machines.

extends SceneTree

const WEIGHTS_PATH: String = "res://ai/policy_weights.json"
const OBS_DIM: int = 8
const ACT_DIM: int = 7
const LIMIT_US: float = 1000.0  # NFR-06: < 1.0 ms per invocation

var n_runs: int = 1000
var n_warmup: int = 200

func _init() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--runs="):
			n_runs = int(arg.get_slice("=", 1))
		elif arg.begins_with("--warmup="):
			n_warmup = int(arg.get_slice("=", 1))

	print("==================================================")
	print("[FORGE BENCH] PPOPolicy.predict() latency benchmark")
	print("[FORGE BENCH] Godot %s | warm-up %d | timed runs %d" % [Engine.get_version_info()["string"], n_warmup, n_runs])
	print("==================================================")

	var policy = load("res://scripts/PPOPolicy.gd").new()
	if not policy.load_weights(WEIGHTS_PATH):
		printerr("[FORGE BENCH] FAIL: could not load %s (benchmark would measure the heuristic fallback)." % WEIGHTS_PATH)
		quit(1)
		return

	# Fixed-seed random observations in [0, 1]^8 (same inputs on every run).
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	var inputs: Array = []
	for i in range(n_warmup + n_runs):
		var obs := PackedFloat32Array()
		for k in range(OBS_DIM):
			obs.append(rng.randf())
		inputs.append(obs)

	# Warm-up (not timed): lets the GDScript VM / caches settle.
	for i in range(n_warmup):
		policy.predict(inputs[i])

	var samples: Array = []
	var bad_outputs: int = 0
	for i in range(n_runs):
		var obs: PackedFloat32Array = inputs[n_warmup + i]
		var t0: int = Time.get_ticks_usec()
		var out: PackedFloat32Array = policy.predict(obs)
		var dt: int = Time.get_ticks_usec() - t0
		samples.append(float(dt))
		if out.size() != ACT_DIM:
			bad_outputs += 1
		else:
			for v in out:
				if v < -1.0 or v > 1.0:
					bad_outputs += 1
					break

	samples.sort()
	var total: float = 0.0
	for v in samples:
		total += v
	var mean_us: float = total / float(n_runs)
	var median_us: float = _percentile(samples, 50.0)
	var p95_us: float = _percentile(samples, 95.0)
	var p99_us: float = _percentile(samples, 99.0)
	var min_us: float = samples[0]
	var max_us: float = samples[n_runs - 1]

	print("--------------------------------------------------")
	print("[FORGE BENCH] mean   : %8.1f us  (%.4f ms)" % [mean_us, mean_us / 1000.0])
	print("[FORGE BENCH] median : %8.1f us  (%.4f ms)" % [median_us, median_us / 1000.0])
	print("[FORGE BENCH] p95    : %8.1f us  (%.4f ms)" % [p95_us, p95_us / 1000.0])
	print("[FORGE BENCH] p99    : %8.1f us  (%.4f ms)" % [p99_us, p99_us / 1000.0])
	print("[FORGE BENCH] min    : %8.1f us  (%.4f ms)" % [min_us, min_us / 1000.0])
	print("[FORGE BENCH] max    : %8.1f us  (%.4f ms)" % [max_us, max_us / 1000.0])
	print("[FORGE BENCH] frame budget @60 FPS = 16666 us -> mean uses %.2f%%" % (mean_us / 16666.7 * 100.0))
	print("[FORGE BENCH] invalid outputs (size != %d or outside [-1,1]): %d" % [ACT_DIM, bad_outputs])
	print("--------------------------------------------------")

	var result := {
		"godot_version": Engine.get_version_info()["string"],
		"runs": n_runs,
		"warmup": n_warmup,
		"unit": "microseconds",
		"mean_us": mean_us,
		"median_us": median_us,
		"p95_us": p95_us,
		"p99_us": p99_us,
		"min_us": min_us,
		"max_us": max_us,
		"limit_us": LIMIT_US,
		"invalid_outputs": bad_outputs,
	}
	var f := FileAccess.open("user://inference_benchmark.json", FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(result, "\t"))
		f.close()
		print("[FORGE BENCH] Wrote %s" % ProjectSettings.globalize_path("user://inference_benchmark.json"))

	if bad_outputs > 0:
		printerr("[FORGE BENCH] FAIL: forward pass produced invalid outputs.")
		quit(1)
	elif median_us > LIMIT_US:
		printerr("[FORGE BENCH] FAIL: median %.1f us exceeds the %.0f us requirement." % [median_us, LIMIT_US])
		quit(1)
	else:
		print("[FORGE BENCH] PASS: median %.1f us <= %.0f us (NFR-06)." % [median_us, LIMIT_US])
		quit(0)

func _percentile(sorted_samples: Array, pct: float) -> float:
	var idx: int = int(ceil(pct / 100.0 * float(sorted_samples.size()))) - 1
	idx = clampi(idx, 0, sorted_samples.size() - 1)
	return sorted_samples[idx]
