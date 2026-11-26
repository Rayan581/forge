# tests/ci_solvability_runner.gd
# Headless automated solvability regression harness.
# For every room count the game can request (3-5 on the calibration floors,
# 5-9 from the PPO policy) it generates 500 seeded layouts and runs a
# breadth-first search over the door graph from the start room to the exit.
# The generator attaches every new room to an existing one, so the layout is a
# spanning tree and connected by construction; this harness is a regression
# test that guards that property (and the requested room count), not a proof.
#
# Map-gen additions (per layout): no overlapping room / corridor rectangles in world space
# (rooms include their 32 px wall ring), exit BFS depth == max BFS depth and >= 2 when there are
# >= 3 rooms, every room size inside the contract bounds; and across the whole run at least
# 6 distinct room sizes per 100 rooms.
#
# BSP baseline: the same checks also run on 500 seeded BSP layouts (DungeonGenerator.layout_mode =
# "bsp", BSPGenerator.gd), whose room count (5-9) is decided by the BSP tree. Reported as "rooms=bsp".

extends SceneTree

const TOTAL_SEEDS: int = 500
const ROOM_COUNTS: Array[int] = [3, 4, 5, 6, 7, 8, 9]
const BSP_PASS: int = -1 # marker in the pass list: BSP layouts (room count chosen by the BSP tree)
const WALL: float = 32.0
const DOOR_W: float = 96.0
const MIN_SIZE := Vector2(560, 400)
const MAX_SIZE := Vector2(1120, 720)

