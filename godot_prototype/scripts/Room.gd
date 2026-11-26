class_name Room
extends Node2D

signal room_entered(room_node: Room)
signal room_cleared(room_node: Room)
signal enemy_killed
signal enemy_damaged_in_room(damage: float, pos: Vector2)
signal player_hit_hazard
signal player_collected_pickup(type: String)
signal dungeon_escaped

@export var room_width: float = 880.0 # overwritten from room_data.size in initialize_room()
@export var room_height: float = 520.0
var door_width: float = 96.0

var enemy_scene = preload("res://scenes/Enemy.tscn")
var hazard_scene = preload("res://scenes/Hazard.tscn")
var pickup_scene = preload("res://scenes/Pickup.tscn")

# Dungeon tileset (16 px tiles drawn at 2x = 32 px world tiles). Sheet coordinates (col,row):
#   floors  : plain (8,1) (3,2) (9,7); cracked/variant (6..9,0..2) (0..3,6..7)
#   shadowed: TL (1,1) T (2,1)(3,1) TR (4,1) L (1,2) R (4,2) BL (1,3) B (2,3)(3,3) BR (4,3)
#   walls   : top face (1..4,0), bottom (1..4,4), left (0,1..3), right (5,1..3),
#             corners TL (0,0) TR (5,0) BL (0,4) BR (5,4)
var tex_tiles: Texture2D = preload("res://assets/tiles/Dungeon_Tileset.png")
const TILE: float = 32.0
const SRC: float = 16.0
const PLAIN_FLOORS: Array = [Vector2i(8, 1), Vector2i(3, 2), Vector2i(9, 7)]
const VARIANT_FLOORS: Array = [
	Vector2i(6, 0), Vector2i(7, 0), Vector2i(8, 0), Vector2i(9, 0), Vector2i(6, 1), Vector2i(7, 1),
	Vector2i(9, 1), Vector2i(6, 2), Vector2i(7, 2), Vector2i(8, 2), Vector2i(9, 2),
	Vector2i(0, 6), Vector2i(1, 6), Vector2i(2, 6), Vector2i(3, 6), Vector2i(0, 7), Vector2i(1, 7), Vector2i(2, 7), Vector2i(3, 7)
]
const TORCH_PATH: String = "res://assets/tiles/torch/torch_%d.png"
static var _torch_frames: SpriteFrames = null

var room_data: DungeonGenerator.RoomData = null
var enemies_alive: int = 0
var is_active_room: bool = false
## Set by Main when the room is built; per-archetype kill counts go here.
var telemetry_logger: Object = null

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
	# Per-room size first: walls, entities and the trigger all depend on it (CONTRACT section 4).
	room_width = data.size.x
	room_height = data.size.y
	var trig_shape = RectangleShape2D.new() # new resource: the scene's sub-resource is shared
	trig_shape.size = Vector2(room_width - 60.0, room_height - 60.0)
	room_trigger.get_node("CollisionShape2D").shape = trig_shape
	
	# Clear old entities and walls
	for child in entities_container.get_children():
		child.queue_free()
	for child in static_walls.get_children():
		child.queue_free()
		
	# Build dynamic collision walls with door openings and corridor walls
	build_walls()
	
	# Spawn entities based on room data and difficulty parameters
	spawn_entities(p_diff)
	
	_build_decor()

	# Configure Exit Portal if Exit Room
	if exit_portal:
		var is_exit = (room_data.room_type == DungeonGenerator.RoomType.EXIT)
		exit_portal.visible = is_exit
		exit_portal.set_deferred("monitoring", is_exit)
		exit_portal.set_deferred("monitorable", is_exit)
		
	queue_redraw()

