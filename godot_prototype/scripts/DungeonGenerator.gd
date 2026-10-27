class_name DungeonGenerator
extends RefCounted

enum RoomType { START, COMBAT, HAZARD, TREASURE, EXIT }

class RoomData:
	var grid_pos: Vector2i
	var world_pos: Vector2
	var room_type: RoomType = RoomType.COMBAT
	var doors: Dictionary = {"N": false, "S": false, "E": false, "W": false}
	var is_cleared: bool = false
	var is_visited: bool = false
	var enemies_count: int = 0
	var hazards_count: int = 0
	var pickups_count: int = 0
	## Interior size in pixels (CONTRACT section 4). Multiples of 32 so the 32 px tiles line up.
	var size: Vector2 = Vector2(880, 520)
	## BFS distance (in doors) from the start room.
	var depth: int = 0
	## Per-door corridor length in px: interior edge of this room to the interior edge of the
	## neighbour behind that door (includes both rooms' 32 px wall rings). Only set for open doors.
	var corridors: Dictionary = {}
	## Seed for purely cosmetic randomness (floor variants, torch placement).
	var visual_seed: int = 0

const WALL_THICK: float = 32.0
const DOOR_WIDTH: float = 96.0
## Room interior sizes are picked from these ladders. Every value is = 32 (mod 64) so the room's
## half-extent is = 16 (mod 32): the 96 px door (half = 48) then lands exactly on the 32 px tile grid
## measured from the room edge, and corridor lengths stay multiples of 32.
const WIDTH_STEPS: Array = [608, 672, 736, 800, 864, 928, 992, 1056, 1120]
const HEIGHT_STEPS: Array = [416, 480, 544, 608, 672]
const MIN_ROOM_SIZE: Vector2 = Vector2(560, 400)
const MAX_ROOM_SIZE: Vector2 = Vector2(1120, 720)
const LAYOUT_ATTEMPTS: int = 24

const DIRS: Array = [
	{"dir": Vector2i(0, -1), "name": "N", "opp": "S"},
	{"dir": Vector2i(0, 1), "name": "S", "opp": "N"},
	{"dir": Vector2i(1, 0), "name": "E", "opp": "W"},
	{"dir": Vector2i(-1, 0), "name": "W", "opp": "E"}
]

var rooms: Dictionary = {} # Vector2i -> RoomData
var start_room_pos: Vector2i = Vector2i.ZERO
var exit_room_pos: Vector2i = Vector2i.ZERO

## Minimum gap between the interior edges of two grid-adjacent rooms (two 32 px wall rings plus
## at least 96 px of open corridor). Real corridor lengths vary per door, see RoomData.corridors.
var corridor_spacing: float = 160.0

