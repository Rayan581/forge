class_name Room
extends Node2D

signal room_entered(room_node: Room)
signal room_cleared(room_node: Room)
signal enemy_killed
signal enemy_damaged_in_room(damage: float, pos: Vector2)
signal player_hit_hazard
signal player_collected_pickup(type: String)
signal dungeon_escaped

@export var room_width: float = 880.0
@export var room_height: float = 520.0
var door_width: float = 96.0

var enemy_scene = preload("res://scenes/Enemy.tscn")
var hazard_scene = preload("res://scenes/Hazard.tscn")
var pickup_scene = preload("res://scenes/Pickup.tscn")

# Preloaded Dungeon Textures
var tex_floor_stone: Texture2D = preload("res://assets/sprites/tile_floor_stone.png")
var tex_floor_start: Texture2D = preload("res://assets/sprites/tile_floor_start.png")
var tex_floor_hazard: Texture2D = preload("res://assets/sprites/tile_floor_hazard.png")
var tex_floor_treasure: Texture2D = preload("res://assets/sprites/tile_floor_treasure.png")
var tex_floor_exit: Texture2D = preload("res://assets/sprites/tile_floor_exit.png")
var tex_wall_top: Texture2D = preload("res://assets/sprites/tile_wall_top.png")

var room_data: DungeonGenerator.RoomData = null
var enemies_alive: int = 0
var is_active_room: bool = false

@onready var entities_container: Node2D = $EntitiesContainer
@onready var static_walls: StaticBody2D = $StaticWalls
@onready var room_trigger: Area2D = $RoomTrigger
@onready var exit_portal: Area2D = $ExitPortal
@onready var portal_sprite: Sprite2D = $ExitPortal/PortalSprite

func _ready() -> void:
	room_trigger.body_entered.connect(_on_player_entered_room)
	if exit_portal:
		exit_portal.body_entered.connect(_on_exit_portal_entered)

func _process(delta: float) -> void:
	# Animate Exit Portal vortex spin & pulse if present
	if exit_portal and exit_portal.visible and portal_sprite:
		portal_sprite.rotation += delta * 1.6
		var is_open = (room_data and (room_data.is_cleared or enemies_alive <= 0))
		if is_open:
			var pulse = 1.0 + sin(Time.get_ticks_msec() / 180.0) * 0.08
			portal_sprite.scale = Vector2(pulse, pulse)
			portal_sprite.modulate = Color(1.1, 1.0, 1.2, 1.0)
		else:
			portal_sprite.scale = Vector2(0.85, 0.85)
			portal_sprite.modulate = Color(0.5, 0.35, 0.6, 0.45)

func initialize_room(data: DungeonGenerator.RoomData, p_diff: DifficultyManager) -> void:
	room_data = data
	global_position = data.world_pos
	
	# Clear old entities and walls
	for child in entities_container.get_children():
		child.queue_free()
	for child in static_walls.get_children():
		child.queue_free()
		
	# Build dynamic collision walls with door openings and corridor walls
	build_walls()
	
	# Spawn entities based on room data and difficulty parameters
	spawn_entities(p_diff)
	
	# Configure Exit Portal if Exit Room
	if exit_portal:
		var is_exit = (room_data.room_type == DungeonGenerator.RoomType.EXIT)
		exit_portal.visible = is_exit
		exit_portal.set_deferred("monitoring", is_exit)
		exit_portal.set_deferred("monitorable", is_exit)
		
	queue_redraw()

