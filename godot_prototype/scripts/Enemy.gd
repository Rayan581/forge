class_name Enemy
extends CharacterBody2D

signal enemy_defeated(enemy_node: Enemy)
signal enemy_damaged(amount: float, hit_position: Vector2)
## Animation / VFX hooks. `kind` is one of &"melee", &"fireball", &"slam", &"lunge", &"bite".
signal attack_windup_started(kind: StringName)
signal attack_impact(kind: StringName)

# Order is part of the shared contract (CONTRACT.md section 1) - do not reorder.
enum Archetype { MELEE_CRAWLER, RANGED_PYROMANCER, HEAVY_BRUTE, AGILE_SKIRMISHER, SWARMER }

## Stat multipliers on the PPO base values: [hp, dmg, speed, aggro] (contract section 1).
## Pyromancer aggro is max(aggro, 420) and handled specially in configure_parameters().
const ARCHETYPE_MULTIPLIERS := {
	Archetype.MELEE_CRAWLER: [1.0, 1.0, 1.0, 1.0],
	Archetype.RANGED_PYROMANCER: [0.75, 0.9, 0.92, 1.0],
	Archetype.HEAVY_BRUTE: [2.0, 1.4, 0.55, 0.8],
	Archetype.AGILE_SKIRMISHER: [0.8, 0.8, 1.3, 1.2],
	Archetype.SWARMER: [0.35, 0.45, 1.15, 1.0],
}

# Heavy Brute tuning
const SLAM_TRIGGER_RANGE := 110.0
const SLAM_RADIUS := 90.0
const SLAM_WINDUP := 0.7
const SLAM_COOLDOWN := 2.2
const SLAM_RECOVER := 0.35
# Agile Skirmisher tuning
const SKIRM_TELEGRAPH := 0.2
const LUNGE_DURATION := 0.25
const LUNGE_SPEED_MULT := 2.5
const RETREAT_DURATION := 0.6
const SKIRM_COOLDOWN := 1.4
# Swarmer tuning
const SWARM_BITE_RATE := 0.7
const SWARM_BITE_REACH := 30.0
@export var archetype: Archetype = Archetype.MELEE_CRAWLER

@export var max_health: float = 60.0
var current_health: float = 60.0
@export var attack_damage: float = 20.0
@export var move_speed: float = 125.0
@export var aggro_radius: float = 240.0
@export var attack_reach: float = 38.0
@export var attack_rate: float = 0.8

# Ranged Pyromancer specific variables
var standoff_min: float = 140.0
var standoff_max: float = 280.0
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

## WIND_UP = telegraphed attack preparation (brute slam, skirmisher lunge tell).
## LUNGE / RETREAT / ORBIT are skirmisher phases. Original five values keep their order.
enum State { WANDER, CHASE, KITE, CHARGING, ATTACK, WIND_UP, LUNGE, RETREAT, ORBIT }
var current_state: State = State.WANDER

# Per-archetype runtime state
var knockback_scale: float = 1.0       # fraction of incoming knockback applied (brute 0.3)
var base_modulate: Color = Color.WHITE # resting sprite tint (set by _apply_archetype_visuals)
var visual_scale: float = 1.0          # sprite scale multiplier
var body_radius: float = 16.0          # collision radius (also used for shadow/health bar)
var bar_color: Color = Color(0.95, 0.2, 0.25, 0.95)
var phase_timer: float = 0.0           # elapsed time in the current WIND_UP/LUNGE/RETREAT/recover phase
var lunge_dir: Vector2 = Vector2.RIGHT
var lunge_hit: bool = false
var orbit_dir: float = 1.0
var orbit_switch_timer: float = 2.0
var orbit_radius: float = 140.0

# Pyromancer line-of-sight (walls = physics layer 3 -> mask bit 4). Cached so we don't raycast every frame.
const WALL_MASK := 4
const LOS_CHECK_INTERVAL := 0.1
var _los_timer: float = 0.0
var _has_los: bool = false
var swarm_offset_rad: float = 0.0      # flank angle offset (swarmer), set by Room via set_swarm_offset_deg()

