# tests/test_damage_telemetry.gd
# Verifies TC-01 inside the real game scene: damage the player takes and
# damage the player deals reach TelemetryLogger and the JSON snapshot.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_damage_telemetry.gd
extends SceneTree

var main_node: Node
var frames: int = 0
var stage: int = 0
var failures: Array[String] = []
var hits_dealt: float = 0.0

func _init() -> void:
	main_node = load("res://scenes/Main.tscn").instantiate()
	root.add_child(main_node)

func _process(_delta: float) -> bool:
	frames += 1
	if stage == 0 and frames > 2:
		main_node._on_start_run_requested()
		stage = 1
	elif stage == 1 and frames > 6:
		var tl = main_node.telemetry_logger
		var p = main_node.player
		# 1) Player takes one 20-damage hit (the TC-01 enemy hit).
		p.take_damage(20.0, Vector2.RIGHT)
		# 2) Player lands three 35-damage sword hits on one enemy.
		var enemy: Node = null
		for n in main_node.get_tree().get_nodes_in_group("enemies"):
			enemy = n
			break
		if enemy == null:
			for n in main_node.find_children("*", "CharacterBody2D", true, false):
				if n.has_method("take_damage") and n != p:
					enemy = n
					break
		if enemy == null:
			failures.append("no enemy found in the generated floor")
		else:
			enemy.max_health = 1000.0
			enemy.current_health = 1000.0
			for i in range(3):
				enemy.take_damage(35.0, Vector2.RIGHT)
				hits_dealt += 35.0
		tl.save_to_file()
		var snap: Dictionary = tl.get_summary()
		print("[FORGE TEST] snapshot: damage_taken=%s damage_dealt=%s" % [snap.damage_taken, snap.damage_dealt])
		if absf(float(snap.damage_taken) - 20.0) > 0.01:
			failures.append("damage_taken %s != 20.0" % snap.damage_taken)
		if absf(float(snap.damage_dealt) - hits_dealt) > 0.01:
			failures.append("damage_dealt %s != %.1f" % [snap.damage_dealt, hits_dealt])
		if failures.is_empty():
			print("[FORGE TEST] TC-01 telemetry capture: PASS (taken 20.0, dealt %.1f)" % hits_dealt)
			quit(0)
		else:
			for f in failures:
				printerr("[FORGE TEST] FAIL: " + f)
			quit(1)
		stage = 2
	return false
