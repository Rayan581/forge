class_name Enemy
extends CharacterBody2D

signal enemy_defeated(enemy_node: Enemy)

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

enum State { WANDER, CHASE, ATTACK }
var current_state: State = State.WANDER

func _ready() -> void:
	current_health = max_health

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
			
	if not is_instance_valid(player_ref):
		player_ref = get_tree().get_first_node_in_group("player")
		
	if player_ref:
		var dist_to_player = global_position.distance_to(player_ref.global_position)
		var dir_to_player = (player_ref.global_position - global_position).normalized()
		
		if dist_to_player <= attack_reach:
			current_state = State.ATTACK
			velocity = velocity.move_toward(Vector2.ZERO, move_speed * 6.0 * delta)
			if attack_cooldown_timer <= 0.0:
				perform_attack()
		elif dist_to_player <= aggro_radius:
			current_state = State.CHASE
			velocity = dir_to_player * move_speed
		else:
			current_state = State.WANDER
			wander_timer -= delta
			if wander_timer <= 0.0:
				wander_timer = randf_range(1.5, 3.5)
				wander_direction = Vector2(randf_range(-1, 1), randf_range(-1, 1)).normalized()
			velocity = wander_direction * (move_speed * 0.45)
	else:
		velocity = Vector2.ZERO
		
	move_and_slide()
	queue_redraw()

func perform_attack() -> void:
	attack_cooldown_timer = attack_rate
	if player_ref and player_ref.has_method("take_damage"):
		var attack_dir = (player_ref.global_position - global_position).normalized()
		player_ref.take_damage(attack_damage, attack_dir)

func take_damage(amount: float, from_dir: Vector2 = Vector2.ZERO) -> void:
	if current_health <= 0:
		return
		
	current_health -= amount
	is_flashing = true
	flash_timer = 0.15
	
	if from_dir != Vector2.ZERO:
		velocity = from_dir * 320.0
		
	if current_health <= 0:
		emit_signal("enemy_defeated", self)
		queue_free()

## Instantly defeats this enemy (used by the Defense Panel's testing toggle).
## Routes through take_damage so telemetry/signals fire exactly as a normal kill would.
func kill() -> void:
	take_damage(current_health)

func _draw() -> void:
	# Calculate visual scaling based on parameters (higher HP = bulkier, higher Dmg = redder)
	var radius = 13.0 + clampf((max_health - 20.0) / 100.0 * 7.0, 0.0, 8.0)
	var red_intensity = clampf((attack_damage - 5.0) / 45.0, 0.3, 1.0)
	var body_color = Color(red_intensity, 0.18, 0.22)
	if is_flashing:
		body_color = Color(1.0, 1.0, 1.0)
		
	# Shadow
	draw_circle(Vector2(0, radius * 0.7), radius * 0.9, Color(0, 0, 0, 0.3))
	# Aggro Aura ring if chasing
	if current_state == State.CHASE:
		draw_arc(Vector2.ZERO, radius + 4.0, 0, TAU, 16, Color(1.0, 0.3, 0.2, 0.55), 2.0)
	# Main Body
	draw_circle(Vector2.ZERO, radius, body_color)
	draw_circle(Vector2.ZERO, radius, Color(0.12, 0.05, 0.05), false, 2.0)
	# Glowing Horns / Spikes based on damage
	var horn_len = 4.0 + (attack_damage / 10.0)
	draw_line(Vector2(-radius*0.6, -radius*0.5), Vector2(-radius*0.8, -radius*0.5 - horn_len), Color(0.9, 0.7, 0.1), 2.5)
	draw_line(Vector2(radius*0.6, -radius*0.5), Vector2(radius*0.8, -radius*0.5 - horn_len), Color(0.9, 0.7, 0.1), 2.5)
	# Eyes
	draw_circle(Vector2(-4, -2), 3.0, Color(1.0, 0.9, 0.2))
	draw_circle(Vector2(4, -2), 3.0, Color(1.0, 0.9, 0.2))
	draw_circle(Vector2(-4, -2), 1.5, Color(0.1, 0.0, 0.0))
	draw_circle(Vector2(4, -2), 1.5, Color(0.1, 0.0, 0.0))
	
	# Health Bar
	if current_health < max_health:
		var bar_w = radius * 2.2
		var bar_h = 4.0
		var bar_y = -radius - 8.0
		draw_rect(Rect2(-bar_w/2, bar_y, bar_w, bar_h), Color(0.15, 0.15, 0.15, 0.8))
		var hp_ratio = clampf(current_health / max_health, 0.0, 1.0)
		draw_rect(Rect2(-bar_w/2, bar_y, bar_w * hp_ratio, bar_h), Color(0.9, 0.2, 0.2, 0.9))
