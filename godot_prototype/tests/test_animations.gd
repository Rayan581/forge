# tests/test_animations.gd
# Checks that Player and every enemy archetype use an AnimatedSprite2D with the required
# animations, and that move / attack / hurt / death actually switch the playing animation.
# Also checks the enemy death contract: enemy_defeated fires immediately, the corpse is inert
# (no collision, not in the "enemies" group) and frees itself after the death animation.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_animations.gd
extends SceneTree

const REQUIRED := [&"idle", &"move", &"attack", &"hurt", &"death"]
var failures: Array[String] = []

func _initialize() -> void:
	_run()

func _fail(msg: String) -> void:
	failures.append(msg)
	printerr("[FORGE TEST] FAIL: " + msg)

func _check(cond: bool, msg: String) -> void:
	if not cond:
		_fail(msg)

func _check_frames(label: String, spr: AnimatedSprite2D) -> void:
	if spr == null or spr.sprite_frames == null:
		_fail("%s: no AnimatedSprite2D/sprite_frames" % label)
		return
	for a in REQUIRED:
		if not spr.sprite_frames.has_animation(a):
			_fail("%s: missing animation %s" % [label, a])
		elif spr.sprite_frames.get_frame_count(a) < 1:
			_fail("%s: animation %s has no frames" % [label, a])
	_check(spr.sprite_frames.get_animation_loop(&"idle") and spr.sprite_frames.get_animation_loop(&"move"),
		"%s: idle/move must loop" % label)

func _run() -> void:
	await _test_player()
	for arch in range(5):
		await _test_enemy(arch)
	await _test_props()
	if failures.is_empty():
		print("[FORGE TEST] PASS: animations")
		quit(0)
	else:
		printerr("[FORGE TEST] FAIL: %d problem(s)" % failures.size())
		quit(1)

func _test_player() -> void:
	var world := Node2D.new()
	root.add_child(world)
	var p: Player = load("res://scenes/Player.tscn").instantiate()
	world.add_child(p)
	await process_frame
	_check_frames("Player", p.sprite)
	if p.sprite == null:
		return
	_check(p.sprite.animation == &"idle", "Player starts in idle")
	p.is_moving = true
	p._update_animation()
	_check(p.sprite.animation == &"move", "Player moving -> move (got %s)" % p.sprite.animation)
	p.is_moving = false
	p._update_animation()
	_check(p.sprite.animation == &"idle", "Player stopped -> idle")
	# Attack: animation switches, hit lands on the arc frame (0.1 s), cooldown unchanged
	var e: Enemy = load("res://scenes/Enemy.tscn").instantiate()
	e.position = Vector2(0, -40) # headless mouse sits straight above the player
	world.add_child(e)
	e.set_physics_process(false)
	for i in 4:
		await physics_frame
	var hp0 := e.current_health
	p.perform_attack()
	_check(p.sprite.animation == &"attack", "Player attack -> attack (got %s)" % p.sprite.animation)
	_check(is_equal_approx(e.current_health, hp0), "Player hit must not land before the arc frame")
	await create_timer(0.25).timeout
	_check(e.current_health < hp0, "Player attack hit lands after the arc frame delay")
	_check(not p.can_attack, "Player attack cooldown still running at 0.25 s (0.35 s total)")
	await create_timer(0.2).timeout
	_check(p.can_attack, "Player attack cooldown ends at attack_cooldown")
	e.queue_free()
	p.attack_anim_timer = 0.0
	p.is_invulnerable = false
	p.take_damage(10.0, Vector2.RIGHT)
	_check(p.sprite.animation == &"hurt", "Player damaged -> hurt (got %s)" % p.sprite.animation)
	p.hurt_anim_timer = 0.0
	p.is_invulnerable = false
	p.take_damage(1000.0)
	_check(p.sprite.animation == &"death", "Player dead -> death (got %s)" % p.sprite.animation)
	p._update_animation()
	_check(p.sprite.animation == &"death", "Player stays in death")
	world.queue_free()

