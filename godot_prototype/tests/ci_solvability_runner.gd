# tests/ci_solvability_runner.gd
# Headless Godot 4.3 automated solvability verification harness.
# Tests 500 procedural layout seeds using graph reachability (BFS/A*)
# to verify unbroken path connectivity from start room to exit chamber.

extends SceneTree

const TOTAL_SEEDS: int = 500

func _init() -> void:
	print("==================================================")
	print("[FORGE CI] Starting Automated Solvability Harness")
	print("[FORGE CI] Target Seeds: %d" % TOTAL_SEEDS)
	print("==================================================")

	var dungeon_gen = load("res://scripts/DungeonGenerator.gd").new()
	var diff_mgr = load("res://scripts/DifficultyManager.gd").new()
	var passed_count: int = 0
	var failed_seeds: Array[int] = []

	for s in range(1, TOTAL_SEEDS + 1):
		seed(s)
		var rooms: Dictionary = dungeon_gen.generate_dungeon(diff_mgr)
		
		var start_pos: Vector2i = dungeon_gen.start_room_pos
		var exit_pos: Vector2i = dungeon_gen.exit_room_pos
		
		if not rooms.has(start_pos) or not rooms.has(exit_pos):
			failed_seeds.append(s)
			continue
			
		# BFS reachability search
		var queue: Array[Vector2i] = [start_pos]
		var visited: Dictionary = {start_pos: true}
		var reachable: bool = false
		
		var dir_map = {
			"N": Vector2i(0, -1),
			"S": Vector2i(0, 1),
			"E": Vector2i(1, 0),
			"W": Vector2i(-1, 0)
		}
		
		while not queue.is_empty():
			var curr = queue.pop_front()
			if curr == exit_pos:
				reachable = true
				break
				
			var room_data = rooms[curr]
			for door_dir in dir_map.keys():
				if room_data.doors.get(door_dir, false):
					var next_pos = curr + dir_map[door_dir]
					if rooms.has(next_pos) and not visited.has(next_pos):
						visited[next_pos] = true
						queue.append(next_pos)
		
		if reachable:
			passed_count += 1
		else:
			failed_seeds.append(s)

	print("--------------------------------------------------")
	print("[FORGE CI] Solvability Results: %d / %d Solvable (%.1f%%)" % [passed_count, TOTAL_SEEDS, (float(passed_count) / float(TOTAL_SEEDS)) * 100.0])
	print("--------------------------------------------------")

	if passed_count == TOTAL_SEEDS:
		print("[FORGE CI] PASS: 100% Topological Solvability Verified across %d seeds." % TOTAL_SEEDS)
		quit(0)
	else:
		printerr("[FORGE CI] FAIL: %d seeds failed solvability check: %s" % [failed_seeds.size(), str(failed_seeds)])
		quit(1)