## Per-archetype animated art (SpriteFrames built by tools/build_sprite_frames.py).
## Every set has: idle, move, attack, hurt, death.
const ARCHETYPE_FRAMES := {
	Archetype.MELEE_CRAWLER: preload("res://assets/sprites/crawler/crawler_frames.tres"),
	Archetype.RANGED_PYROMANCER: preload("res://assets/sprites/pyromancer/pyromancer_frames.tres"),
	Archetype.HEAVY_BRUTE: preload("res://assets/sprites/enemies/brute/brute_frames.tres"),
	Archetype.AGILE_SKIRMISHER: preload("res://assets/sprites/enemies/skirmisher/skirmisher_frames.tres"),
	Archetype.SWARMER: preload("res://assets/sprites/enemies/swarmer/swarmer_frames.tres"),
}
## [feet row inside the frame, frame height] in source pixels, used to plant the feet on the shadow.
const ARCHETYPE_FEET := {
	Archetype.MELEE_CRAWLER: [15.0, 16.0],
	Archetype.RANGED_PYROMANCER: [15.0, 16.0],
	Archetype.HEAVY_BRUTE: [32.0, 32.0],
	Archetype.AGILE_SKIRMISHER: [19.5, 20.0],
	Archetype.SWARMER: [15.5, 16.0],
}
const ATTACK_ANIM_TIME := 0.25
const DEATH_ANIM_TIME := 0.45
var sprite_base_y: float = -2.0        # resting local y of the sprite (feet on the shadow)
var attack_anim_timer: float = 0.0     # one-shot strike pose (crawler strike, bite, fireball release)
var is_dying: bool = false             # death animation playing; body is inert (no collision/damage)
var projectile_scene: PackedScene = preload("res://scenes/ProjectileFireball.tscn")

@onready var sprite: AnimatedSprite2D = get_node_or_null("AnimatedSprite2D")

func _ready() -> void:
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	if not sprite and has_node("AnimatedSprite2D"):
		sprite = $AnimatedSprite2D
	_apply_archetype()
	current_health = max_health

func set_archetype(p_archetype: Archetype) -> void:
	archetype = p_archetype
	_apply_archetype()

func _apply_archetype() -> void:
	if archetype == Archetype.RANGED_PYROMANCER:
		attack_reach = 360.0
		attack_rate = 1.6
		standoff_min = 140.0
		standoff_max = 280.0
		aggro_radius = 420.0
	elif archetype == Archetype.HEAVY_BRUTE:
		attack_reach = SLAM_TRIGGER_RANGE
		attack_rate = SLAM_COOLDOWN
		knockback_scale = 0.3
		aggro_radius = 240.0
	elif archetype == Archetype.AGILE_SKIRMISHER:
		attack_reach = 40.0
		attack_rate = SKIRM_COOLDOWN
		orbit_radius = randf_range(120.0, 160.0)
		orbit_dir = 1.0 if randf() < 0.5 else -1.0
		aggro_radius = 240.0
	elif archetype == Archetype.SWARMER:
		attack_reach = SWARM_BITE_REACH
		attack_rate = SWARM_BITE_RATE
		aggro_radius = 240.0
	else:
		attack_reach = 38.0
		attack_rate = 0.8
		standoff_min = 34.0
		standoff_max = 38.0
		aggro_radius = 240.0
	if archetype != Archetype.HEAVY_BRUTE:
		knockback_scale = 1.0
	_apply_archetype_visuals()

