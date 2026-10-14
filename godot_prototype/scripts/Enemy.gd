class_name Enemy
extends CharacterBody2D

signal enemy_defeated(enemy_node: Enemy)
signal enemy_damaged(amount: float, hit_position: Vector2)

enum Archetype { MELEE_CRAWLER, RANGED_PYROMANCER }
@export var archetype: Archetype = Archetype.MELEE_CRAWLER

@export var max_health: float = 60.0
var current_health: float = 60.0
@export var attack_damage: float = 20.0
@export var move_speed: float = 125.0
@export var aggro_radius: float = 240.0
@export var attack_reach: float = 38.0
@export var attack_rate: float = 0.8

# Ranged Pyromancer specific variables
var standoff_min: float = 180.0
var standoff_max: float = 230.0
var is_charging: bool = false
var charge_timer: float = 0.0
var charge_duration: float = 0.5 # 0.5s yellow telegraph tell
var aim_direction: Vector2 = Vector2.RIGHT

var player_ref: Node2D = null
var attack_cooldown_timer: float = 0.0
var is_flashing: bool = false
var flash_timer: float = 0.0
var wander_timer: float = 0.0
var wander_direction: Vector2 = Vector2.ZERO

# Persistent Knockback Impulse System
var knockback_velocity: Vector2 = Vector2.ZERO
var knockback_decay: float = 1400.0 # Decays 420px/s impulse smoothly over ~0.30s

enum State { WANDER, CHASE, KITE, CHARGING, ATTACK }
var current_state: State = State.WANDER

var tex_crawler: Texture2D = preload("res://assets/sprites/enemy_crawler.png")
var tex_pyromancer: Texture2D = preload("res://assets/sprites/enemy_pyromancer.png")
var projectile_scene: PackedScene = preload("res://scenes/ProjectileFireball.tscn")

@onready var sprite: Sprite2D = get_node_or_null("Sprite2D")

func _ready() -> void:
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	if not sprite and has_node("Sprite2D"):
		sprite = $Sprite2D
	_apply_archetype()
	current_health = max_health

func set_archetype(p_archetype: Archetype) -> void:
	archetype = p_archetype
	_apply_archetype()

func _apply_archetype() -> void:
	if archetype == Archetype.RANGED_PYROMANCER:
		if sprite:
			sprite.texture = tex_pyromancer
		attack_reach = 220.0
		attack_rate = 1.6
		standoff_min = 180.0
		standoff_max = 230.0
	else:
		if sprite:
			sprite.texture = tex_crawler
		attack_reach = 38.0
		attack_rate = 0.8

func configure_parameters(p_health: float, p_damage: float, p_speed: float, p_aggro: float) -> void:
	if archetype == Archetype.RANGED_PYROMANCER:
		max_health = p_health * 0.75 # Lower HP for ranged caster
		attack_damage = p_damage * 0.9 # Projectile damage ~18
		move_speed = p_speed * 0.92
		aggro_radius = maxf(p_aggro, 260.0)
	else:
		max_health = p_health
		attack_damage = p_damage
		move_speed = p_speed
		aggro_radius = p_aggro
		
	current_health = max_health
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
		aim_direction = dir_to_player
		
		if archetype == Archetype.MELEE_CRAWLER:
			move_velocity = _process_crawler_ai(dist_to_player, dir_to_player, delta)
		else:
			move_velocity = _process_pyromancer_ai(dist_to_player, dir_to_player, delta)
	else:
		move_velocity = Vector2.ZERO
		current_state = State.WANDER
		
	# Decay Persistent Knockback Force
	if knockback_velocity != Vector2.ZERO:
		knockback_velocity = knockback_velocity.move_toward(Vector2.ZERO, knockback_decay * delta)
		
	# Apply Combined Velocity
	velocity = move_velocity + knockback_velocity
	
	# Sprite visual juice
	if sprite:
		if abs(velocity.x) > 5.0:
			sprite.flip_h = (velocity.x < 0.0)
			
		if archetype == Archetype.MELEE_CRAWLER:
			if current_state == State.CHASE:
				var scuttle = sin(Time.get_ticks_msec() / 65.0) * 0.1
				sprite.scale = Vector2(1.0 + scuttle, 1.0 - scuttle)
			else:
				sprite.scale = Vector2(1.0, 1.0)
		else:
			# Pyromancer floating levitation bob
			var hover = sin(Time.get_ticks_msec() / 110.0) * 2.0
			sprite.position.y = -2.0 + hover
			if is_charging:
				# Pulsing yellow charging glow
				var glow = sin(Time.get_ticks_msec() / 40.0) * 0.4
				sprite.modulate = Color(1.8 + glow, 1.6 + glow, 0.4)
			elif not is_flashing:
				sprite.modulate = Color.WHITE
		
	move_and_slide()
	queue_redraw()

func _process_crawler_ai(dist_to_player: float, dir_to_player: Vector2, delta: float) -> Vector2:
	var move_velocity = Vector2.ZERO
	# 1. Contact Anti-Stuck Separation (< 34px: colliders are touching)
	if dist_to_player < 34.0:
		current_state = State.ATTACK
		move_velocity = -dir_to_player * 75.0
		if attack_cooldown_timer <= 0.0:
			perform_attack()
	# 2. Attack Reach (34px - 38px): Hold position and strike
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
		
	return move_velocity

