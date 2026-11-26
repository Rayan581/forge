class_name MiniMap
extends Control

var rooms_data: Dictionary = {}
var current_player_grid_pos: Vector2i = Vector2i.ZERO
var cell_size: float = 24.0
var cell_spacing: float = 6.0
var reveal_exit: bool = false # set true by DefenseOverlay's Auto-Kill testing toggle

func set_dungeon_data(p_rooms: Dictionary, p_start: Vector2i) -> void:
	rooms_data = p_rooms
	current_player_grid_pos = p_start
	queue_redraw()

func set_reveal_exit(enabled: bool) -> void:
	reveal_exit = enabled
	queue_redraw()

func update_player_pos(p_pos: Vector2i) -> void:
	current_player_grid_pos = p_pos
	if rooms_data.has(p_pos):
		rooms_data[p_pos].is_visited = true
	queue_redraw()

## Maps world space (room world_pos / size) into the panel, so rooms keep their relative sizes.
func _draw() -> void:
	if rooms_data.is_empty():
		return
	var pad = 8.0
	var lo = Vector2(INF, INF)
	var hi = Vector2(-INF, -INF)
	for pos in rooms_data.keys():
		var r0 = rooms_data[pos]
		lo = lo.min(r0.world_pos - r0.size / 2.0)
		hi = hi.max(r0.world_pos + r0.size / 2.0)
	var extent = hi - lo
	var scl = minf((size.x - 2.0 * pad) / extent.x, (size.y - 2.0 * pad) / extent.y)
	var origin = (size - extent * scl) / 2.0 - lo * scl
	
	# Draw Background Panel
	draw_rect(Rect2(0, 0, size.x, size.y), Color(0.08, 0.09, 0.13, 0.85))
	draw_rect(Rect2(0, 0, size.x, size.y), Color(0.25, 0.35, 0.5, 0.7), false, 1.5)
	
	# Draw Corridors between connected rooms (door to door, centre lines)
	for pos in rooms_data.keys():
		var rc = rooms_data[pos]
		var c0 = origin + rc.world_pos * scl
		if rc.doors["E"] and rooms_data.has(pos + Vector2i(1, 0)):
			draw_line(c0, origin + rooms_data[pos + Vector2i(1, 0)].world_pos * scl, Color(0.4, 0.45, 0.55), 2.0)
		if rc.doors["S"] and rooms_data.has(pos + Vector2i(0, 1)):
			draw_line(c0, origin + rooms_data[pos + Vector2i(0, 1)].world_pos * scl, Color(0.4, 0.45, 0.55), 2.0)
			
	# Draw Rooms
	for pos in rooms_data.keys():
		var r = rooms_data[pos]
		var rsz = Vector2(maxf(r.size.x * scl, 4.0), maxf(r.size.y * scl, 4.0))
		var rc0 = origin + r.world_pos * scl
		var rx = rc0.x - rsz.x / 2.0
		var ry = rc0.y - rsz.y / 2.0
		var r_rect = Rect2(rx, ry, rsz.x, rsz.y)
		var min_dim = minf(rsz.x, rsz.y)
		
		# When Auto-Kill testing mode is on, reveal the exit room (the one with
		# the door/portal) even before the player has ever set foot in it.
		var is_exit_revealed = reveal_exit and r.room_type == DungeonGenerator.RoomType.EXIT
		
		var room_color = Color(0.2, 0.22, 0.28) # Unvisited
		if r.is_visited or is_exit_revealed:
			if r.room_type == DungeonGenerator.RoomType.START:
				room_color = Color(0.2, 0.55, 0.85)
			elif r.room_type == DungeonGenerator.RoomType.EXIT:
				room_color = Color(0.75, 0.3, 0.85)
			elif r.room_type == DungeonGenerator.RoomType.HAZARD:
				room_color = Color(0.85, 0.3, 0.25)
			elif r.room_type == DungeonGenerator.RoomType.TREASURE:
				room_color = Color(0.95, 0.8, 0.25)
			elif r.is_cleared:
				room_color = Color(0.25, 0.75, 0.45)
			else:
				room_color = Color(0.65, 0.35, 0.35)
				
		draw_rect(r_rect, room_color)
		draw_rect(r_rect, Color(0.1, 0.12, 0.16), false, 1.0)
		
		# Ring marker so a revealed-but-unvisited exit room reads clearly as
		# "the room with the door", distinct from one you've already explored.
		if is_exit_revealed and not r.is_visited:
			draw_arc(rc0, min_dim * 0.32, 0, TAU, 12, Color(1, 1, 1, 0.9), 1.5)
		
		# Current player marker
		if pos == current_player_grid_pos:
			draw_rect(r_rect.grow(2.0), Color(1, 1, 1), false, 2.0)
			draw_circle(rc0, 3.5, Color(1, 1, 1))