func _test_enemy(arch: int) -> void:
	var world := Node2D.new()
	root.add_child(world)
	var e: Enemy = load("res://scenes/Enemy.tscn").instantiate()
	e.set_archetype(arch)
	e.configure_parameters(60.0, 20.0, 125.0, 240.0)
	world.add_child(e)
	e.set_physics_process(false)
	await process_frame
	var label := "Enemy[%d]" % arch
	_check_frames(label, e.sprite)
	if e.sprite == null:
		return
	_check(e.sprite.sprite_frames == Enemy.ARCHETYPE_FRAMES[arch], "%s uses its own SpriteFrames" % label)
	_check(e.is_in_group("enemies"), "%s in enemies group" % label)
	# idle -> move
	e.velocity = Vector2.ZERO
	e._update_animation(0.0)
	_check(e.sprite.animation == &"idle", "%s idle (got %s)" % [label, e.sprite.animation])
	e.velocity = Vector2(100, 0)
	e._update_animation(0.0)
	_check(e.sprite.animation == &"move", "%s moving -> move (got %s)" % [label, e.sprite.animation])
	# attack
	e.velocity = Vector2.ZERO
	e._strike_pose()
	_check(e.sprite.animation == &"attack", "%s strike -> attack (got %s)" % [label, e.sprite.animation])
	e.attack_anim_timer = 0.0
	if arch == Enemy.Archetype.HEAVY_BRUTE or arch == Enemy.Archetype.AGILE_SKIRMISHER:
		e.current_state = Enemy.State.WIND_UP
		e._update_animation(0.0)
		_check(e.sprite.animation == &"attack", "%s wind-up -> attack" % label)
		e.current_state = Enemy.State.WANDER
	elif arch == Enemy.Archetype.RANGED_PYROMANCER:
		e.current_state = Enemy.State.CHARGING
		e._update_animation(0.0)
		_check(e.sprite.animation == &"attack", "%s charging -> attack" % label)
		e.current_state = Enemy.State.WANDER
	# hurt
	var defeated := [0]
	e.enemy_defeated.connect(func(_n): defeated[0] += 1)
	e.take_damage(1.0, Vector2.RIGHT)
	_check(e.sprite.animation == &"hurt", "%s damaged -> hurt (got %s)" % [label, e.sprite.animation])
	_check(not e.is_dying, "%s survives a 1 hp hit" % label)
	# death
	e.take_damage(99999.0)
	_check(defeated[0] == 1, "%s enemy_defeated emitted exactly once, immediately" % label)
	_check(e.is_dying and e.sprite.animation == &"death", "%s dead -> death (got %s)" % [label, e.sprite.animation])
	_check(e.collision_layer == 0 and e.collision_mask == 0, "%s corpse has no collision" % label)
	_check(not e.is_in_group("enemies"), "%s corpse leaves the enemies group" % label)
	e.take_damage(10.0)
	_check(defeated[0] == 1, "%s corpse cannot be defeated twice" % label)
	await create_timer(Enemy.DEATH_ANIM_TIME + 0.3).timeout
	_check(not is_instance_valid(e), "%s freed after death animation" % label)
	world.queue_free()

func _test_props() -> void:
	var pk: Pickup = load("res://scenes/Pickup.tscn").instantiate()
	var hz: Hazard = load("res://scenes/Hazard.tscn").instantiate()
	root.add_child(pk)
	root.add_child(hz)
	await process_frame
	_check(pk.sprite != null and pk.sprite.sprite_frames.get_frame_count(&"idle") == 4, "Pickup flask has 4 idle frames")
	_check(hz.sprite != null and hz.sprite.sprite_frames.has_animation(&"stab") and hz.sprite.sprite_frames.has_animation(&"idle"), "Hazard has idle+stab")
	pk.queue_free()
	hz.queue_free()
