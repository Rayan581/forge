# tests/test_bsp_generator.gd
# BSP non-adaptive baseline ("Baseline A"):
#   1. BSPGenerator + DungeonGenerator (layout_mode = "bsp"): 200 seeds -> every dungeon has 5-9 rooms,
#      is connected (BFS reaches every room and the exit), doors are symmetric, exit != start, exit is
#      at the maximum BFS depth and >= 2, start sits at grid (0, 0), room sizes are on the size ladders,
#      and the same seed gives the same layout.
#   2. The room counts vary (the BSP tree decides them, not the PPO).
#   3. DifficultyManager: generator modes are exclusive, BSP mode has no calibration and keeps the
#      Intermediate preset on every floor (no +8 % growth).
#   4. TelemetryLogger stores generator = "bsp" (phase "static") for BSP floors, "forge" otherwise.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_bsp_generator.gd
extends SceneTree

const SEEDS: int = 200
const JSON_PATH := "user://test_bsp_generator.json"
const INSTALL_PATH := "user://test_bsp_generator_install.txt"
const OFFS := {"N": Vector2i(0, -1), "S": Vector2i(0, 1), "E": Vector2i(1, 0), "W": Vector2i(-1, 0)}
const OPP := {"N": "S", "S": "N", "E": "W", "W": "E"}

var failures: Array[String] = []

func _fail(msg: String) -> void:
	if failures.size() < 40:
		failures.append(msg)

func _signature(rooms: Dictionary, exit_pos: Vector2i) -> String:
	var keys: Array = rooms.keys()
	keys.sort()
	var parts: Array[String] = []
	for k in keys:
		var r = rooms[k]
		parts.append("%s:%s%s%s%s:%s" % [str(k), int(r.doors["N"]), int(r.doors["S"]), int(r.doors["E"]),
			int(r.doors["W"]), str(r.size)])
	return ",".join(parts) + "|exit=" + str(exit_pos)

func _check_layout(gen, s: int) -> Dictionary:
	var rooms: Dictionary = gen.rooms
	var start: Vector2i = gen.start_room_pos
	var exit_pos: Vector2i = gen.exit_room_pos
	var n := rooms.size()
	if n < gen.bsp_min_rooms or n > gen.bsp_max_rooms:
		_fail("seed %d: %d rooms (want %d-%d)" % [s, n, gen.bsp_min_rooms, gen.bsp_max_rooms])
	if start != Vector2i.ZERO or not rooms.has(start):
		_fail("seed %d: start not at (0,0)" % s)
	if exit_pos == start or not rooms.has(exit_pos):
		_fail("seed %d: bad exit %s" % [s, str(exit_pos)])
	if rooms[start].room_type != DungeonGenerator.RoomType.START:
		_fail("seed %d: start room type" % s)
	if rooms.has(exit_pos) and rooms[exit_pos].room_type != DungeonGenerator.RoomType.EXIT:
		_fail("seed %d: exit room type" % s)
	# doors: every open door has a neighbour with the matching door
	for pos in rooms.keys():
		for dn in OFFS.keys():
			if rooms[pos].doors[dn]:
				var nb: Vector2i = pos + OFFS[dn]
				if not rooms.has(nb) or not rooms[nb].doors[OPP[dn]]:
					_fail("seed %d: door %s of %s has no matching door" % [s, dn, str(pos)])
		var sz: Vector2 = rooms[pos].size
		if not (int(sz.x) in DungeonGenerator.WIDTH_STEPS) or not (int(sz.y) in DungeonGenerator.HEIGHT_STEPS):
			_fail("seed %d: size %s not on the size ladder" % [s, str(sz)])
	# connectivity + exit depth
	var depths: Dictionary = DungeonGenerator.bfs_depths(rooms, start)
	if depths.size() != n:
		_fail("seed %d: only %d of %d rooms reachable" % [s, depths.size(), n])
	var max_d := 0
	for d in depths.values():
		max_d = maxi(max_d, d)
	var ed: int = depths.get(exit_pos, -1)
	if ed != max_d or ed < 2:
		_fail("seed %d: exit depth %d (max %d)" % [s, ed, max_d])
	# tree: a connected graph with n rooms and n-1 door pairs
	var door_ends := 0
	for pos in rooms.keys():
		for dn in OFFS.keys():
			if rooms[pos].doors[dn]:
				door_ends += 1
	if door_ends != 2 * (n - 1):
		_fail("seed %d: %d door pairs for %d rooms (want a tree)" % [s, door_ends / 2, n])
	return {"n": n, "sig": _signature(rooms, exit_pos)}