## ALL per-archetype visuals live here: SpriteFrames, scale, feet placement, collider radius and
## health-bar colour. Art is 16-px (32-px for the brute) pixel art drawn at an integer x2.
func _apply_archetype_visuals() -> void:
	base_modulate = Color.WHITE
	visual_scale = 2.0
	body_radius = 16.0
	bar_color = Color(0.95, 0.2, 0.25, 0.95)
	match archetype:
		Archetype.RANGED_PYROMANCER:
			bar_color = Color(1.0, 0.5, 0.1, 0.95)
		Archetype.HEAVY_BRUTE:
			body_radius = 22.0
			bar_color = Color(0.7, 0.08, 0.1, 0.95)
		Archetype.AGILE_SKIRMISHER:
			bar_color = Color(0.2, 0.85, 0.8, 0.95)
		Archetype.SWARMER:
			body_radius = 10.0
			bar_color = Color(0.5, 0.9, 0.25, 0.95)
	var feet: Array = ARCHETYPE_FEET[archetype]
	sprite_base_y = body_radius * 0.75 - (float(feet[0]) - float(feet[1]) * 0.5) * visual_scale
	if sprite:
		sprite.sprite_frames = ARCHETYPE_FRAMES[archetype]
		sprite.modulate = base_modulate
		sprite.scale = Vector2.ONE * visual_scale
		sprite.position = Vector2(0.0, sprite_base_y)
		sprite.play(&"idle")
	var col := get_node_or_null("CollisionShape2D") as CollisionShape2D
	if col and col.shape is CircleShape2D:
		# The scene's shape sub-resource is shared between instances: give each enemy its own.
		var shp := (col.shape as CircleShape2D).duplicate() as CircleShape2D
		shp.radius = body_radius
		col.shape = shp

## Swarmer flank angle (Room passes -40, 0, +40 degrees for the three pack members).
func set_swarm_offset_deg(deg: float) -> void:
	swarm_offset_rad = deg_to_rad(deg)

## True during a telegraph phase (brute slam wind-up, skirmisher lunge tell, pyromancer charge).
func is_winding_up() -> bool:
	return current_state == State.WIND_UP or current_state == State.CHARGING

## True while the damaging phase of an attack is active (melee strike range, lunge, slam recovery).
func is_attacking() -> bool:
	return current_state == State.ATTACK or current_state == State.LUNGE

func configure_parameters(p_health: float, p_damage: float, p_speed: float, p_aggro: float) -> void:
	var m: Array = ARCHETYPE_MULTIPLIERS[archetype]
	max_health = p_health * m[0]
	attack_damage = p_damage * m[1]
	move_speed = p_speed * m[2]
	if archetype == Archetype.RANGED_PYROMANCER:
		aggro_radius = maxf(p_aggro, 420.0) # Room-wide casting vision
	else:
		aggro_radius = p_aggro * m[3]
		
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
				sprite.modulate = base_modulate
			
	if not is_instance_valid(player_ref):
		player_ref = get_tree().get_first_node_in_group("player")
		
	var move_velocity = Vector2.ZERO
	
	if player_ref:
		var dist_to_player = global_position.distance_to(player_ref.global_position)
		var dir_to_player = (player_ref.global_position - global_position).normalized()
		aim_direction = dir_to_player
		
		match archetype:
			Archetype.MELEE_CRAWLER:
				move_velocity = _process_crawler_ai(dist_to_player, dir_to_player, delta)
			Archetype.RANGED_PYROMANCER:
				move_velocity = _process_pyromancer_ai(dist_to_player, dir_to_player, delta)
			Archetype.HEAVY_BRUTE:
				move_velocity = _process_brute_ai(dist_to_player, dir_to_player, delta)
			Archetype.AGILE_SKIRMISHER:
				move_velocity = _process_skirmisher_ai(dist_to_player, dir_to_player, delta)
			Archetype.SWARMER:
				move_velocity = _process_swarmer_ai(dist_to_player, dir_to_player, delta)
	else:
		move_velocity = Vector2.ZERO
		current_state = State.WANDER
		
	# Decay Persistent Knockback Force
	if knockback_velocity != Vector2.ZERO:
		knockback_velocity = knockback_velocity.move_toward(Vector2.ZERO, knockback_decay * delta)
		
	# Apply Combined Velocity
	velocity = move_velocity + knockback_velocity
	
	# Sprite visual juice (the animation itself is chosen in _update_animation)
	if sprite:
		if abs(velocity.x) > 5.0:
			sprite.flip_h = (velocity.x < 0.0)
		var hover := 0.0
		if archetype == Archetype.MELEE_CRAWLER:
			if current_state == State.CHASE and not is_flashing:
				var scuttle = sin(Time.get_ticks_msec() / 65.0) * 0.06
				sprite.scale = Vector2(visual_scale * (1.0 + scuttle), visual_scale * (1.0 - scuttle))
			else:
				sprite.scale = Vector2.ONE * visual_scale
		elif archetype != Archetype.RANGED_PYROMANCER:
			_update_new_archetype_visuals()
		else:
			# Pyromancer floating levitation bob
			hover = sin(Time.get_ticks_msec() / 110.0) * 2.0
			if is_charging:
				# Pulsing yellow charging glow
				var glow = sin(Time.get_ticks_msec() / 40.0) * 0.4
				sprite.modulate = Color(1.8 + glow, 1.6 + glow, 0.4)
			elif not is_flashing:
				sprite.modulate = base_modulate
		sprite.position = Vector2(0.0, sprite_base_y + hover)
		_update_animation(delta)
		
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