## Wall rings sit OUTSIDE the interior rectangle (one 32 px tile thick); doors are 96 px gaps
## centred on each side. Corridors are owned by the north/west room of each pair (doors S / E):
## that room builds the corridor side walls for the full per-door length.
func build_walls() -> void:
	var w = room_width
	var h = room_height
	var dw = door_width
	var t = DungeonGenerator.WALL_THICK
	var hd = dw / 2.0
	
	# Top / bottom rings (include the corner tiles, so they span the full width + 2 walls)
	for side in ["N", "S"]:
		var sy = -h/2 - t/2 if side == "N" else h/2 + t/2
		if room_data.doors[side]:
			var seg_w = (w + 2.0 * t) / 2.0 - hd
			_create_wall_segment(Vector2(-hd - seg_w/2, sy), Vector2(seg_w, t))
			_create_wall_segment(Vector2(hd + seg_w/2, sy), Vector2(seg_w, t))
		else:
			_create_wall_segment(Vector2(0, sy), Vector2(w + 2.0 * t, t))
	# Left / right rings
	for side in ["W", "E"]:
		var sx = -w/2 - t/2 if side == "W" else w/2 + t/2
		if room_data.doors[side]:
			var seg_h = h / 2.0 - hd
			_create_wall_segment(Vector2(sx, -hd - seg_h/2), Vector2(t, seg_h))
			_create_wall_segment(Vector2(sx, hd + seg_h/2), Vector2(t, seg_h))
		else:
			_create_wall_segment(Vector2(sx, 0), Vector2(t, h))
	
	# Corridor side walls (owned by the S / E room of each connection)
	if room_data.doors["S"]:
		var l = _corridor_len("S")
		for sgn in [-1.0, 1.0]:
			_create_wall_segment(Vector2(sgn * (hd + t/2), h/2 + l/2), Vector2(t, l))
	if room_data.doors["E"]:
		var l = _corridor_len("E")
		for sgn in [-1.0, 1.0]:
			_create_wall_segment(Vector2(w/2 + l/2, sgn * (hd + t/2)), Vector2(l, t))

func _corridor_len(side: String) -> float:
	return room_data.corridors.get(side, 160.0)

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
		
	# Spawn Enemies with vector E parameters. Each *slot* samples an archetype from the
	# difficulty manager's archetype_mix; a SWARMER slot spawns a pack of 3 bodies (contract 1).
	for i in range(room_data.enemies_count):
		var arch: int = p_diff.sample_archetype(randf())
		var is_apex: bool = (room_data.room_type == DungeonGenerator.RoomType.EXIT and i == 0 \
				and p_diff.enemy_health >= 85.0)
		if is_apex:
			arch = Enemy.Archetype.HEAVY_BRUTE # Floor 5 exit-room champion
		var bodies: int = 3 if arch == Enemy.Archetype.SWARMER else 1
		var centre := Vector2(
			randf_range(-room_width / 2 + 90, room_width / 2 - 90),
			randf_range(-room_height / 2 + 80, room_height / 2 - 80))
		var offsets := [-40.0, 0.0, 40.0]
		for k in range(bodies):
			var e = enemy_scene.instantiate()
			var pos := centre
			if bodies > 1:
				# Loose triangle around the slot centre, kept >= 80 px from the walls
				pos += Vector2.from_angle(TAU * float(k) / 3.0 + randf() * 0.4) * 28.0
				pos.x = clampf(pos.x, -room_width / 2 + 80, room_width / 2 - 80)
				pos.y = clampf(pos.y, -room_height / 2 + 80, room_height / 2 - 80)
			e.position = pos
			e.set_archetype(arch)
			if arch == Enemy.Archetype.SWARMER:
				e.set_swarm_offset_deg(offsets[k])
			e.configure_parameters(p_diff.enemy_health, p_diff.enemy_damage, p_diff.enemy_speed, p_diff.enemy_aggro)
			
			# Floor 5 Apex Mini-boss buff for the lead champion in the Exit room
			if is_apex:
				e.max_health *= 1.7
				e.current_health = e.max_health
				e.scale = Vector2(1.28, 1.28)
				e.attack_damage *= 1.25
			
			e.enemy_damaged.connect(func(dmg, pos2): emit_signal("enemy_damaged_in_room", dmg, pos2))
			e.enemy_defeated.connect(_on_enemy_defeated)
			e.enemy_defeated.connect(_record_archetype_defeat)
			entities_container.add_child(e)
			enemies_alive += 1

