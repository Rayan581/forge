# tests/test_telemetry_fallback.gd
# JSON fallback backend: records 3 floors, reopens, reads them back and exports the CSV.
# Must pass whether or not the godot-sqlite addon is installed (the backend is forced to "json").
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_telemetry_fallback.gd
extends SceneTree

func _init() -> void:
	var sc = load("res://tests/telemetry_scenario.gd").new()
	sc.run("json", "fallback", "json")
	var ok: bool = sc.report("telemetry JSON fallback")
	sc.cleanup("fallback")
	quit(0 if ok else 1)