func _process_pyromancer_ai(dist_to_player: float, dir_to_player: Vector2, delta: float) -> Vector2:
	var move_velocity = Vector2.ZERO
	
	if is_charging:
		current_state = State.CHARGING
		charge_timer += delta
		# Slowly drift backwards while casting
		move_velocity = -dir_to_player * 25.0
		if charge_timer >= charge_duration:
			is_charging = false
			shoot_fireball(dir_to_player)
		return move_velocity
		
	# If player is outside aggro radius: Wander casually
	if dist_to_player > aggro_radius:
		current_state = State.WANDER
		wander_timer -= delta
		if wander_timer <= 0.0:
			wander_timer = randf_range(2.0, 4.0)
			wander_direction = Vector2(randf_range(-1, 1), randf_range(-1, 1)).normalized()
		move_velocity = wander_direction * (move_speed * 0.4)
		return move_velocity
		
	# Player is within aggro radius:
	# 1. Kiting Retreat: Player is too close (< 180px), back away
	if dist_to_player < standoff_min:
		current_state = State.KITE
		move_velocity = -dir_to_player * (move_speed * 1.1)
		# Can still cast while backing away if cooldown is ready
		if attack_cooldown_timer <= 0.0:
			start_charging()
	# 2. Approach: Player is beyond standoff range (> 230px), close in
	elif dist_to_player > standoff_max:
		current_state = State.CHASE
		move_velocity = dir_to_player * move_speed
	# 3. Sweet Spot (180px - 230px): Standoff distance maintained!
	else:
		current_state = State.ATTACK
		# Slight strafe to feel alive and avoid feeling static
		var strafe_dir = Vector2(-dir_to_player.y, dir_to_player.x)
		move_velocity = strafe_dir * 30.0
		if attack_cooldown_timer <= 0.0:
			start_charging()
			
	return move_velocity

func start_charging() -> void:
	is_charging = true
	charge_timer = 0.0
	current_state = State.CHARGING

func shoot_fireball(target_dir: Vector2) -> void:
	attack_cooldown_timer = attack_rate
	if projectile_scene:
		var p = projectile_scene.instantiate() as ProjectileFireball
		p.global_position = global_position + target_dir * 24.0
		p.setup(target_dir, attack_damage, 240.0)
		get_parent().add_child(p)
		# Light recoil pushback on caster
		apply_knockback(-target_dir * 120.0)

func apply_knockback(impulse: Vector2) -> void:
	knockback_velocity = impulse

func perform_attack() -> void:
	attack_cooldown_timer = attack_rate
	if player_ref and player_ref.has_method("take_damage"):
		var attack_dir = (player_ref.global_position - global_position).normalized()
		player_ref.take_damage(attack_damage, attack_dir)
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
	
	# If was charging, taking heavy damage interrupts charge slightly
	if is_charging and amount > 25.0:
		is_charging = false
		attack_cooldown_timer = 0.6
		
	# Apply persistent knockback impulse away from weapon hit
	if from_dir != Vector2.ZERO:
		apply_knockback(from_dir * 420.0)
		
	if current_health <= 0:
		emit_signal("enemy_defeated", self)
		queue_free()

## Instantly defeats this enemy (used by the Defense Panel's testing toggle).
func kill() -> void:
	take_damage(current_health)

func _draw() -> void:
	# Grounded contact shadow
	draw_circle(Vector2(0, 12), 16.0, Color(0, 0, 0, 0.42))
	
	if archetype == Archetype.MELEE_CRAWLER:
		# Menacing demonic aggro aura with pulsing edge
		if current_state == State.CHASE:
			var pulse = sin(Time.get_ticks_msec() / 120.0) * 3.0
			draw_arc(Vector2.ZERO, 24.0 + pulse, 0, TAU, 24, Color(1.0, 0.25, 0.15, 0.45), 2.5)
			draw_arc(Vector2.ZERO, 20.0, 0, TAU, 24, Color(1.0, 0.4, 0.2, 0.25), 1.5)
	else:
		# Pyromancer Fiery Runic Aura
		var pulse_fire = sin(Time.get_ticks_msec() / 90.0) * 3.0
		if current_state == State.CHARGING:
			# Vibrant charging telegraph beam & tell circle
			var charge_progress = clampf(charge_timer / charge_duration, 0.0, 1.0)
			var tell_radius = 28.0 * (1.0 - charge_progress * 0.3)
			# Outer charging ring collapsing in
			draw_arc(Vector2.ZERO, tell_radius, 0, TAU, 24, Color(1.0, 0.8, 0.1, 0.9), 3.0)
			# Telegraphed aim indicator line toward player
			draw_line(Vector2.ZERO, aim_direction * (32.0 + charge_progress * 24.0), Color(1.0, 0.6, 0.1, 0.85), 2.5)
			# Fiery core burst
			draw_circle(Vector2.ZERO, 10.0 + charge_progress * 6.0, Color(1.0, 0.4, 0.05, 0.4))
		elif current_state == State.CHASE or current_state == State.KITE:
			# Ambient warm ember aura
			draw_arc(Vector2.ZERO, 22.0 + pulse_fire, 0, TAU, 24, Color(1.0, 0.45, 0.1, 0.4), 2.0)
	
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
			var hp_color = Color(0.95, 0.2, 0.25, 0.95) if archetype == Archetype.MELEE_CRAWLER else Color(1.0, 0.5, 0.1, 0.95)
			draw_rect(Rect2(-bar_w/2, bar_y, fill_w, bar_h), hp_color)
			draw_line(Vector2(-bar_w/2, bar_y + 1), Vector2(-bar_w/2 + fill_w, bar_y + 1), Color(1.0, 0.7, 0.6, 0.7), 1.0)
