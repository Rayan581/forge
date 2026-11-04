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
# --- Sprite animation (AnimatedSprite2D driven by game state) ---
# The attack animation is 6 frames @ 30 fps (0.2 s); the slash arc is on its frames 3-4, so the
# damage query fires ATTACK_HIT_DELAY (= 3 frames) after the swing starts. The total attack
# cooldown (attack_cooldown) is unchanged.
const ATTACK_ANIM_TIME := 0.2
const ATTACK_HIT_DELAY := 0.1
const HURT_ANIM_TIME := 0.25
var attack_anim_timer: float = 0.0
var hurt_anim_timer: float = 0.0
var is_moving: bool = false
var base_scale: Vector2 = Vector2(2, 2)
var base_pos: Vector2 = Vector2(0, -15)

@onready var sprite: AnimatedSprite2D = get_node_or_null("AnimatedSprite2D")

func _ready() -> void:
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	current_health = max_health
	emit_signal("health_changed", current_health, max_health)
	if not sprite and has_node("AnimatedSprite2D"):
		sprite = $AnimatedSprite2D
	if sprite:
		base_scale = sprite.scale
		base_pos = sprite.position

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
	is_moving = input_vector != Vector2.ZERO
	
	if is_dashing:
		dash_timer -= delta
		move_velocity = dash_direction * (move_speed * dash_speed_multiplier)
		if sprite:
			sprite.scale = base_scale * Vector2(1.25, 0.75)
			sprite.modulate = Color(0.6, 1.3, 2.2, 0.85)
		if dash_timer <= 0.0:
			is_dashing = false
			if sprite:
				sprite.scale = base_scale
	elif input_vector != Vector2.ZERO:
		input_vector = input_vector.normalized()
		facing_direction = input_vector
		move_velocity = input_vector * move_speed
		emit_signal("player_moved")
		
		# The walk cycle supplies the bob; just face the direction of travel.
		if sprite and attack_anim_timer <= 0.0 and abs(facing_direction.x) > 0.1:
			sprite.flip_h = (facing_direction.x < 0.0)
			
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
	attack_anim_timer = maxf(0.0, attack_anim_timer - delta)
	hurt_anim_timer = maxf(0.0, hurt_anim_timer - delta)
	_update_animation()
			
	queue_redraw()

## Picks the looping base animation (idle/move). attack/hurt/death are one-shots started by
## perform_attack() / take_damage() and simply hold priority until their timers run out.
func _update_animation() -> void:
	if not sprite or current_health <= 0.0 or attack_anim_timer > 0.0 or hurt_anim_timer > 0.0:
		return
	var want := &"move" if (is_moving or is_dashing) else &"idle"
	if sprite.animation != want or not sprite.is_playing():
		sprite.play(want)

func _play_oneshot(anim: StringName) -> void:
	if sprite and sprite.sprite_frames and sprite.sprite_frames.has_animation(anim):
		sprite.play(anim)

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
	
	# Attack target point based on mouse or facing direction
	var mouse_pos = get_global_mouse_position()
	var attack_dir = (mouse_pos - global_position).normalized()
	if attack_dir == Vector2.ZERO:
		attack_dir = facing_direction
	swing_angle = attack_dir.angle()
	
	# Swing animation: face the aim side, play the slash, land the hit on the arc frames.
	attack_anim_timer = ATTACK_ANIM_TIME
	if sprite and abs(attack_dir.x) > 0.05:
		sprite.flip_h = (attack_dir.x < 0.0)
	_play_oneshot(&"attack")
	await get_tree().create_timer(ATTACK_HIT_DELAY).timeout
	if is_instance_valid(self) and current_health > 0.0:
		is_swinging = true # aimed slash FX lands together with the sprite's arc frames
		swing_timer = 0.18
		_apply_attack_hit(attack_dir)
			
	# Cooldown timer (total swing time unchanged: ATTACK_HIT_DELAY + remainder == attack_cooldown)
	await get_tree().create_timer(maxf(attack_cooldown - ATTACK_HIT_DELAY, 0.0)).timeout
	can_attack = true

func _apply_attack_hit(attack_dir: Vector2) -> void:
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
		attack_anim_timer = 0.0
		if sprite:
			sprite.modulate = Color.WHITE
			sprite.scale = base_scale
		_play_oneshot(&"death")
		emit_signal("player_died")
	else:
		hurt_anim_timer = HURT_ANIM_TIME
		_play_oneshot(&"hurt")

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
	attack_anim_timer = 0.0
	hurt_anim_timer = 0.0
	if sprite:
		sprite.modulate = Color.WHITE
		sprite.rotation = 0.0
		sprite.position = base_pos
		sprite.scale = base_scale
		sprite.play(&"idle")
	emit_signal("health_changed", current_health, max_health)

func _draw() -> void:
	# Subtle grounded shadow underneath sprite
	draw_set_transform(Vector2(0, 11), 0.0, Vector2(1.0, 0.42))
	draw_circle(Vector2.ZERO, 15.0, Color(0, 0, 0, 0.45))
	# Faint cyan ground ring so the hero never gets lost among the (also skeletal) crawlers
	draw_arc(Vector2.ZERO, 15.0, 0.0, TAU, 28, Color(0.35, 0.85, 1.0, 0.55), 1.2)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	
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
		draw_arc(arc_center, arc_radius + 6.0, start_a, end_a, 24, Color(1.0, 0.75, 0.25, 0.22), 6.0)
		# 2. Main crescent blade wave (electric gold)
		draw_arc(arc_center, arc_radius, start_a, end_a, 24, Color(1.0, 0.95, 0.45, 0.6), 3.0)
		# 3. Inner razor edge (pure bright white)
		draw_arc(arc_center, arc_radius - 2.0, start_a + 0.1, end_a - 0.1, 24, Color(1.0, 1.0, 1.0, 0.7), 1.5)
		# 4. Kinetic tip punch line
		var tip_vec = Vector2.from_angle(swing_angle) * (arc_radius + 12.0)
		draw_line(arc_center, arc_center + tip_vec, Color(1.0, 0.9, 0.5, 0.35), 2.0)
		draw_circle(arc_center + tip_vec, 3.5, Color(1.0, 1.0, 1.0, 0.9))