func build_walls() -> void:
	var w = room_width
	var h = room_height
	var dw = door_width
	var wall_thick = 32.0
	var half_spacing = 60.0 # spacing / 2.0 (corridor length per room side)
	
	# Top Wall
	if room_data.doors["N"]:
		var seg_w = (w - dw) / 2.0
		_create_wall_segment(Vector2(-w/2 + seg_w/2 - wall_thick/2, -h/2), Vector2(seg_w + wall_thick, wall_thick))
		_create_wall_segment(Vector2(w/2 - seg_w/2 + wall_thick/2, -h/2), Vector2(seg_w + wall_thick, wall_thick))
		# North Corridor Walls
		_create_wall_segment(Vector2(-dw/2 - wall_thick/2, -h/2 - half_spacing/2), Vector2(wall_thick, half_spacing + wall_thick))
		_create_wall_segment(Vector2(dw/2 + wall_thick/2, -h/2 - half_spacing/2), Vector2(wall_thick, half_spacing + wall_thick))
	else:
		_create_wall_segment(Vector2(0, -h/2), Vector2(w + wall_thick * 2, wall_thick))
		
	# Bottom Wall
	if room_data.doors["S"]:
		var seg_w = (w - dw) / 2.0
		_create_wall_segment(Vector2(-w/2 + seg_w/2 - wall_thick/2, h/2), Vector2(seg_w + wall_thick, wall_thick))
		_create_wall_segment(Vector2(w/2 - seg_w/2 + wall_thick/2, h/2), Vector2(seg_w + wall_thick, wall_thick))
		# South Corridor Walls
		_create_wall_segment(Vector2(-dw/2 - wall_thick/2, h/2 + half_spacing/2), Vector2(wall_thick, half_spacing + wall_thick))
		_create_wall_segment(Vector2(dw/2 + wall_thick/2, h/2 + half_spacing/2), Vector2(wall_thick, half_spacing + wall_thick))
	else:
		_create_wall_segment(Vector2(0, h/2), Vector2(w + wall_thick * 2, wall_thick))
		
	# Left Wall
	if room_data.doors["W"]:
		var seg_h = (h - dw) / 2.0
		_create_wall_segment(Vector2(-w/2, -h/2 + seg_h/2 - wall_thick/2), Vector2(wall_thick, seg_h + wall_thick))
		_create_wall_segment(Vector2(-w/2, h/2 - seg_h/2 + wall_thick/2), Vector2(wall_thick, seg_h + wall_thick))
		# West Corridor Walls
		_create_wall_segment(Vector2(-w/2 - half_spacing/2, -dw/2 - wall_thick/2), Vector2(half_spacing + wall_thick, wall_thick))
		_create_wall_segment(Vector2(-w/2 - half_spacing/2, dw/2 + wall_thick/2), Vector2(half_spacing + wall_thick, wall_thick))
	else:
		_create_wall_segment(Vector2(-w/2, 0), Vector2(wall_thick, h + wall_thick * 2))
		
	# Right Wall
	if room_data.doors["E"]:
		var seg_h = (h - dw) / 2.0
		_create_wall_segment(Vector2(w/2, -h/2 + seg_h/2 - wall_thick/2), Vector2(wall_thick, seg_h + wall_thick))
		_create_wall_segment(Vector2(w/2, h/2 - seg_h/2 + wall_thick/2), Vector2(wall_thick, seg_h + wall_thick))
		# East Corridor Walls
		_create_wall_segment(Vector2(w/2 + half_spacing/2, -dw/2 - wall_thick/2), Vector2(half_spacing + wall_thick, wall_thick))
		_create_wall_segment(Vector2(w/2 + half_spacing/2, dw/2 + wall_thick/2), Vector2(half_spacing + wall_thick, wall_thick))
	else:
		_create_wall_segment(Vector2(w/2, 0), Vector2(wall_thick, h + wall_thick * 2))

func _create_wall_segment(pos: Vector2, size: Vector2) -> void:
	var col = CollisionShape2D.new()
	var rect_shape = RectangleShape2D.new()
	rect_shape.size = size
	col.shape = rect_shape
	col.position = pos
	static_walls.add_child(col)

func spawn_entities(p_diff: DifficultyManager) -> void:
	enemies_alive = 0
	
	# Spawn Hazards
	for i in range(room_data.hazards_count):
		var h = hazard_scene.instantiate()
		var rand_x = randf_range(-room_width/2 + 80, room_width/2 - 80)
		var rand_y = randf_range(-room_height/2 + 80, room_height/2 - 80)
		h.position = Vector2(rand_x, rand_y)
		h.player_hit_hazard.connect(func(): emit_signal("player_hit_hazard"))
		entities_container.add_child(h)
		
	# Spawn Pickups
	for i in range(room_data.pickups_count):
		var pk = pickup_scene.instantiate()
		var rand_x = randf_range(-room_width/2 + 70, room_width/2 - 70)
		var rand_y = randf_range(-room_height/2 + 70, room_height/2 - 70)
		pk.position = Vector2(rand_x, rand_y)
		pk.pickup_collected.connect(func(type): emit_signal("player_collected_pickup", type))
		entities_container.add_child(pk)
		
	# Spawn Enemies with vector E parameters
	for i in range(room_data.enemies_count):
		var e = enemy_scene.instantiate()
		var rand_x = randf_range(-room_width/2 + 90, room_width/2 - 90)
		var rand_y = randf_range(-room_height/2 + 80, room_height/2 - 80)
		e.position = Vector2(rand_x, rand_y)
		e.configure_parameters(p_diff.enemy_health, p_diff.enemy_damage, p_diff.enemy_speed, p_diff.enemy_aggro)
		e.enemy_damaged.connect(func(dmg, pos): emit_signal("enemy_damaged_in_room", dmg, pos))
		e.enemy_defeated.connect(_on_enemy_defeated)
		entities_container.add_child(e)
		enemies_alive += 1

