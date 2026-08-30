class_name Player
extends CharacterBody2D

signal health_changed(current_hp: float, max_hp: float)
signal player_died

@export var max_health: float = 100.0
var current_health: float = 100.0
@export var move_speed: float = 220.0
@export var attack_damage: float = 35.0
@export var attack_cooldown: float = 0.35

var can_attack: bool = true
var is_invulnerable: bool = false
var invulnerable_timer: float = 0.0
var facing_direction: Vector2 = Vector2.DOWN
var is_swinging: bool = false
var swing_timer: float = 0.0
var swing_angle: float = 0.0

@onready var collision_shape: CollisionShape2D = $CollisionShape2D

func _ready() -> void:
	current_health = max_health
	emit_signal("health_changed", current_health, max_health)

func _physics_process(delta: float) -> void:
	if current_health <= 0:
		return
		
	# Input Handling
	var input_vector = Vector2.ZERO
	input_vector.x = Input.get_axis("move_left", "move_right")
	input_vector.y = Input.get_axis("move_up", "move_down")
	
	if input_vector != Vector2.ZERO:
		input_vector = input_vector.normalized()
		facing_direction = input_vector
		velocity = input_vector * move_speed
	else:
		velocity = velocity.move_toward(Vector2.ZERO, move_speed * 8.0 * delta)
		
	move_and_slide()
	
	# Attack Handling
	if Input.is_action_just_pressed("attack") and can_attack:
		perform_attack()
		
	# Timers
	if is_invulnerable:
		invulnerable_timer -= delta
		if invulnerable_timer <= 0.0:
			is_invulnerable = false
			
	if is_swinging:
		swing_timer -= delta
		if swing_timer <= 0.0:
			is_swinging = false
			
	queue_redraw()

func perform_attack() -> void:
	can_attack = false
	is_swinging = true
	swing_timer = 0.18
	
	# Attack target point based on mouse or facing direction
	var mouse_pos = get_global_mouse_position()
	var attack_dir = (mouse_pos - global_position).normalized()
	if attack_dir == Vector2.ZERO:
		attack_dir = facing_direction
	swing_angle = attack_dir.angle()
	
	# Area query for enemies
	var space_state = get_world_2d().direct_space_state
	var query = PhysicsShapeQueryParameters2D.new()
	var circle = CircleShape2D.new()
	circle.radius = 58.0
	query.shape = circle
	query.transform = Transform2D(0.0, global_position + attack_dir * 36.0)
	query.collide_with_areas = false
	query.collide_with_bodies = true
	
	var results = space_state.intersect_shape(query, 16)
	for hit in results:
		var body = hit.collider
		if body is Enemy and body != self:
			body.take_damage(attack_damage, attack_dir)
			
	# Cooldown timer
	await get_tree().create_timer(attack_cooldown).timeout
	can_attack = true

func take_damage(amount: float, from_dir: Vector2 = Vector2.ZERO) -> void:
	if is_invulnerable or current_health <= 0:
		return
		
	current_health = maxf(0.0, current_health - amount)
	is_invulnerable = true
	invulnerable_timer = 0.6
	emit_signal("health_changed", current_health, max_health)
	
	# Knockback
	if from_dir != Vector2.ZERO:
		velocity = from_dir * 280.0
		
	if current_health <= 0:
		emit_signal("player_died")

func heal(amount: float) -> void:
	current_health = minf(max_health, current_health + amount)
	emit_signal("health_changed", current_health, max_health)

func reset(start_pos: Vector2) -> void:
	global_position = start_pos
	current_health = max_health
	is_invulnerable = false
	is_swinging = false
	can_attack = true
	emit_signal("health_changed", current_health, max_health)

func _draw() -> void:
	# Draw Player Character (Knight / Adventurer)
	var body_color = Color(0.18, 0.52, 0.88)
	if is_invulnerable and fmod(Time.get_ticks_msec() / 100.0, 2.0) > 1.0:
		body_color = Color(0.9, 0.9, 0.9, 0.6) # Flash on hurt
		
	# Shadow
	draw_circle(Vector2(0, 10), 16.0, Color(0, 0, 0, 0.25))
	# Main body
	draw_circle(Vector2.ZERO, 16.0, body_color)
	draw_circle(Vector2.ZERO, 16.0, Color(0.1, 0.25, 0.5), false, 2.5) # Outline
	# Helm / Visor
	var eye_offset = facing_direction * 7.0
	draw_circle(eye_offset, 5.5, Color(0.95, 0.85, 0.3))
	draw_circle(eye_offset, 3.0, Color(0.1, 0.1, 0.15))
	
	# Sword Attack Arc Visual
	if is_swinging:
		var arc_center = Vector2.ZERO
		var arc_radius = 48.0
		var start_a = swing_angle - PI/3.0
		var end_a = swing_angle + PI/3.0
		draw_arc(arc_center, arc_radius, start_a, end_a, 16, Color(1.0, 0.9, 0.4, 0.85), 5.0)
		draw_line(arc_center, arc_center + Vector2.from_angle(swing_angle) * (arc_radius + 6), Color(1.0, 1.0, 0.9), 3.0)