## target_room_count now normally comes from p_diff.room_count_target, which the
## PPO policy sets after each level based on how the player performed. Main.gd
## still passes it explicitly so this function stays testable in isolation.
func generate_dungeon(p_diff: DifficultyManager, target_room_count: int = 6) -> Dictionary:
	rooms.clear()
	
	# 1. Generate the room layout (random walk with branching). The layout is retried (bounded,
	#    deterministic under the global seed) until the exit would sit deep in the graph.
	var min_depth: int = 2 if target_room_count >= 3 else (1 if target_room_count == 2 else 0)
	var goal_depth: int = maxi(min_depth, int(ceil(target_room_count * 0.5)))
	var best: Dictionary = {}
	var best_score: int = -1
	for attempt in range(LAYOUT_ATTEMPTS):
		var layout = _random_layout(target_room_count)
		var depths = bfs_depths(layout, Vector2i.ZERO)
		var max_d = 0
		for d in depths.values():
			max_d = maxi(max_d, d)
		var cand = _pick_exit(layout, depths, max_d)
		var hidden = (cand.x != 0 and cand.y != 0)
		var score = max_d * 2 + (1 if hidden else 0)
		if max_d >= min_depth and score > best_score:
			best = layout
			best_score = score
		# Accept early when deep enough and (while we still have attempts) not in line with the start.
		if max_d >= goal_depth and (hidden or attempt >= LAYOUT_ATTEMPTS / 2):
			best = layout
			break
	if best.is_empty():
		best = _chain_layout(target_room_count)
	rooms = best
	start_room_pos = Vector2i.ZERO

	# 2. Exit = a room at the maximum BFS depth (door-graph distance), never the grid-Manhattan one.
	var depth_map = bfs_depths(rooms, start_room_pos)
	var max_depth = 0
	for pos in rooms.keys():
		rooms[pos].depth = depth_map[pos]
		max_depth = maxi(max_depth, depth_map[pos])
	exit_room_pos = _pick_exit(rooms, depth_map, max_depth)
	rooms[exit_room_pos].room_type = RoomType.EXIT
	
	# 3. Assign Room Types & Difficulty Parameters (Vectors E & M)
	var available_keys = []
	for pos in rooms.keys():
		if pos != start_room_pos and pos != exit_room_pos:
			available_keys.append(pos)
	available_keys.shuffle()
	
	# Determine special room ratios based on environmental vector M
	# High hazard density -> More hazard-heavy rooms
	# Low resource scarcity -> More treasure rooms with health pickups
	var num_hazard_rooms = clampi(int(p_diff.hazard_density * float(available_keys.size())), 1, available_keys.size())
	var num_treasure_rooms = clampi(int((1.0 - p_diff.resource_scarcity) * 2.5), 1, 3)
	
	for i in range(available_keys.size()):
		var pos = available_keys[i]
		var r = rooms[pos]
		if i < num_hazard_rooms:
			r.room_type = RoomType.HAZARD
			r.hazards_count = clampi(int(p_diff.hazard_density * 10.0), 3, 10)
			r.enemies_count = _scale_enemies(randi_range(1, 3), p_diff)
		elif i < num_hazard_rooms + num_treasure_rooms:
			r.room_type = RoomType.TREASURE
			r.pickups_count = randi_range(2, 4)
			r.enemies_count = _scale_enemies(randi_range(1, 2), p_diff)
		else:
			r.room_type = RoomType.COMBAT
			r.enemies_count = _scale_enemies(randi_range(2, 5), p_diff)
			r.hazards_count = clampi(int(p_diff.hazard_density * 4.0), 0, 4)
			r.pickups_count = 1 if randf() > p_diff.resource_scarcity else 0
			
	# Configure Exit Room
	rooms[exit_room_pos].enemies_count = _scale_enemies(clampi(int(3 + p_diff.hazard_density * 3.0), 3, 6), p_diff)
	rooms[exit_room_pos].hazards_count = clampi(int(p_diff.hazard_density * 6.0), 1, 6)
	
	# 4. Per-room sizes, then world positions / per-door corridor lengths.
	_assign_sizes(target_room_count)
	_layout_world()
	for pos in rooms.keys():
		rooms[pos].visual_seed = randi()
		
	return rooms

## Applies the PPO-controlled enemy_count_scale on top of the base random count,
## keeping at least 1 enemy in rooms that were meant to have any.
func _scale_enemies(base_count: int, p_diff: DifficultyManager) -> int:
	if base_count <= 0:
		return 0
	return max(1, int(round(base_count * p_diff.enemy_count_scale)))


## --- Layout helpers -------------------------------------------------------------------------

func _new_room(pos: Vector2i) -> RoomData:
	var r = RoomData.new()
	r.grid_pos = pos
	return r

func _make_start() -> Dictionary:
	var layout: Dictionary = {}
	var start = _new_room(Vector2i.ZERO)
	start.room_type = RoomType.START
	start.is_visited = true
	start.is_cleared = true
	layout[Vector2i.ZERO] = start
	return layout

func _connect(layout: Dictionary, parent_pos: Vector2i, d: Dictionary) -> Vector2i:
	var np = parent_pos + d.dir
	layout[np] = _new_room(np)
	layout[parent_pos].doors[d.name] = true
	layout[np].doors[d.opp] = true
	return np

## Random walk with branching. Half of the time the walk extends the most recently added room
## (grows long corridors of rooms); otherwise it branches from any open room.
func _random_layout(count: int) -> Dictionary:
	var layout = _make_start()
	var queue: Array[Vector2i] = [Vector2i.ZERO]
	var dirs = DIRS.duplicate()
	while layout.size() < count and not queue.is_empty():
		var pick_idx = queue.size() - 1 if randf() < 0.5 else randi() % queue.size()
		var parent_pos = queue[pick_idx]
		dirs.shuffle()
		var placed = false
		for d in dirs:
			if not layout.has(parent_pos + d.dir):
				queue.append(_connect(layout, parent_pos, d))
				placed = true
				break
		if not placed:
			queue.remove_at(pick_idx)
	return layout

