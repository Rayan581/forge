# tests/test_enemy_archetypes.gd
# Behaviour test for all 5 enemy archetypes against a dummy player that records take_damage().
# Uses real physics frames (needed for the pyromancer fireball Area2D). (real time)
# Runs in real time (~30 s).
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_enemy_archetypes.gd
extends SceneTree

var failures: Array[String] = []
var DummyScript: GDScript
var enemy_scene: PackedScene

func _initialize() -> void:
	Engine.time_scale = 1.0
	DummyScript = GDScript.new()
	DummyScript.source_code = """extends Player
var hits: Array = []
func take_damage(amount: float, from_dir: Vector2 = Vector2.ZERO) -> void:
	hits.append(amount)
"""
	DummyScript.reload()
	enemy_scene = load("res://scenes/Enemy.tscn")
	_run()

func _fail(msg: String) -> void:
	failures.append(msg)
	printerr("[FORGE TEST] FAIL: " + msg)

func _make_dummy(pos: Vector2) -> CharacterBody2D:
	var d: CharacterBody2D = DummyScript.new()
	var shp := CollisionShape2D.new()
	var c := CircleShape2D.new()
	c.radius = 16.0
	shp.shape = c
	shp.name = "CollisionShape2D"
	d.add_child(shp)
	d.add_to_group("player")
	d.position = pos
	return d

func _spawn(arch: int, dist: float, dummy_out: Array) -> Enemy:
	var world := Node2D.new()
	root.add_child(world)
	var d := _make_dummy(Vector2(dist, 0))
	world.add_child(d)
	d.set_physics_process(false)
	var e: Enemy = enemy_scene.instantiate()
	e.set_archetype(arch)
	e.configure_parameters(60.0, 20.0, 125.0, 240.0)
	e.position = Vector2.ZERO
	world.add_child(e)
	dummy_out.append(d)
	dummy_out.append(world)
	return e

## Simulates up to max_sec. Returns {windup, attacking, hit_t, hits, impacts}.
func _simulate(e: Enemy, d, max_sec: float, stop_on_hit: bool = true) -> Dictionary:
	var res := {"windup": false, "attacking": false, "hit_t": -1.0, "impacts": 0}
	e.attack_impact.connect(func(_k): res.impacts += 1)
	var t := 0.0
	while t < max_sec:
		await physics_frame
		t += 1.0 / 60.0
		if not is_instance_valid(e):
			break
		if e.is_winding_up():
			res.windup = true
		if e.is_attacking():
			res.attacking = true
		if res.hit_t < 0.0 and d.hits.size() > 0:
			res.hit_t = t
			if stop_on_hit:
				break
	res["hits"] = d.hits.size()
	return res

func _run() -> void:
	var names := ["MELEE_CRAWLER", "RANGED_PYROMANCER", "HEAVY_BRUTE", "AGILE_SKIRMISHER", "SWARMER"]
	# arch, start distance, max seconds, must wind up?
	var cases := [
		[0, 150.0, 6.0, false], [1, 200.0, 8.0, true], [2, 180.0, 8.0, true],
		[3, 200.0, 8.0, true], [4, 150.0, 6.0, false]]
	for c in cases:
		var holder := []
		var e := _spawn(c[0], c[1], holder)
		var res: Dictionary = await _simulate(e, holder[0], c[2])
		var ok: bool = res.hit_t > 0.0 and (res.windup or res.attacking) and (res.windup or not c[3])
		print("[FORGE TEST] %-17s windup=%s attacking=%s first_hit=%.2fs hits=%d" % [
			names[c[0]], str(res.windup), str(res.attacking), res.hit_t, res.hits])
		if not ok:
			_fail("%s did not reach attack state / damage the dummy within %.0fs" % [names[c[0]], c[2]])
		holder[1].queue_free()
		await process_frame

	# Brute slam: lands (and hits) when the target stays inside 90 px
	var h1 := []
	var b := _spawn(2, 100.0, h1)
	var r1: Dictionary = await _simulate(b, h1[0], 3.0, false)
	print("[FORGE TEST] brute slam, target inside: hits=%d impacts=%d first_hit=%.2fs" % [r1.hits, r1.impacts, r1.hit_t])
	if r1.hits != 1 or r1.impacts != 1:
		_fail("brute slam should hit once inside 90px (hits=%d impacts=%d)" % [r1.hits, r1.impacts])
	if r1.hit_t < 0.6 or r1.hit_t > 1.1:
		_fail("brute wind-up should be ~0.7s (first hit at %.2fs)" % r1.hit_t)
	if is_instance_valid(b) and b.knockback_scale != 0.3:
		_fail("brute knockback scale != 0.3")
	h1[1].queue_free()
	await process_frame

	# Brute slam misses a target that leaves the 90 px radius during the wind-up
	var h2 := []
	var b2 := _spawn(2, 100.0, h2)
	var elapsed := 0.0
	var saw_windup := false
	var imp := {"n": 0}
	b2.attack_impact.connect(func(_k): imp.n += 1)
	while elapsed < 2.0:
		await physics_frame
		elapsed += 1.0 / 60.0
		if b2.is_winding_up() and not saw_windup:
			saw_windup = true
			h2[0].position = Vector2(b2.position.x + 200.0, 0.0)  # step out of range
	var impacts: int = imp.n
	print("[FORGE TEST] brute slam, target outside: windup=%s impacts=%d hits=%d" % [str(saw_windup), impacts, h2[0].hits.size()])
	if not saw_windup or impacts < 1:
		_fail("brute never slammed in the miss test")
	if h2[0].hits.size() != 0:
		_fail("brute slam hit a target outside 90px")
	h2[1].queue_free()
	await process_frame

	# Knockback resistance
	var cr: Enemy = enemy_scene.instantiate()
	var br: Enemy = enemy_scene.instantiate()
	br.set_archetype(2)
	root.add_child(cr)
	root.add_child(br)
	cr.apply_knockback(Vector2(100, 0))
	br.apply_knockback(Vector2(100, 0))
	if absf(br.knockback_velocity.x - 30.0) > 0.01 or absf(cr.knockback_velocity.x - 100.0) > 0.01:
		_fail("knockback scaling wrong (brute %.1f, crawler %.1f)" % [br.knockback_velocity.x, cr.knockback_velocity.x])
	cr.queue_free()
	br.queue_free()

	if failures.is_empty():
		print("[FORGE TEST] test_enemy_archetypes: PASS")
		quit(0)
	else:
		quit(1)