func _init() -> void:
	var gen = load("res://scripts/DungeonGenerator.gd").new()
	var dm = load("res://scripts/DifficultyManager.gd").new()

	# --- 3. modes ------------------------------------------------------------------------------
	dm.set_generator_mode("bsp")
	if not dm.bsp_baseline_mode or dm.static_baseline_mode or dm.generator_mode() != "bsp":
		_fail("set_generator_mode(bsp) flags wrong")
	if dm.is_in_calibration(3):
		_fail("BSP mode must not calibrate")
	if dm.layout_mode() != DungeonGenerator.LAYOUT_BSP:
		_fail("BSP mode layout_mode() != bsp")
	var p = dm.PRESETS[dm.ProfileTier.INTERMEDIATE]
	for floor_num in [1, 5, 12]:
		dm.apply_baseline(floor_num)
		if dm.enemy_health != p.health or dm.enemy_damage != p.damage or dm.enemy_speed != p.speed \
				or dm.enemy_aggro != p.aggro or dm.hazard_density != p.hazard or dm.resource_scarcity != p.scarcity:
			_fail("BSP floor %d is not the Intermediate preset" % floor_num)
	dm.set_generator_mode("static")
	if dm.bsp_baseline_mode or not dm.static_baseline_mode or dm.layout_mode() != DungeonGenerator.LAYOUT_FORGE:
		_fail("set_generator_mode(static) flags wrong")
	dm.set_generator_mode("forge")
	if dm.is_baseline_mode() or not dm.is_in_calibration(3):
		_fail("set_generator_mode(forge) must restore calibration")

	# --- 1 + 2. layouts --------------------------------------------------------------------------
	dm.set_generator_mode("bsp")
	dm.apply_baseline(1)
	gen.layout_mode = DungeonGenerator.LAYOUT_BSP
	var counts: Dictionary = {}
	for s in range(1, SEEDS + 1):
		seed(s)
		gen.generate_dungeon(dm, 6)
		var a := _check_layout(gen, s)
		counts[a.n] = counts.get(a.n, 0) + 1
		seed(s)
		gen.generate_dungeon(dm, 6)
		if _signature(gen.rooms, gen.exit_room_pos) != a.sig:
			_fail("seed %d: not deterministic" % s)
	if counts.size() < 3:
		_fail("room counts do not vary: %s" % str(counts))
	# FORGE mode still ignores the BSP code path
	gen.layout_mode = DungeonGenerator.LAYOUT_FORGE
	seed(7)
	var forge_rooms: Dictionary = gen.generate_dungeon(dm, 7)
	if forge_rooms.size() != 7:
		_fail("forge layout_mode must honour the requested room count")

	# --- 4. telemetry --------------------------------------------------------------------------
	var tl := TelemetryLogger.new()
	tl.backend_preference = "json"
	tl.json_path = JSON_PATH
	tl.install_id_path = INSTALL_PATH
	tl.begin_floor(1, 6)
	tl.record_floor(dm, {"floor_num": 1, "completion_time": 30.0, "player_max_hp": 100.0})
	var row: Dictionary = tl.floor_history[-1]
	if str(row.get("generator", "")) != "bsp" or str(row.get("phase", "")) != "static":
		_fail("BSP floor row: generator=%s phase=%s" % [row.get("generator"), row.get("phase")])
	dm.set_generator_mode("forge")
	dm.apply_calibration_level(2)
	tl.begin_floor(2, 4)
	tl.record_floor(dm, {"floor_num": 2, "completion_time": 30.0, "player_max_hp": 100.0})
	row = tl.floor_history[-1]
	if str(row.get("generator", "")) != "forge":
		_fail("FORGE floor row: generator=%s" % row.get("generator"))
	tl.close()
	for path in [JSON_PATH, INSTALL_PATH]:
		var abs_path: String = ProjectSettings.globalize_path(path)
		if FileAccess.file_exists(abs_path):
			DirAccess.remove_absolute(abs_path)

	if failures.is_empty():
		print("[FORGE TEST] test_bsp_generator: PASS (%d seeds, room counts %s)" % [SEEDS, str(counts)])
		quit(0)
	else:
		for f in failures:
			printerr("[FORGE TEST] FAIL: " + f)
		quit(1)
