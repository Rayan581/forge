# tests/ci_solvability_runner.gd
# Headless automated solvability regression harness.
# For every room count the game can request (3-5 on the calibration floors,
# 5-9 from the PPO policy) it generates 500 seeded layouts and runs a
# breadth-first search over the door graph from the start room to the exit.
# The generator attaches every new room to an existing one, so the layout is a
# spanning tree and connected by construction; this harness is a regression
# test that guards that property (and the requested room count), not a proof.

extends SceneTree

const TOTAL_SEEDS: int = 500
const ROOM_COUNTS: Array[int] = [3, 4, 5, 6, 7, 8, 9]

func _init() -> void:
	print("==================================================")
	print("[FORGE CI] Starting Automated Solvability Harness")
	print("[FORGE CI] Seeds per room count: %d | room counts: %s" % [TOTAL_SEEDS, str(ROOM_COUNTS)])
	print("==================================================")

	var dungeon_gen = load("res://scripts/DungeonGenerator.gd").new()
	var diff_mgr = load("res://scripts/DifficultyManager.gd").new()
	var total: int = 0
	var passed_count: int = 0
	var failures: Array[String] = []

	var dir_map = {
		"N": Vector2i(0, -1),
		"S": Vector2i(0, 1),
		"E": Vector2i(1, 0),
		"W": Vector2i(-1, 0)
	}

	for n_rooms in ROOM_COUNTS:
		var passed_here: int = 0
		for s in range(1, TOTAL_SEEDS + 1):
			total += 1
			seed(s)
			var rooms: Dictionary = dungeon_gen.generate_dungeon(diff_mgr, n_rooms)
			var start_pos: Vector2i = dungeon_gen.start_room_pos
			var exit_pos: Vector2i = dungeon_gen.exit_room_pos

			if rooms.size() != n_rooms or not rooms.has(start_pos) or not rooms.has(exit_pos) or start_pos == exit_pos:
				failures.append("rooms=%d seed=%d (layout)" % [n_rooms, s])
				continue

			# BFS over the door graph; also checks that every door has its matching
			# door on the neighbouring room.
			var queue: Array[Vector2i] = [start_pos]
			var visited: Dictionary = {start_pos: true}
			var doors_ok: bool = true
			while not queue.is_empty():
				var curr = queue.pop_front()
				var room_data = rooms[curr]
				for door_dir in dir_map.keys():
					if room_data.doors.get(door_dir, false):
						var next_pos = curr + dir_map[door_dir]
						if not rooms.has(next_pos):
							doors_ok = false
							continue
						var opp = {"N": "S", "S": "N", "E": "W", "W": "E"}[door_dir]
						if not rooms[next_pos].doors.get(opp, false):
							doors_ok = false
						if not visited.has(next_pos):
							visited[next_pos] = true
							queue.append(next_pos)

			if visited.has(exit_pos) and visited.size() == rooms.size() and doors_ok:
				passed_count += 1
				passed_here += 1
			else:
				failures.append("rooms=%d seed=%d (reachability)" % [n_rooms, s])
		print("[FORGE CI] rooms=%d: %d / %d solvable" % [n_rooms, passed_here, TOTAL_SEEDS])

	print("--------------------------------------------------")
	print("[FORGE CI] Solvability Results: %d / %d Solvable" % [passed_count, total])
	print("--------------------------------------------------")

	if passed_count == total:
		print("[FORGE CI] PASS: every room reachable in all %d layouts." % total)
		quit(0)
	else:
		printerr("[FORGE CI] FAIL: %d layouts failed: %s" % [failures.size(), str(failures.slice(0, 20))])
		quit(1)