## True if no wall lies between this enemy and the player. Re-evaluated at most every LOS_CHECK_INTERVAL.
func _can_see_player(delta: float) -> bool:
	_los_timer -= delta
	if _los_timer > 0.0:
		return _has_los
	_los_timer = LOS_CHECK_INTERVAL
	if not is_instance_valid(player_ref):
		_has_los = false
		return false
	var query := PhysicsRayQueryParameters2D.create(global_position, player_ref.global_position, WALL_MASK)
	query.collide_with_areas = false
	query.collide_with_bodies = true
	_has_los = get_world_2d().direct_space_state.intersect_ray(query).is_empty()
	return _has_los

func _process_pyromancer_ai(dist_to_player: float, dir_to_player: Vector2, delta: float) -> Vector2:
	var move_velocity = Vector2.ZERO
	var can_see := _can_see_player(delta)

	# Lost sight mid-cast (player ducked behind a wall): abort instead of firing into the wall.
	if is_charging and not can_see:
		is_charging = false
		charge_timer = 0.0

	if is_charging:
		current_state = State.CHARGING
		charge_timer += delta
		# Hold ground / slight drift while casting
		move_velocity = -dir_to_player * 18.0
		if charge_timer >= charge_duration:
			is_charging = false
			shoot_fireball(dir_to_player)
		return move_velocity
		
	# If player is outside aggro radius OR hidden behind a wall: Wander casually
	if dist_to_player > aggro_radius or not can_see:
		current_state = State.WANDER
		wander_timer -= delta
		if wander_timer <= 0.0:
			wander_timer = randf_range(2.0, 4.0)
			wander_direction = Vector2(randf_range(-1, 1), randf_range(-1, 1)).normalized()
		return wander_direction * (move_speed * 0.4)
		
	# Player is within aggro radius!
	# 1. Kiting Retreat: Player is too close (< 140px), back away to maintain distance
	if dist_to_player < standoff_min:
		current_state = State.KITE
		move_velocity = -dir_to_player * (move_speed * 1.15)
	# 2. Beyond preferred range (> 280px): Approach player
	elif dist_to_player > standoff_max:
		current_state = State.CHASE
		move_velocity = dir_to_player * move_speed
	# 3. In preferred standoff zone (140px - 280px): Strafe / hold ground
	else:
		current_state = State.ATTACK
		var strafe_dir = Vector2(-dir_to_player.y, dir_to_player.x)
		move_velocity = strafe_dir * 32.0
		
	# FIREBALL CAST TRIGGER:
	# Whenever cooldown is ready and player is within room aggro range, start charging!
	if attack_cooldown_timer <= 0.0 and dist_to_player <= aggro_radius:
		start_charging()
			
	return move_velocity