## Last-resort layout: a straight line of rooms (depth = count - 1).
func _chain_layout(count: int) -> Dictionary:
	var layout = _make_start()
	var pos = Vector2i.ZERO
	for i in range(count - 1):
		pos = _connect(layout, pos, DIRS[2])
	return layout

## BFS over the door graph. Returns Vector2i -> depth (number of doors from `from`).
static func bfs_depths(layout: Dictionary, from: Vector2i) -> Dictionary:
	var depths: Dictionary = {from: 0}
	var queue: Array[Vector2i] = [from]
	var offs = {"N": Vector2i(0, -1), "S": Vector2i(0, 1), "E": Vector2i(1, 0), "W": Vector2i(-1, 0)}
	while not queue.is_empty():
		var cur: Vector2i = queue.pop_front()
		for dn in offs.keys():
			if layout[cur].doors[dn]:
				var nxt: Vector2i = cur + offs[dn]
				if layout.has(nxt) and not depths.has(nxt):
					depths[nxt] = depths[cur] + 1
					queue.append(nxt)
	return depths

## Among rooms at the maximum BFS depth prefer one that is not in line with the start (so it can't
## be seen straight down a chain of doors), then the one farthest away on the grid.
func _pick_exit(layout: Dictionary, depths: Dictionary, max_d: int) -> Vector2i:
	var best_pos = Vector2i.ZERO
	var best_key = -1
	for pos in layout.keys():
		if depths.get(pos, -1) != max_d:
			continue
		var key = abs(pos.x) + abs(pos.y) + (100 if (pos.x != 0 and pos.y != 0) else 0)
		if key > best_key:
			best_key = key
			best_pos = pos
	return best_pos

func _assign_sizes(count: int) -> void:
	# Bigger dungeons use slightly smaller rooms so the world stays traversable.
	var cap_w: int = WIDTH_STEPS.size() - (1 if count >= 8 else 0)
	var cap_h: int = HEIGHT_STEPS.size() - (1 if count >= 8 else 0)
	for pos in rooms.keys():
		var r: RoomData = rooms[pos]
		var bw = 0
		var bh = 0
		match r.room_type:
			RoomType.EXIT:
				bw = 3
				bh = 1
			RoomType.COMBAT:
				bw = 1
			RoomType.TREASURE, RoomType.START:
				bw = -1
		var wi = clampi(randi_range(0, cap_w - 1) + bw, 0, cap_w - 1)
		var hi = clampi(randi_range(0, cap_h - 1) + bh, 0, cap_h - 1)
		r.size = Vector2(WIDTH_STEPS[wi], HEIGHT_STEPS[hi])

## Rooms sit on the centres of a column/row table (each column as wide as its widest room, each
## row as tall as its tallest), so neighbouring doors always line up in a straight corridor while
## the corridor length adapts to both rooms' sizes.
func _layout_world() -> void:
	var col_w: Dictionary = {}
	var row_h: Dictionary = {}
	for pos in rooms.keys():
		col_w[pos.x] = maxf(col_w.get(pos.x, 0.0), rooms[pos].size.x)
		row_h[pos.y] = maxf(row_h.get(pos.y, 0.0), rooms[pos].size.y)
	var cx: Dictionary = {}
	var cy: Dictionary = {}
	var xs = col_w.keys()
	xs.sort()
	var cursor = 0.0
	for x in xs:
		cx[x] = cursor + col_w[x] / 2.0
		cursor += col_w[x] + corridor_spacing
	var ys = row_h.keys()
	ys.sort()
	cursor = 0.0
	for y in ys:
		cy[y] = cursor + row_h[y] / 2.0
		cursor += row_h[y] + corridor_spacing
	var origin = Vector2(cx[0], cy[0]) # start room (grid 0,0) sits at the world origin
	for pos in rooms.keys():
		rooms[pos].world_pos = Vector2(cx[pos.x], cy[pos.y]) - origin
	for pos in rooms.keys():
		var r: RoomData = rooms[pos]
		r.corridors.clear()
		for d in DIRS:
			if r.doors[d.name] and rooms.has(pos + d.dir):
				var nb: RoomData = rooms[pos + d.dir]
				if d.dir.x != 0:
					r.corridors[d.name] = absf(nb.world_pos.x - r.world_pos.x) - (r.size.x + nb.size.x) / 2.0
				else:
					r.corridors[d.name] = absf(nb.world_pos.y - r.world_pos.y) - (r.size.y + nb.size.y) / 2.0
