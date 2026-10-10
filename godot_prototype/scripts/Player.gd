class_name Player
extends CharacterBody2D

signal health_changed(current_hp: float, max_hp: float)
signal player_damaged(amount: float)
signal player_healed(amount: float)
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

# Persistent Knockback Impulse System
var knockback_velocity: Vector2 = Vector2.ZERO
var knockback_decay: float = 1300.0 # Decays ~340px/s impulse smoothly over ~0.26s

@onready var collision_shape: CollisionShape2D = $CollisionShape2D
@onready var sprite: Sprite2D = get_node_or_null("Sprite2D")

func _ready() -> void:
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	current_health = max_health
	emit_signal("health_changed", current_health, max_health)
	if not sprite and has_node("Sprite2D"):
		sprite = $Sprite2D

func _physics_process(delta: float) -> void:
	if current_health <= 0:
		return
		
	# 1. Player Input Vector
	var input_vector = Vector2.ZERO
	input_vector.x = Input.get_axis("move_left", "move_right")
	input_vector.y = Input.get_axis("move_up", "move_down")
	
	var move_velocity = Vector2.ZERO
	if input_vector != Vector2.ZERO:
		input_vector = input_vector.normalized()
		facing_direction = input_vector
		move_velocity = input_vector * move_speed
		
		# Sprite movement juice: gentle tilt and bob
		if sprite:
			sprite.position.y = -2.0 + sin(Time.get_ticks_msec() / 90.0) * 1.5
			sprite.rotation = sin(Time.get_ticks_msec() / 110.0) * 0.07
			if abs(facing_direction.x) > 0.1:
				sprite.flip_h = (facing_direction.x < 0.0)
	else:
		if sprite:
			sprite.position.y = -2.0
			sprite.rotation = 0.0
			
	# 2. Decay Persistent Knockback Force
	if knockback_velocity != Vector2.ZERO:
		knockback_velocity = knockback_velocity.move_toward(Vector2.ZERO, knockback_decay * delta)
		
	# 3. Combine Input & Knockback Vectors (prevents bounce/stick trapping)
	velocity = move_velocity + knockback_velocity
	move_and_slide()
	
	# Attack Handling
	if Input.is_action_just_pressed("attack") and can_attack:
		perform_attack()
		
	# Timers
	if is_invulnerable:
		invulnerable_timer -= delta
		if sprite:
			# Hurt blink effect
			sprite.modulate.a = 0.4 if fmod(Time.get_ticks_msec() / 80.0, 2.0) > 1.0 else 1.0
		if invulnerable_timer <= 0.0:
			is_invulnerable = false
			if sprite:
				sprite.modulate = Color.WHITE
	else:
		if sprite and sprite.modulate.a != 1.0:
			sprite.modulate = Color.WHITE
			
	if is_swinging:
		swing_timer -= delta
		if swing_timer <= 0.0:
			is_swinging = false
			
	queue_redraw()

func apply_knockback(impulse: Vector2) -> void:
	knockback_velocity = impulse

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
	emit_signal("player_damaged", amount)
	
	# Apply persistent knockback impulse away from attacker
	if from_dir != Vector2.ZERO:
		apply_knockback(from_dir * 340.0)
		
	if current_health <= 0:
		emit_signal("player_died")

func heal(amount: float) -> void:
	var actual_heal = minf(amount, max_health - current_health)
	if actual_heal > 0:
		current_health = minf(max_health, current_health + actual_heal)
		emit_signal("health_changed", current_health, max_health)
		emit_signal("player_healed", actual_heal)

func reset(start_pos: Vector2) -> void:
	global_position = start_pos
	current_health = max_health
	is_invulnerable = false
	is_swinging = false
	can_attack = true
	knockback_velocity = Vector2.ZERO
	velocity = Vector2.ZERO
	if sprite:
		sprite.modulate = Color.WHITE
		sprite.rotation = 0.0
		sprite.position = Vector2(0, -2)
	emit_signal("health_changed", current_health, max_health)

func _draw() -> void:
	# Subtle grounded shadow underneath sprite
	draw_circle(Vector2(0, 10), 15.0, Color(0, 0, 0, 0.35))
	
	# Sword Attack Arc Visual (Kinetic Slash FX)
	if is_swinging:
		var arc_center = Vector2.ZERO
		var arc_radius = 48.0
		var start_a = swing_angle - PI/2.8
		var end_a = swing_angle + PI/2.8
		
		# Outer luminous slash wave
		draw_arc(arc_center, arc_radius + 4.0, start_a, end_a, 20, Color(1.0, 0.95, 0.5, 0.9), 5.5)
		# Inner piercing blade line
		draw_arc(arc_center, arc_radius, start_a + 0.1, end_a - 0.1, 20, Color(1.0, 1.0, 1.0, 1.0), 3.0)
		draw_line(arc_center, arc_center + Vector2.from_angle(swing_angle) * (arc_radius + 8.0), Color(1.0, 0.9, 0.3), 3.0)