# ---------------------------------------------------------------------------
# HEAVY BRUTE: slow tank, telegraphed ground slam
# ---------------------------------------------------------------------------
func _process_brute_ai(dist_to_player: float, dir_to_player: Vector2, delta: float) -> Vector2:
	if current_state == State.WIND_UP:
		phase_timer += delta
		if phase_timer >= SLAM_WINDUP:
			_do_slam()
			return Vector2.ZERO
		# Lumbering step-in: close to ~70 px so a player who stands still is inside the 90 px
		# radius at impact, while a player who moves away is not (the slam is dodgeable).
		var step := minf(maxf(dist_to_player - 70.0, 0.0) / SLAM_WINDUP, 110.0)
		return dir_to_player * step
	if current_state == State.ATTACK and phase_timer > 0.0:
		# Post-slam recovery: planted for a moment
		phase_timer -= delta
		return Vector2.ZERO
	if dist_to_player <= SLAM_TRIGGER_RANGE and attack_cooldown_timer <= 0.0:
		current_state = State.WIND_UP
		phase_timer = 0.0
		emit_signal("attack_windup_started", &"slam")
		return Vector2.ZERO
	if dist_to_player <= aggro_radius or dist_to_player <= SLAM_TRIGGER_RANGE:
		if dist_to_player > 55.0:
			current_state = State.CHASE
			return dir_to_player * move_speed
		current_state = State.CHASE
		return -dir_to_player * 40.0 if dist_to_player < 40.0 else Vector2.ZERO
	return _wander(delta)

func _do_slam() -> void:
	attack_cooldown_timer = SLAM_COOLDOWN
	current_state = State.ATTACK
	phase_timer = SLAM_RECOVER
	if is_instance_valid(player_ref):
		var d := global_position.distance_to(player_ref.global_position)
		if d <= SLAM_RADIUS and player_ref.has_method("take_damage"):
			player_ref.take_damage(attack_damage, (player_ref.global_position - global_position).normalized())
	var wave := SlamShockwave.new()
	wave.setup(SLAM_RADIUS, 0.4, Color(1.0, 0.45, 0.2))
	if get_parent():
		get_parent().add_child(wave)
		wave.global_position = global_position
	emit_signal("attack_impact", &"slam")

# ---------------------------------------------------------------------------
# AGILE SKIRMISHER: orbit -> telegraph -> lunge -> retreat
# ---------------------------------------------------------------------------
func _lunge_travel() -> float:
	return move_speed * LUNGE_SPEED_MULT * LUNGE_DURATION

func _process_skirmisher_ai(dist_to_player: float, dir_to_player: Vector2, delta: float) -> Vector2:
	if current_state == State.WIND_UP:
		phase_timer += delta
		if phase_timer >= SKIRM_TELEGRAPH:
			current_state = State.LUNGE
			phase_timer = 0.0
			lunge_hit = false
			lunge_dir = dir_to_player
			attack_cooldown_timer = SKIRM_COOLDOWN
			emit_signal("attack_impact", &"lunge")
		return -dir_to_player * 15.0
	if current_state == State.LUNGE:
		phase_timer += delta
		if not lunge_hit and dist_to_player < 40.0 and player_ref and player_ref.has_method("take_damage"):
			lunge_hit = true
			player_ref.take_damage(attack_damage, lunge_dir)
			apply_knockback(-lunge_dir * 120.0)
		if phase_timer >= LUNGE_DURATION:
			current_state = State.RETREAT
			phase_timer = 0.0
		return lunge_dir * move_speed * LUNGE_SPEED_MULT
	if current_state == State.RETREAT:
		phase_timer += delta
		if phase_timer >= RETREAT_DURATION:
			current_state = State.ORBIT
			phase_timer = 0.0
		return -dir_to_player * move_speed
	if dist_to_player > aggro_radius:
		return _wander(delta)
	current_state = State.ORBIT
	orbit_switch_timer -= delta
	if orbit_switch_timer <= 0.0:
		orbit_switch_timer = randf_range(1.5, 3.0)
		orbit_dir = -orbit_dir
	var ready := attack_cooldown_timer <= 0.0
	# When ready, tighten the orbit so the lunge can actually reach the target.
	var target_r := orbit_radius
	var lunge_range := _lunge_travel() + 30.0
	if ready:
		target_r = clampf(lunge_range - 10.0, 60.0, orbit_radius)
		if dist_to_player <= minf(lunge_range, orbit_radius + 20.0):
			current_state = State.WIND_UP
			phase_timer = 0.0
			emit_signal("attack_windup_started", &"lunge")
			return Vector2.ZERO
	var tangent := Vector2(-dir_to_player.y, dir_to_player.x) * orbit_dir
	var radial := dir_to_player * clampf((dist_to_player - target_r) * 3.0, -move_speed, move_speed)
	return (tangent * move_speed * 0.9 + radial).limit_length(move_speed)