## Optional per-archetype telemetry: forwards to Main's telemetry logger when it supports it.
func _record_archetype_defeat(enemy_node: Enemy) -> void:
	var logger = telemetry_logger
	if logger == null:
		# Fallback for rooms built outside Main (tests/tools): look it up on the running scene.
		var tree := get_tree()
		if tree != null and tree.current_scene != null:
			logger = tree.current_scene.get("telemetry_logger")
	if logger != null and logger.has_method("record_enemy_defeated_by_archetype"):
		logger.record_enemy_defeated_by_archetype(int(enemy_node.archetype))

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
		elif child is ProjectileFireball or child is SlamShockwave:
			child.queue_free()

func _on_player_entered_room(body: Node2D) -> void:
	if body is Player:
		room_data.is_visited = true
		emit_signal("room_entered", self)

func _on_exit_portal_entered(body: Node2D) -> void:
	if body is Player and room_data and room_data.room_type == DungeonGenerator.RoomType.EXIT:
		if room_data.is_cleared or enemies_alive <= 0:
			emit_signal("dungeon_escaped")

func _tile(col: int, row: int, pos: Vector2) -> void:
	draw_texture_rect_region(tex_tiles, Rect2(pos, Vector2(TILE, TILE)), Rect2(col * SRC, row * SRC, SRC, SRC))

func _tile_v(c: Vector2i, pos: Vector2) -> void:
	_tile(c.x, c.y, pos)

func _pick_floor(rng: RandomNumberGenerator) -> Vector2i:
	# Mostly plain stone with an occasional cracked/variant tile (seeded, so stable across redraws).
	if rng.randf() < 0.62:
		return PLAIN_FLOORS[rng.randi() % PLAIN_FLOORS.size()]
	return VARIANT_FLOORS[rng.randi() % VARIANT_FLOORS.size()]

func _in_gap(center: float, door_open: bool) -> bool:
	return door_open and absf(center) < door_width / 2.0