func _on_enemy_defeated(_enemy_node: Enemy) -> void:
	enemies_alive -= 1
	emit_signal("enemy_killed")
	if enemies_alive <= 0 and not room_data.is_cleared:
		room_data.is_cleared = true
		emit_signal("room_cleared", self)
		queue_redraw()

## Instantly defeats every living enemy currently in this room.
func kill_all_enemies() -> void:
	for child in entities_container.get_children():
		if child is Enemy:
			child.kill()

func _on_player_entered_room(body: Node2D) -> void:
	if body is Player:
		room_data.is_visited = true
		emit_signal("room_entered", self)

func _on_exit_portal_entered(body: Node2D) -> void:
	if body is Player and room_data and room_data.room_type == DungeonGenerator.RoomType.EXIT:
		if room_data.is_cleared or enemies_alive <= 0:
			emit_signal("dungeon_escaped")

func _draw() -> void:
	if room_data == null:
		return
		
	var w = room_width
	var h = room_height
	var rect = Rect2(-w/2, -h/2, w, h)
	var dw = door_width
	var wall_thick = 32.0
	var half_spacing = 60.0
	
	# 1. Select appropriate themed floor tile
	var floor_tex = tex_floor_stone
	if room_data.room_type == DungeonGenerator.RoomType.START:
		floor_tex = tex_floor_start
	elif room_data.room_type == DungeonGenerator.RoomType.HAZARD:
		floor_tex = tex_floor_hazard
	elif room_data.room_type == DungeonGenerator.RoomType.TREASURE:
		floor_tex = tex_floor_treasure
	elif room_data.room_type == DungeonGenerator.RoomType.EXIT:
		floor_tex = tex_floor_exit
		
	# Draw tiled stone flagstone floor
	draw_texture_rect(floor_tex, rect, true)
	
	# Layered dungeon atmosphere shadows:
	# 1. Outer deep border shadow (inner wall drop shadow)
	draw_rect(rect, Color(0, 0, 0, 0.45), false, 18.0)
	# 2. Soft perimeter vignette
	draw_rect(Rect2(-w/2 + 18, -h/2 + 18, w - 36, h - 36), Color(0, 0, 0, 0.2), false, 24.0)
	# 3. Corner architectural stone reinforcement brackets
	var bracket_c = Color(0.2, 0.25, 0.35, 0.6)
	var b_sz = 36.0
	draw_rect(Rect2(-w/2, -h/2, b_sz, 6.0), bracket_c)
	draw_rect(Rect2(-w/2, -h/2, 6.0, b_sz), bracket_c)
	draw_rect(Rect2(w/2 - b_sz, -h/2, b_sz, 6.0), bracket_c)
	draw_rect(Rect2(w/2 - 6.0, -h/2, 6.0, b_sz), bracket_c)
	draw_rect(Rect2(-w/2, h/2 - 6.0, b_sz, 6.0), bracket_c)
	draw_rect(Rect2(-w/2, h/2 - b_sz, 6.0, b_sz), bracket_c)
	draw_rect(Rect2(w/2 - b_sz, h/2 - 6.0, b_sz, 6.0), bracket_c)
	draw_rect(Rect2(w/2 - 6.0, h/2 - b_sz, 6.0, b_sz), bracket_c)
	
	# 2. Draw Corridor Floors with stone tiling
	if room_data.doors["N"]:
		draw_texture_rect(tex_floor_stone, Rect2(-dw/2, -h/2 - half_spacing, dw, half_spacing), true)
		draw_rect(Rect2(-dw/2, -h/2 - half_spacing, dw, half_spacing), Color(0, 0, 0, 0.25), false, 6.0)
	if room_data.doors["S"]:
		draw_texture_rect(tex_floor_stone, Rect2(-dw/2, h/2, dw, half_spacing), true)
		draw_rect(Rect2(-dw/2, h/2, dw, half_spacing), Color(0, 0, 0, 0.25), false, 6.0)
	if room_data.doors["E"]:
		draw_texture_rect(tex_floor_stone, Rect2(w/2, -dw/2, half_spacing, dw), true)
		draw_rect(Rect2(w/2, -dw/2, half_spacing, dw), Color(0, 0, 0, 0.25), false, 6.0)
	if room_data.doors["W"]:
		draw_texture_rect(tex_floor_stone, Rect2(-w/2 - half_spacing, -dw/2, half_spacing, dw), true)
		draw_rect(Rect2(-w/2 - half_spacing, -dw/2, half_spacing, dw), Color(0, 0, 0, 0.25), false, 6.0)
		
	# 3. Draw Solid Walls with masonry brick texture & beveled coping
	var seg_w = (w - dw) / 2.0
	var seg_h = (h - dw) / 2.0
	
	var draw_wall_box = func(pos: Vector2, size: Vector2):
		var r = Rect2(pos.x - size.x/2.0, pos.y - size.y/2.0, size.x, size.y)
		# Tiled masonry texture
		draw_texture_rect(tex_wall_top, r, true)
		# Subtle stone border highlight & drop shadow line
		draw_rect(r, Color(0.38, 0.44, 0.56, 0.8), false, 1.5)
		# Drop shadow on bottom edge
		draw_line(Vector2(r.position.x, r.end.y), Vector2(r.end.x, r.end.y), Color(0.05, 0.06, 0.09, 0.95), 2.5)
	
	# Top Wall
	if room_data.doors["N"]:
		draw_wall_box.call(Vector2(-w/2 + seg_w/2 - wall_thick/2, -h/2), Vector2(seg_w + wall_thick, wall_thick))
		draw_wall_box.call(Vector2(w/2 - seg_w/2 + wall_thick/2, -h/2), Vector2(seg_w + wall_thick, wall_thick))
		# North Corridor Walls
		draw_wall_box.call(Vector2(-dw/2 - wall_thick/2, -h/2 - half_spacing/2), Vector2(wall_thick, half_spacing + wall_thick))
		draw_wall_box.call(Vector2(dw/2 + wall_thick/2, -h/2 - half_spacing/2), Vector2(wall_thick, half_spacing + wall_thick))
	else:
		draw_wall_box.call(Vector2(0, -h/2), Vector2(w + wall_thick * 2, wall_thick))
		
	# Bottom Wall
	if room_data.doors["S"]:
		draw_wall_box.call(Vector2(-w/2 + seg_w/2 - wall_thick/2, h/2), Vector2(seg_w + wall_thick, wall_thick))
		draw_wall_box.call(Vector2(w/2 - seg_w/2 + wall_thick/2, h/2), Vector2(seg_w + wall_thick, wall_thick))
		# South Corridor Walls
		draw_wall_box.call(Vector2(-dw/2 - wall_thick/2, h/2 + half_spacing/2), Vector2(wall_thick, half_spacing + wall_thick))
		draw_wall_box.call(Vector2(dw/2 + wall_thick/2, h/2 + half_spacing/2), Vector2(wall_thick, half_spacing + wall_thick))
	else:
		draw_wall_box.call(Vector2(0, h/2), Vector2(w + wall_thick * 2, wall_thick))
		
	# Left Wall
	if room_data.doors["W"]:
		draw_wall_box.call(Vector2(-w/2, -h/2 + seg_h/2 - wall_thick/2), Vector2(wall_thick, seg_h + wall_thick))
		draw_wall_box.call(Vector2(-w/2, h/2 - seg_h/2 + wall_thick/2), Vector2(wall_thick, seg_h + wall_thick))
		# West Corridor Walls
		draw_wall_box.call(Vector2(-w/2 - half_spacing/2, -dw/2 - wall_thick/2), Vector2(half_spacing + wall_thick, wall_thick))
		draw_wall_box.call(Vector2(-w/2 - half_spacing/2, dw/2 + wall_thick/2), Vector2(half_spacing + wall_thick, wall_thick))
	else:
		draw_wall_box.call(Vector2(-w/2, 0), Vector2(wall_thick, h + wall_thick * 2))
		
	# Right Wall
	if room_data.doors["E"]:
		draw_wall_box.call(Vector2(w/2, -h/2 + seg_h/2 - wall_thick/2), Vector2(wall_thick, seg_h + wall_thick))
		draw_wall_box.call(Vector2(w/2, h/2 - seg_h/2 + wall_thick/2), Vector2(wall_thick, seg_h + wall_thick))
		# East Corridor Walls
		draw_wall_box.call(Vector2(w/2 + half_spacing/2, -dw/2 - wall_thick/2), Vector2(half_spacing + wall_thick, wall_thick))
		draw_wall_box.call(Vector2(w/2 + half_spacing/2, dw/2 + wall_thick/2), Vector2(half_spacing + wall_thick, wall_thick))
	else:
		draw_wall_box.call(Vector2(w/2, 0), Vector2(wall_thick, h + wall_thick * 2))