# ---------------------------------------------------------------------------
# SWARMER: pack member approaching on an offset angle, light bites
# ---------------------------------------------------------------------------
func _process_swarmer_ai(dist_to_player: float, dir_to_player: Vector2, delta: float) -> Vector2:
	if dist_to_player < 22.0:
		current_state = State.ATTACK
		if attack_cooldown_timer <= 0.0:
			_swarm_bite(dir_to_player)
		return -dir_to_player * 60.0
	if dist_to_player <= attack_reach:
		current_state = State.ATTACK
		if attack_cooldown_timer <= 0.0:
			_swarm_bite(dir_to_player)
		return Vector2.ZERO
	if dist_to_player <= aggro_radius:
		current_state = State.CHASE
		# Flank: offset the heading, fading the offset out as we close so the pack converges.
		var t := clampf((dist_to_player - 40.0) / 80.0, 0.0, 1.0)
		return dir_to_player.rotated(swarm_offset_rad * t) * move_speed
	return _wander(delta)

func _swarm_bite(dir_to_player: Vector2) -> void:
	attack_cooldown_timer = SWARM_BITE_RATE
	_strike_pose()
	if player_ref and player_ref.has_method("take_damage"):
		player_ref.take_damage(attack_damage, dir_to_player)
		apply_knockback(-dir_to_player * 140.0)
	emit_signal("attack_impact", &"bite")

func _wander(delta: float) -> Vector2:
	current_state = State.WANDER
	wander_timer -= delta
	if wander_timer <= 0.0:
		wander_timer = randf_range(1.5, 3.5)
		wander_direction = Vector2(randf_range(-1, 1), randf_range(-1, 1)).normalized()
	return wander_direction * (move_speed * 0.45)

## Tint/scale feedback for the new archetypes (placeholder; replaced by animations later).
func _update_new_archetype_visuals() -> void:
	var s := visual_scale
	if is_flashing:
		sprite.scale = Vector2.ONE * s
		return
	match current_state:
		State.WIND_UP:
			var f := 0.5 + 0.5 * sin(Time.get_ticks_msec() / 35.0)
			sprite.modulate = base_modulate.lerp(Color(2.0, 1.6, 1.0), f * 0.8)
			var squash := 1.0 + 0.08 * f
			sprite.scale = Vector2(s * squash, s / squash)
		State.LUNGE:
			sprite.modulate = base_modulate.lerp(Color.WHITE, 0.5)
			sprite.scale = Vector2(s * 1.25, s * 0.8)
		State.CHASE, State.ORBIT:
			sprite.modulate = base_modulate
			var bob := sin(Time.get_ticks_msec() / 70.0) * 0.07
			sprite.scale = Vector2(s * (1.0 + bob), s * (1.0 - bob))
		_:
			sprite.modulate = base_modulate
			sprite.scale = Vector2.ONE * s

## True while the sprite should show its attack/telegraph pose.
func _is_attack_pose() -> bool:
	if attack_anim_timer > 0.0 or is_winding_up() or current_state == State.LUNGE:
		return true
	# Brute slam recovery (planted after the impact)
	return archetype == Archetype.HEAVY_BRUTE and current_state == State.ATTACK and phase_timer > 0.0