## World-space rectangles (outer, wall ring included) of the rooms and corridors of a layout.
func _geometry_ok(rooms: Dictionary) -> String:
	var rects: Array = [] # {r: Rect2, tag: String, a: Vector2i, b: Vector2i}
	for pos in rooms.keys():
		var rd = rooms[pos]
		rects.append({"r": Rect2(rd.world_pos - rd.size / 2.0 - Vector2(WALL, WALL), rd.size + Vector2(WALL, WALL) * 2.0), "tag": "room", "a": pos, "b": pos})
		for dn in ["S", "E"]:
			if not rd.doors[dn]:
				continue
			var l: float = rd.corridors.get(dn, -1.0)
			if l < 96.0:
				return "corridor too short/missing"
			var half = DOOR_W / 2.0 + WALL
			var rect: Rect2
			var nb: Vector2i
			if dn == "S":
				rect = Rect2(rd.world_pos.x - half, rd.world_pos.y + rd.size.y / 2.0, half * 2.0, l)
				nb = pos + Vector2i(0, 1)
			else:
				rect = Rect2(rd.world_pos.x + rd.size.x / 2.0, rd.world_pos.y - half, l, half * 2.0)
				nb = pos + Vector2i(1, 0)
			# the corridor must end exactly at the neighbour's interior edge (straight door-to-door)
			var n = rooms[nb]
			if dn == "S" and absf(rect.end.y - (n.world_pos.y - n.size.y / 2.0)) > 0.01: return "corridor misses neighbour"
			if dn == "E" and absf(rect.end.x - (n.world_pos.x - n.size.x / 2.0)) > 0.01: return "corridor misses neighbour"
			if dn == "S" and absf(n.world_pos.x - rd.world_pos.x) > 0.01: return "corridor not straight"
			if dn == "E" and absf(n.world_pos.y - rd.world_pos.y) > 0.01: return "corridor not straight"
			rects.append({"r": rect, "tag": "corr", "a": pos, "b": nb})
	for i in range(rects.size()):
		for j in range(i + 1, rects.size()):
			var x = rects[i]
			var y = rects[j]
			if x.tag == "room" and y.tag == "room":
				if x.r.intersects(y.r): return "room/room overlap"
			elif x.tag == "corr" and y.tag == "corr":
				if x.r.intersects(y.r): return "corridor/corridor overlap"
			else:
				var rm = x if x.tag == "room" else y
				var co = y if x.tag == "room" else x
				if rm.a != co.a and rm.a != co.b and rm.r.intersects(co.r): return "corridor/room overlap"
	return ""

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
	var geom_fail: int = 0
	var exit_fail: int = 0
	var size_fail: int = 0
	var total_rooms: int = 0
	var size_set: Dictionary = {}
	var block_set: Dictionary = {}   # distinct sizes in the current block of 100 rooms
	var block_count: int = 0
	var min_block_distinct: int = 999
	var blocks_checked: int = 0
	var min_exit_depth: int = 999
	var exit_depth_sum: int = 0

	var dir_map = {
		"N": Vector2i(0, -1),
		"S": Vector2i(0, 1),
		"E": Vector2i(1, 0),
		"W": Vector2i(-1, 0)
	}

	var passes: Array = ROOM_COUNTS.duplicate()
	passes.append(BSP_PASS)
	for n_rooms in passes:
		var passed_here: int = 0
		var is_bsp: bool = n_rooms == BSP_PASS
		dungeon_gen.layout_mode = DungeonGenerator.LAYOUT_BSP if is_bsp else DungeonGenerator.LAYOUT_FORGE
		for s in range(1, TOTAL_SEEDS + 1):
			total += 1
			seed(s)
			var rooms: Dictionary = dungeon_gen.generate_dungeon(diff_mgr, 6 if is_bsp else n_rooms)
			var start_pos: Vector2i = dungeon_gen.start_room_pos
			var exit_pos: Vector2i = dungeon_gen.exit_room_pos
			var count_ok: bool = (rooms.size() >= dungeon_gen.bsp_min_rooms and rooms.size() <= dungeon_gen.bsp_max_rooms) \
				if is_bsp else rooms.size() == n_rooms

			if not count_ok or not rooms.has(start_pos) or not rooms.has(exit_pos) or start_pos == exit_pos:
				failures.append("rooms=%d seed=%d (layout)" % [n_rooms, s])
				continue

			# --- map-gen checks -------------------------------------------------------------
			var depths: Dictionary = DungeonGenerator.bfs_depths(rooms, start_pos)
			var max_depth: int = 0
			for dv in depths.values():
				max_depth = maxi(max_depth, dv)
			var exit_depth: int = depths.get(exit_pos, -1)
			min_exit_depth = mini(min_exit_depth, exit_depth)
			exit_depth_sum += exit_depth
			if exit_depth != max_depth or (rooms.size() >= 3 and exit_depth < 2):
				exit_fail += 1
				failures.append("rooms=%d seed=%d (exit depth %d, max %d)" % [n_rooms, s, exit_depth, max_depth])
			var geom_err: String = _geometry_ok(rooms)
			if geom_err != "":
				geom_fail += 1
				failures.append("rooms=%d seed=%d (%s)" % [n_rooms, s, geom_err])
			for rp in rooms.keys():
				var sz: Vector2 = rooms[rp].size
				total_rooms += 1
				size_set[sz] = true
				block_set[sz] = true
				block_count += 1
				if block_count == 100:
					min_block_distinct = mini(min_block_distinct, block_set.size())
					blocks_checked += 1
					block_set.clear()
					block_count = 0
				if sz.x < MIN_SIZE.x or sz.x > MAX_SIZE.x or sz.y < MIN_SIZE.y or sz.y > MAX_SIZE.y or int(sz.x) % 32 != 0 or int(sz.y) % 32 != 0:
					size_fail += 1
					failures.append("rooms=%d seed=%d (size %s out of bounds)" % [n_rooms, s, str(sz)])

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
		print("[FORGE CI] rooms=%s: %d / %d solvable" % ["bsp" if is_bsp else str(n_rooms), passed_here, TOTAL_SEEDS])
	dungeon_gen.layout_mode = DungeonGenerator.LAYOUT_FORGE

	print("--------------------------------------------------")
	print("[FORGE CI] Solvability Results: %d / %d Solvable" % [passed_count, total])
	print("--------------------------------------------------")

	print("[FORGE CI] Map-gen: exit-depth failures=%d, overlap failures=%d, size-bound failures=%d" % [exit_fail, geom_fail, size_fail])
	print("[FORGE CI] Map-gen: %d rooms, %d distinct sizes overall; per block of 100 rooms (%d blocks) min distinct = %d (need >= 6)" % [total_rooms, size_set.size(), blocks_checked, min_block_distinct])
	print("[FORGE CI] Map-gen: min exit depth=%d, mean exit depth=%.2f" % [min_exit_depth, float(exit_depth_sum) / float(total)])
	if min_block_distinct < 6:
		failures.append("size diversity too low (min %d distinct per 100 rooms)" % min_block_distinct)

	if passed_count == total and failures.is_empty():
		print("[FORGE CI] PASS: every room reachable in all %d layouts." % total)
		quit(0)
	else:
		printerr("[FORGE CI] FAIL: %d layouts failed: %s" % [failures.size(), str(failures.slice(0, 20))])
		quit(1)
