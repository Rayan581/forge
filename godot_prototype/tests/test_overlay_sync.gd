extends SceneTree
## Regression test: DefenseOverlay.sync_ui_with_manager() must not write stale slider
## values back into the DifficultyManager (bug: only enemy_health survived a sync).
func _initialize() -> void:
	var overlay = load("res://scenes/DefenseOverlay.tscn").instantiate()
	root.add_child(overlay)
	await process_frame
	var dm := DifficultyManager.new()
	overlay.setup(dm, TelemetryLogger.new())
	var ok := true
	for lvl in [1, 2, 3, 4, 5]:
		var cal: Dictionary = dm.apply_calibration_level(lvl)
		overlay.sync_ui_with_manager()
		var pairs = [["enemy_health", cal.health], ["enemy_damage", cal.damage], ["enemy_speed", cal.speed],
			["enemy_aggro", cal.aggro], ["hazard_density", cal.hazard], ["resource_scarcity", cal.scarcity]]
		for p in pairs:
			var got: float = dm.get(p[0])
			if absf(got - float(p[1])) > 1e-4:
				ok = false
				printerr("[FORGE TEST] FAIL overlay sync L%d %s: expected %.3f got %.3f" % [lvl, p[0], p[1], got])
	# 8-dim PPO action must also survive the sync
	dm.apply_ppo_action(PackedFloat32Array([0.5, -0.5, 0.2, -0.2, 0.1, 0.3, 0.0, 0.4]))
	var snap = [dm.enemy_health, dm.enemy_damage, dm.enemy_speed, dm.enemy_aggro, dm.hazard_density, dm.resource_scarcity]
	overlay.sync_ui_with_manager()
	var after = [dm.enemy_health, dm.enemy_damage, dm.enemy_speed, dm.enemy_aggro, dm.hazard_density, dm.resource_scarcity]
	for i in snap.size():
		if absf(snap[i] - after[i]) > 1e-4:
			ok = false
			printerr("[FORGE TEST] FAIL overlay sync PPO idx %d: %.3f -> %.3f" % [i, snap[i], after[i]])
	if ok:
		print("[FORGE TEST] test_overlay_sync: PASS")
		quit(0)
	else:
		print("[FORGE TEST] test_overlay_sync: FAIL")
		quit(1)