## Chooses the animation from game state (hurt > attack > move > idle) and lunges the sprite
## toward the target during one-shot strikes. Safe to call without a player.
func _update_animation(delta: float) -> void:
	if not sprite or is_dying:
		return
	if attack_anim_timer > 0.0:
		attack_anim_timer = maxf(0.0, attack_anim_timer - delta)
		var p := 1.0 - attack_anim_timer / ATTACK_ANIM_TIME
		sprite.position += aim_direction * 5.0 * sin(PI * p)
	var want: StringName = &"idle"
	if is_flashing:
		want = &"hurt"
	elif _is_attack_pose():
		want = &"attack"
	elif velocity.length() > 12.0:
		want = &"move"
	if sprite.animation != want:
		sprite.play(want)
	elif not sprite.is_playing() and sprite.sprite_frames.get_animation_loop(want):
		sprite.play(want)

func _strike_pose() -> void:
	attack_anim_timer = ATTACK_ANIM_TIME
	if sprite and sprite.sprite_frames and not is_dying:
		sprite.play(&"attack")

func _begin_death() -> void:
	is_dying = true
	is_charging = false
	remove_from_group("enemies")
	collision_layer = 0
	collision_mask = 0
	var col := get_node_or_null("CollisionShape2D") as CollisionShape2D
	if col:
		col.set_deferred("disabled", true)
	velocity = Vector2.ZERO
	if sprite:
		sprite.play(&"death")
		sprite.modulate = Color(2.5, 2.2, 2.2)
	var tw := create_tween().set_parallel(true)
	tw.tween_property(self, "modulate:a", 0.0, DEATH_ANIM_TIME).set_ease(Tween.EASE_IN)
	if sprite:
		tw.tween_property(sprite, "scale", Vector2(visual_scale * 1.25, visual_scale * 0.15), DEATH_ANIM_TIME).set_ease(Tween.EASE_IN)
		tw.tween_property(sprite, "position:y", sprite_base_y + 8.0 * visual_scale, DEATH_ANIM_TIME).set_ease(Tween.EASE_IN)
	tw.chain().tween_callback(queue_free)
	queue_redraw()

func start_charging() -> void:
	is_charging = true
	charge_timer = 0.0
	current_state = State.CHARGING

func shoot_fireball(target_dir: Vector2) -> void:
	attack_cooldown_timer = attack_rate
	attack_anim_timer = 0.2
	if projectile_scene:
		var p = projectile_scene.instantiate()
		var spawn_pos = global_position + target_dir * 28.0
		get_parent().add_child(p)
		p.setup(target_dir, spawn_pos, attack_damage, 240.0)
		apply_knockback(-target_dir * 90.0)

func apply_knockback(impulse: Vector2) -> void:
	knockback_velocity = impulse * knockback_scale

func perform_attack() -> void:
	attack_cooldown_timer = attack_rate
	_strike_pose()
	if player_ref and player_ref.has_method("take_damage"):
		var attack_dir = (player_ref.global_position - global_position).normalized()
		player_ref.take_damage(attack_damage, attack_dir)
		apply_knockback(-attack_dir * 180.0)

func take_damage(amount: float, from_dir: Vector2 = Vector2.ZERO) -> void:
	if current_health <= 0 or is_dying:
		return
		
	current_health -= amount
	is_flashing = true
	flash_timer = 0.14
	if sprite:
		sprite.modulate = Color(2.5, 2.2, 2.2) # Crisp hurt flash
		if current_health > 0:
			sprite.play(&"hurt")
		
	emit_signal("enemy_damaged", amount, global_position)
	
	# If hit during early charge, brief interrupt; otherwise finishes casting
	if is_charging and charge_timer < charge_duration * 0.5:
		is_charging = false
		attack_cooldown_timer = 0.35
		
	# Apply persistent knockback impulse away from weapon hit
	if from_dir != Vector2.ZERO:
		apply_knockback(from_dir * 420.0)
		
	if current_health <= 0:
		# Signal immediately (room-clear logic unchanged); the corpse then plays its death
		# animation inertly (no collision, no damage, out of the "enemies" group) and frees itself.
		emit_signal("enemy_defeated", self)
		_begin_death()

