class_name Player
extends CharacterBody2D

signal health_changed(current_hp: float, max_hp: float)
signal player_damaged(amount: float)
signal player_healed(amount: float)
signal player_died
signal player_moved
signal player_dashed

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

# Dodge Roll / Dash System (Spacebar)
var is_dashing: bool = false
var dash_timer: float = 0.0
var dash_duration: float = 0.20
var dash_speed_multiplier: float = 2.45
var dash_cooldown: float = 1.0
var dash_cooldown_timer: float = 0.0
var dash_direction: Vector2 = Vector2.DOWN

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
		
	if dash_cooldown_timer > 0.0:
		dash_cooldown_timer -= delta
		
	# 1. Player Input Vector
	var input_vector = Vector2.ZERO
	input_vector.x = Input.get_axis("move_left", "move_right")
	input_vector.y = Input.get_axis("move_up", "move_down")
	
	# Check Dodge Roll trigger
	var wants_dodge = Input.is_action_just_pressed("dodge")
	if not wants_dodge and Input.is_key_pressed(KEY_SPACE) and not Input.is_action_just_pressed("attack"):
		wants_dodge = true
		
	if wants_dodge and dash_cooldown_timer <= 0.0 and not is_dashing:
		perform_dash(input_vector)
		
	var move_velocity = Vector2.ZERO
	
	if is_dashing:
		dash_timer -= delta
		move_velocity = dash_direction * (move_speed * dash_speed_multiplier)
		if sprite:
			sprite.scale = Vector2(1.25, 0.75)
			sprite.modulate = Color(0.6, 1.3, 2.2, 0.85)
		if dash_timer <= 0.0:
			is_dashing = false
			if sprite:
				sprite.scale = Vector2.ONE
	elif input_vector != Vector2.ZERO:
		input_vector = input_vector.normalized()
		facing_direction = input_vector
		move_velocity = input_vector * move_speed
		emit_signal("player_moved")
		
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
	if Input.is_action_just_pressed("attack") and can_attack and not is_dashing:
		perform_attack()
		
	# Timers
	if is_invulnerable and not is_dashing:
		invulnerable_timer -= delta
		if sprite:
			# Hurt blink effect
			sprite.modulate.a = 0.4 if fmod(Time.get_ticks_msec() / 80.0, 2.0) > 1.0 else 1.0
		if invulnerable_timer <= 0.0:
			is_invulnerable = false
			if sprite:
				sprite.modulate = Color.WHITE
	elif not is_dashing:
		if sprite and sprite.modulate != Color.WHITE:
			sprite.modulate = Color.WHITE
			
	if is_swinging:
		swing_timer -= delta
		if swing_timer <= 0.0:
			is_swinging = false
			
	queue_redraw()

func perform_dash(input_dir: Vector2) -> void:
	is_dashing = true
	dash_timer = dash_duration
	dash_cooldown_timer = dash_cooldown
	is_invulnerable = true
	invulnerable_timer = dash_duration + 0.06
	
	if input_dir != Vector2.ZERO:
		dash_direction = input_dir.normalized()
	else:
		dash_direction = facing_direction
		
	emit_signal("player_dashed")

func apply_knockback(impulse: Vector2) -> void:
	if not is_dashing:
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
	is_dashing = false
	is_swinging = false
	can_attack = true
	dash_cooldown_timer = 0.0
	knockback_velocity = Vector2.ZERO
	velocity = Vector2.ZERO
	if sprite:
		sprite.modulate = Color.WHITE
		sprite.rotation = 0.0
		sprite.position = Vector2(0, -2)
		sprite.scale = Vector2.ONE
	emit_signal("health_changed", current_health, max_health)

func _draw() -> void:
	# Subtle grounded shadow underneath sprite
	draw_circle(Vector2(0, 10), 16.0, Color(0, 0, 0, 0.4))
	
	# Ethereal Dash Afterimage Trail
	if is_dashing:
		var trail_p1 = -dash_direction * 16.0
		var trail_p2 = -dash_direction * 32.0
		draw_circle(trail_p1, 14.0, Color(0.3, 0.7, 1.0, 0.4))
		draw_circle(trail_p2, 10.0, Color(0.2, 0.5, 0.9, 0.22))
		draw_line(Vector2.ZERO, -dash_direction * 40.0, Color(0.6, 0.9, 1.0, 0.75), 3.0)
	
	# Subtle dash cooldown ring around feet when cooling down
	if dash_cooldown_timer > 0.0:
		var recharge = 1.0 - (dash_cooldown_timer / dash_cooldown)
		draw_arc(Vector2(0, 10), 18.0, -PI/2, -PI/2 + TAU * recharge, 20, Color(0.3, 0.8, 1.0, 0.5), 2.0)
	
	# Sword Attack Arc Visual (Kinetic Slash FX with Radiant Bloom)
	if is_swinging:
		var arc_center = Vector2.ZERO
		var arc_radius = 52.0
		var start_a = swing_angle - PI/2.6
		var end_a = swing_angle + PI/2.6
		
		# 1. Outer luminous radiant flare (gold/amber)
		draw_arc(arc_center, arc_radius + 6.0, start_a, end_a, 24, Color(1.0, 0.75, 0.25, 0.5), 8.0)
		# 2. Main crescent blade wave (electric gold)
		draw_arc(arc_center, arc_radius, start_a, end_a, 24, Color(1.0, 0.95, 0.45, 0.95), 4.5)
		# 3. Inner razor edge (pure bright white)
		draw_arc(arc_center, arc_radius - 2.0, start_a + 0.1, end_a - 0.1, 24, Color(1.0, 1.0, 1.0, 1.0), 2.5)
		# 4. Kinetic tip punch line
		var tip_vec = Vector2.from_angle(swing_angle) * (arc_radius + 12.0)
		draw_line(arc_center, arc_center + tip_vec, Color(1.0, 0.9, 0.5, 0.8), 3.0)
		draw_circle(arc_center + tip_vec, 3.5, Color(1.0, 1.0, 1.0, 0.9))