func _draw() -> void:
	if room_data == null:
		return
	var rng = RandomNumberGenerator.new()
	rng.seed = room_data.visual_seed
	var w = room_width
	var h = room_height
	var t = DungeonGenerator.WALL_THICK
	var hd = door_width / 2.0
	var nx = int(round(w / TILE))
	var ny = int(round(h / TILE))
	var d = room_data.doors
	
	# 1. Room floor. Cells next to a wall use the shadowed edge tiles (except in door gaps).
	for j in range(ny):
		for i in range(nx):
			var p = Vector2(-w/2 + i * TILE, -h/2 + j * TILE)
			var cx = p.x + TILE/2.0
			var cy = p.y + TILE/2.0
			var top = j == 0 and not _in_gap(cx, d["N"])
			var bottom = j == ny - 1 and not _in_gap(cx, d["S"])
			var left = i == 0 and not _in_gap(cy, d["W"])
			var right = i == nx - 1 and not _in_gap(cy, d["E"])
			var tc: Vector2i
			if top and left: tc = Vector2i(1, 1)
			elif top and right: tc = Vector2i(4, 1)
			elif bottom and left: tc = Vector2i(1, 3)
			elif bottom and right: tc = Vector2i(4, 3)
			elif top: tc = Vector2i(2 + rng.randi() % 2, 1)
			elif bottom: tc = Vector2i(2 + rng.randi() % 2, 3)
			elif left: tc = Vector2i(1, 2)
			elif right: tc = Vector2i(4, 2)
			else: tc = _pick_floor(rng)
			_tile_v(tc, p)
	
	# 2. Corridor floors (S / E rooms own the corridor to their neighbour)
	if d["S"]:
		var l = _corridor_len("S")
		for k in range(int(round(l / TILE))):
			var y = h/2 + k * TILE
			_tile(1, 2, Vector2(-hd, y))
			_tile_v(_pick_floor(rng) if k % 2 == 0 else PLAIN_FLOORS[0], Vector2(-hd + TILE, y))
			_tile(4, 2, Vector2(hd - TILE, y))
	if d["E"]:
		var l = _corridor_len("E")
		for k in range(int(round(l / TILE))):
			var x = w/2 + k * TILE
			_tile(2 + rng.randi() % 2, 1, Vector2(x, -hd))
			_tile_v(_pick_floor(rng) if k % 2 == 0 else PLAIN_FLOORS[0], Vector2(x, -hd + TILE))
			_tile(2 + rng.randi() % 2, 3, Vector2(x, hd - TILE))
	
	# 3. Wall rings: top face row, bottom row, side bands, corner tiles; door gaps stay open.
	for i in range(-1, nx + 1):
		var x = -w/2 + i * TILE
		var cx = x + TILE/2.0
		if not _in_gap(cx, d["N"]):
			_tile(0 if i == -1 else (5 if i == nx else 1 + rng.randi() % 4), 0, Vector2(x, -h/2 - t))
		if not _in_gap(cx, d["S"]):
			_tile(0 if i == -1 else (5 if i == nx else 1 + rng.randi() % 4), 4, Vector2(x, h/2))
	for j in range(ny):
		var y = -h/2 + j * TILE
		var cy = y + TILE/2.0
		if not _in_gap(cy, d["W"]):
			_tile(0, 1 + rng.randi() % 3, Vector2(-w/2 - t, y))
		if not _in_gap(cy, d["E"]):
			_tile(5, 1 + rng.randi() % 3, Vector2(w/2, y))
	
	# 4. Corridor side walls (between the two rooms' rings)
	if d["S"]:
		var n = int(round((_corridor_len("S") - 2.0 * t) / TILE))
		for k in range(n):
			var y = h/2 + t + k * TILE
			_tile(0, 1 + rng.randi() % 3, Vector2(-hd - t, y))
			_tile(5, 1 + rng.randi() % 3, Vector2(hd, y))
	if d["E"]:
		var n = int(round((_corridor_len("E") - 2.0 * t) / TILE))
		for k in range(n):
			var x = w/2 + t + k * TILE
			_tile(1 + rng.randi() % 4, 0, Vector2(x, -hd - t))
			_tile(1 + rng.randi() % 4, 4, Vector2(x, hd))

## Animated wall torches on the north wall (never next to a door gap). Purely cosmetic.
func _build_decor() -> void:
	var old = get_node_or_null("Decor")
	if old:
		old.queue_free()
	var decor = Node2D.new()
	decor.name = "Decor"
	add_child(decor)
	if _torch_frames == null:
		_torch_frames = SpriteFrames.new()
		_torch_frames.add_animation("burn")
		_torch_frames.set_animation_speed("burn", 8.0)
		_torch_frames.set_animation_loop("burn", true)
		for i in range(1, 5):
			_torch_frames.add_frame("burn", load(TORCH_PATH % i))
	var rng = RandomNumberGenerator.new()
	rng.seed = room_data.visual_seed + 17
	var n = clampi(int(room_width / 256.0), 2, 4)
	var span = room_width / float(n)
	for k in range(n):
		var x = round((-room_width/2 + span * (k + 0.5) + rng.randf_range(-24.0, 24.0)) / TILE) * TILE
		if room_data.doors["N"] and absf(x) < door_width / 2.0 + TILE * 1.5:
			continue
		var sp = AnimatedSprite2D.new()
		sp.sprite_frames = _torch_frames
		sp.animation = "burn"
		sp.scale = Vector2(2, 2)
		sp.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		sp.position = Vector2(x, -room_height/2 - DungeonGenerator.WALL_THICK/2.0 - 2.0)
		sp.frame = rng.randi() % 4
		sp.speed_scale = rng.randf_range(0.85, 1.15)
		decor.add_child(sp)
		sp.play("burn")
