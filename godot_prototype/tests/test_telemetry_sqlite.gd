# tests/test_telemetry_sqlite.gd
# SQLite backend (godot-sqlite addon). Skips with exit 0 if the "SQLite" class is not registered
# (addon not installed). In CI the addon is downloaded first (see .github/workflows/ci.yml).
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_telemetry_sqlite.gd
extends SceneTree

func _init() -> void:
	if not ClassDB.class_exists("SQLite"):
		print("SKIP (godot-sqlite not installed)")
		quit(0)
		return
	var sc = load("res://tests/telemetry_scenario.gd").new()
	var tag := "sqlite"
	sc.cleanup(tag)
	# Seed a legacy flat-JSON history: it must be imported exactly once on the first SQLite run.
	# (Passed into run(), which cleans up first and then writes it, so the cleanup cannot delete it.)
	var legacy_json := JSON.stringify([
		{"session_id": "sess_legacy_1", "timestamp": 1700000000, "elapsed_seconds": 10.0, "rooms_cleared": 1, "total_deaths": 0,
		 "damage_dealt": 5.0, "damage_taken": 2.0, "enemies_defeated": 3, "pickups_collected": 0, "hazard_hits": 0},
		{"session_id": "sess_legacy_1", "timestamp": 1700000000, "elapsed_seconds": 25.0, "rooms_cleared": 2, "total_deaths": 1,
		 "damage_dealt": 9.0, "damage_taken": 4.0, "enemies_defeated": 6, "pickups_collected": 1, "hazard_hits": 1},
	])
	sc.run("sqlite", tag, "sqlite", legacy_json)
	var tl = sc._new_logger("sqlite", tag)
	var b = tl._ensure_backend()
	var leg: Dictionary = b.get_session("sess_legacy_1")
	sc._eq("legacy session imported", leg.is_empty(), false)
	sc._near("legacy elapsed (last snapshot wins)", leg.get("elapsed_seconds", null), 25.0)
	sc._eq("legacy mode unknown", leg.get("mode", ""), "unknown")
	# Third open: schema_version must still be a single v1 row and the legacy import must not repeat.
	tl.close()
	var tl3 = sc._new_logger("sqlite", tag)
	var b3 = tl3._ensure_backend()
	sc._eq("backend sqlite after reopen", b3.backend_name(), "sqlite")
	sc._eq("legacy still single row", b3.get_session("sess_legacy_1").get("rooms_cleared", -1), 2)
	tl3.close()
	var ok: bool = sc.report("telemetry SQLite")
	sc.cleanup(tag)
	# Deferred: quitting from inside _init() can leave the process hanging once the native
	# godot-sqlite extension is loaded; let the engine finish starting up first.
	call_deferred("quit", 0 if ok else 1)