## Instantly defeats this enemy (used by the Defense Panel's testing toggle).
func kill() -> void:
	take_damage(current_health)

func _draw() -> void:
	# Grounded contact shadow
	draw_set_transform(Vector2(0, body_radius * 0.75), 0.0, Vector2(1.0, 0.42))
	draw_circle(Vector2.ZERO, body_radius * 0.95, Color(0, 0, 0, 0.45))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	if is_dying:
		return
	
	# Ground telegraphs for the new archetypes (drawn in world scale even if the node is scaled).
	var inv: float = 1.0 / maxf(absf(scale.x), 0.01)
	if archetype == Archetype.HEAVY_BRUTE and current_state == State.WIND_UP:
		var p := clampf(phase_timer / SLAM_WINDUP, 0.0, 1.0)
		var r := SLAM_RADIUS * inv
		draw_circle(Vector2.ZERO, r * p, Color(1.0, 0.2, 0.1, 0.12 + 0.28 * p))
		draw_arc(Vector2.ZERO, r, 0, TAU, 48, Color(1.0, 0.25, 0.1, 0.35 + 0.45 * p), 3.0 * inv)
		draw_arc(Vector2.ZERO, r * p, 0, TAU, 48, Color(1.0, 0.8, 0.3, 0.9), 2.0 * inv)
	elif archetype == Archetype.AGILE_SKIRMISHER and current_state == State.WIND_UP:
		var tp := clampf(phase_timer / SKIRM_TELEGRAPH, 0.0, 1.0)
		draw_line(Vector2.ZERO, aim_direction * _lunge_travel() * inv, Color(0.3, 1.0, 0.95, 0.4 + 0.5 * tp), 3.0 * inv)
	
	if archetype in [Archetype.HEAVY_BRUTE, Archetype.AGILE_SKIRMISHER, Archetype.SWARMER]:
		pass
	elif archetype == Archetype.MELEE_CRAWLER:
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
			draw_line(Vector2.ZERO, aim_direction * (32.0 + charge_progress * 28.0), Color(1.0, 0.6, 0.1, 0.85), 2.5)
			# Fiery core burst
			draw_circle(Vector2.ZERO, 10.0 + charge_progress * 6.0, Color(1.0, 0.4, 0.05, 0.4))
		elif current_state == State.CHASE or current_state == State.KITE or current_state == State.ATTACK:
			# Ambient warm ember aura
			draw_arc(Vector2.ZERO, 22.0 + pulse_fire, 0, TAU, 24, Color(1.0, 0.45, 0.1, 0.4), 2.0)
	
	# Beveled dark health bar with crimson-orange gradient
	if current_health < max_health:
		var bar_w = 34.0 if archetype != Archetype.HEAVY_BRUTE else 48.0
		if archetype == Archetype.SWARMER:
			bar_w = 20.0
		var bar_h = 5.0
		var bar_y = -(body_radius + 10.0) * (1.0 if archetype != Archetype.HEAVY_BRUTE else 1.25)
		# Dark steel backing border
		draw_rect(Rect2(-bar_w/2 - 1.5, bar_y - 1.5, bar_w + 3.0, bar_h + 3.0), Color(0.06, 0.06, 0.09, 0.95))
		draw_rect(Rect2(-bar_w/2, bar_y, bar_w, bar_h), Color(0.2, 0.08, 0.1, 0.9))
		var hp_ratio = clampf(current_health / max_health, 0.0, 1.0)
		var fill_w = bar_w * hp_ratio
		if fill_w > 0:
			var hp_color = bar_color
			draw_rect(Rect2(-bar_w/2, bar_y, fill_w, bar_h), hp_color)
			draw_line(Vector2(-bar_w/2, bar_y + 1), Vector2(-bar_w/2 + fill_w, bar_y + 1), Color(1.0, 0.7, 0.6, 0.7), 1.0)
