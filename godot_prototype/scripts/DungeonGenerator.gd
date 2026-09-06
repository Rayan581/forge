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

var rooms: Dictionary = {} # Vector2i -> RoomData
var start_room_pos: Vector2i = Vector2i.ZERO
var exit_room_pos: Vector2i = Vector2i.ZERO

var room_width: float = 880.0
var room_height: float = 520.0
var corridor_spacing: float = 120.0 # Distance between room borders

## target_room_count now normally comes from p_diff.room_count_target, which the
## PPO policy sets after each level based on how the player performed. Main.gd
## still passes it explicitly so this function stays testable in isolation.
func generate_dungeon(p_diff: DifficultyManager, target_room_count: int = 6) -> Dictionary:
	rooms.clear()
	
	# 1. Generate Room Layout on Grid using Random Walk with Branching
	var current_pos = Vector2i.ZERO
	start_room_pos = current_pos
	
	var start_room = RoomData.new()
	start_room.grid_pos = current_pos
	start_room.room_type = RoomType.START
	start_room.is_visited = true
	start_room.is_cleared = true
	rooms[current_pos] = start_room
	
	var directions = [
		{"dir": Vector2i(0, -1), "name": "N", "opp": "S"},
		{"dir": Vector2i(0, 1), "name": "S", "opp": "N"},
		{"dir": Vector2i(1, 0), "name": "E", "opp": "W"},
		{"dir": Vector2i(-1, 0), "name": "W", "opp": "E"}
	]
	
	var room_queue: Array[Vector2i] = [current_pos]
	
	while rooms.size() < target_room_count and not room_queue.is_empty():
		var pick_idx = randi() % room_queue.size()
		var parent_pos = room_queue[pick_idx]
		
		# Try random direction
		directions.shuffle()
		var placed = false
		for d in directions:
			var neighbor_pos = parent_pos + d.dir
			if not rooms.has(neighbor_pos):
				# Create new room
				var new_room = RoomData.new()
				new_room.grid_pos = neighbor_pos
				rooms[neighbor_pos] = new_room
				
				# Connect doors
				rooms[parent_pos].doors[d.name] = true
				new_room.doors[d.opp] = true
				
				room_queue.append(neighbor_pos)
				placed = true
				break
				
		if not placed:
			room_queue.remove_at(pick_idx)
			
	# 2. Find the room furthest from start to designate as the EXIT chamber
	var furthest_pos = start_room_pos
	var max_dist = 0
	for pos in rooms.keys():
		var dist = abs(pos.x - start_room_pos.x) + abs(pos.y - start_room_pos.y)
		if dist > max_dist:
			max_dist = dist
			furthest_pos = pos
			
	exit_room_pos = furthest_pos
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
	
	# Calculate world positions for each room
	for pos in rooms.keys():
		var r = rooms[pos]
		var wx = float(pos.x) * (room_width + corridor_spacing)
		var wy = float(pos.y) * (room_height + corridor_spacing)
		r.world_pos = Vector2(wx, wy)
		
	return rooms

## Applies the PPO-controlled enemy_count_scale on top of the base random count,
## keeping at least 1 enemy in rooms that were meant to have any.
func _scale_enemies(base_count: int, p_diff: DifficultyManager) -> int:
	if base_count <= 0:
		return 0
	return max(1, int(round(base_count * p_diff.enemy_count_scale)))
