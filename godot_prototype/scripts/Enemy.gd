class_name Enemy
extends CharacterBody2D

signal enemy_defeated(enemy_node: Enemy)
signal enemy_damaged(amount: float, hit_position: Vector2)

@export var max_health: float = 60.0
var current_health: float = 60.0
@export var attack_damage: float = 20.0
@export var move_speed: float = 125.0
@export var aggro_radius: float = 240.0
@export var attack_reach: float = 38.0
@export var attack_rate: float = 0.8

var player_ref: Node2D = null
var attack_cooldown_timer: float = 0.0
var is_flashing: bool = false
var flash_timer: float = 0.0
var wander_timer: float = 0.0
var wander_direction: Vector2 = Vector2.ZERO

# Persistent Knockback Impulse System
var knockback_velocity: Vector2 = Vector2.ZERO
var knockback_decay: float = 1400.0 # Decays 420px/s impulse smoothly over ~0.30s

enum State { WANDER, CHASE, ATTACK }
var current_state: State = State.WANDER

@onready var sprite: Sprite2D = get_node_or_null("Sprite2D")

func _ready() -> void:
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	current_health = max_health
	if not sprite and has_node("Sprite2D"):
		sprite = $Sprite2D

func configure_parameters(p_health: float, p_damage: float, p_speed: float, p_aggro: float) -> void:
	max_health = p_health
	current_health = max_health
	attack_damage = p_damage
	move_speed = p_speed
	aggro_radius = p_aggro
	queue_redraw()

func _physics_process(delta: float) -> void:
	if current_health <= 0:
		return
		
	if attack_cooldown_timer > 0.0:
		attack_cooldown_timer -= delta
		
	if is_flashing:
		flash_timer -= delta
		if flash_timer <= 0.0:
			is_flashing = false
			if sprite:
				sprite.modulate = Color.WHITE
			
	if not is_instance_valid(player_ref):
		player_ref = get_tree().get_first_node_in_group("player")
		
	var move_velocity = Vector2.ZERO
	
	if player_ref:
		var dist_to_player = global_position.distance_to(player_ref.global_position)
		var dir_to_player = (player_ref.global_position - global_position).normalized()
		
		# 1. Contact Anti-Stuck Separation (< 34px: colliders are touching)
		if dist_to_player < 34.0:
			current_state = State.ATTACK
			# Back off slightly so colliders don't pinch and stick
			move_velocity = -dir_to_player * 75.0
			if attack_cooldown_timer <= 0.0:
				perform_attack()
				
		# 2. Attack Reach (34px - 38px): Hold position and strike without pushing
		elif dist_to_player <= attack_reach:
			current_state = State.ATTACK
			move_velocity = Vector2.ZERO
			if attack_cooldown_timer <= 0.0:
				perform_attack()
				
		# 3. Chase Range
		elif dist_to_player <= aggro_radius:
			current_state = State.CHASE
			move_velocity = dir_to_player * move_speed
			
		# 4. Wander Range
		else:
			current_state = State.WANDER
			wander_timer -= delta
			if wander_timer <= 0.0:
				wander_timer = randf_range(1.5, 3.5)
				wander_direction = Vector2(randf_range(-1, 1), randf_range(-1, 1)).normalized()
			move_velocity = wander_direction * (move_speed * 0.45)
	else:
		move_velocity = Vector2.ZERO
		
	# 5. Decay Persistent Knockback Force
	if knockback_velocity != Vector2.ZERO:
		knockback_velocity = knockback_velocity.move_toward(Vector2.ZERO, knockback_decay * delta)
		
	# 6. Apply Combined Velocity
	velocity = move_velocity + knockback_velocity
	
	# Sprite visual juice: scuttle and flip
	if sprite:
		if abs(velocity.x) > 5.0:
			sprite.flip_h = (velocity.x < 0.0)
		if current_state == State.CHASE:
			var scuttle = sin(Time.get_ticks_msec() / 65.0) * 0.1
			sprite.scale = Vector2(1.0 + scuttle, 1.0 - scuttle)
		else:
			sprite.scale = Vector2(1.0, 1.0)
		
	move_and_slide()
	queue_redraw()

func apply_knockback(impulse: Vector2) -> void:
	knockback_velocity = impulse

func perform_attack() -> void:
	attack_cooldown_timer = attack_rate
	if player_ref and player_ref.has_method("take_damage"):
		var attack_dir = (player_ref.global_position - global_position).normalized()
		player_ref.take_damage(attack_damage, attack_dir)
		# Tactile recoil bounce on attacker (creates clean 50px separation gap)
		apply_knockback(-attack_dir * 180.0)

func take_damage(amount: float, from_dir: Vector2 = Vector2.ZERO) -> void:
	if current_health <= 0:
		return
		
	current_health -= amount
	is_flashing = true
	flash_timer = 0.14
	if sprite:
		sprite.modulate = Color(2.5, 2.2, 2.2) # Crisp hurt flash
		
	emit_signal("enemy_damaged", amount, global_position)
	
	# Apply persistent knockback impulse away from weapon hit
	if from_dir != Vector2.ZERO:
		apply_knockback(from_dir * 420.0)
		
	if current_health <= 0:
		emit_signal("enemy_defeated", self)
		queue_free()

## Instantly defeats this enemy (used by the Defense Panel's testing toggle).
## Routes through take_damage so telemetry/signals fire exactly as a normal kill would.
func kill() -> void:
	take_damage(current_health)

func _draw() -> void:
	# Grounded contact shadow
	draw_circle(Vector2(0, 12), 16.0, Color(0, 0, 0, 0.42))
	
	# Menacing demonic aggro aura with pulsing edge
	if current_state == State.CHASE:
		var pulse = sin(Time.get_ticks_msec() / 120.0) * 3.0
		draw_arc(Vector2.ZERO, 24.0 + pulse, 0, TAU, 24, Color(1.0, 0.25, 0.15, 0.45), 2.5)
		draw_arc(Vector2.ZERO, 20.0, 0, TAU, 24, Color(1.0, 0.4, 0.2, 0.25), 1.5)
	
	# Beveled dark health bar with crimson-orange gradient
	if current_health < max_health:
		var bar_w = 34.0
		var bar_h = 5.0
		var bar_y = -26.0
		# Dark steel backing border
		draw_rect(Rect2(-bar_w/2 - 1.5, bar_y - 1.5, bar_w + 3.0, bar_h + 3.0), Color(0.06, 0.06, 0.09, 0.95))
		draw_rect(Rect2(-bar_w/2, bar_y, bar_w, bar_h), Color(0.2, 0.08, 0.1, 0.9))
		var hp_ratio = clampf(current_health / max_health, 0.0, 1.0)
		var fill_w = bar_w * hp_ratio
		if fill_w > 0:
			draw_rect(Rect2(-bar_w/2, bar_y, fill_w, bar_h), Color(0.95, 0.2, 0.25, 0.95))
			# Top gloss shine
			draw_line(Vector2(-bar_w/2, bar_y + 1), Vector2(-bar_w/2 + fill_w, bar_y + 1), Color(1.0, 0.55, 0.6, 0.7), 1.0)

