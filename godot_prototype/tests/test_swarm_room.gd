# tests/test_swarm_room.gd
# Room-level archetype behaviour: a SWARMER slot spawns 3 bodies (each counted in enemies_alive),
# the room clears only after all 3 die, slot sampling follows the mix, spawns respect room bounds,
# and the Floor-5 exit-room apex champion is a buffed HEAVY_BRUTE.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_swarm_room.gd
extends SceneTree

var failures: Array[String] = []

func _fail(msg: String) -> void:
	failures.append(msg)
	printerr("[FORGE TEST] FAIL: " + msg)

func _make_room(slots: int, mix: Array, room_type = DungeonGenerator.RoomType.COMBAT, hp: float = 60.0) -> Room:
	var room: Room = load("res://scenes/Room.tscn").instantiate()
	root.add_child(room)
	var dm := DifficultyManager.new()
	dm.set_archetype_mix(mix)
	dm.enemy_health = hp
	var rd := DungeonGenerator.RoomData.new()
	rd.room_type = room_type
	rd.doors = {"N": true, "S": true, "E": true, "W": true}
	rd.enemies_count = slots
	room.initialize_room(rd, dm)
	return room

func _enemies(room: Room) -> Array:
	var out: Array = []
	for c in room.entities_container.get_children():
		if c is Enemy:
			out.append(c)
	return out

func _initialize() -> void:
	_run()

func _run() -> void:
	await process_frame
	# (e) one swarmer slot -> 3 bodies, room clears only after all three die
	var room := _make_room(1, [0, 0, 0, 0, 1.0])
	var cleared := {"n": 0}
	room.room_cleared.connect(func(_r): cleared.n += 1)
	var es := _enemies(room)
	if es.size() != 3 or room.enemies_alive != 3:
		_fail("swarmer slot should spawn 3 bodies (got %d, alive=%d)" % [es.size(), room.enemies_alive])
	var offs := []
	for e in es:
		if e.archetype != Enemy.Archetype.SWARMER:
			_fail("swarm body has wrong archetype")
		offs.append(snappedf(rad_to_deg(e.swarm_offset_rad), 0.1))
		if absf(e.position.x) > room.room_width / 2 - 79.0 or absf(e.position.y) > room.room_height / 2 - 79.0:
			_fail("swarm body spawned too close to walls: %s" % str(e.position))
	offs.sort()
	if offs != [-40.0, 0.0, 40.0]:
		_fail("swarm offsets should be -40/0/+40 deg, got %s" % str(offs))
	es[0].kill()
	es[1].kill()
	if cleared.n != 0 or room.room_data.is_cleared or room.enemies_alive != 1:
		_fail("room cleared early after 2 of 3 swarmers (alive=%d)" % room.enemies_alive)
	es[2].kill()
	if cleared.n != 1 or not room.room_data.is_cleared or room.enemies_alive != 0:
		_fail("room did not clear after all 3 swarmers died")
	print("[FORGE TEST] (e) swarmer slot -> 3 bodies, clears after the 3rd kill")

	# Mixed slots: bodies = slots + 2 * swarmer slots; non-swarm slots spawn 1 body
	var room2 := _make_room(6, [0.5, 0, 0, 0.5, 0])
	if _enemies(room2).size() != 6 or room2.enemies_alive != 6:
		_fail("non-swarm slots should spawn exactly 1 body each")
	room2.kill_all_enemies()
	if room2.enemies_alive != 0 or not room2.room_data.is_cleared:
		_fail("kill_all_enemies should clear the room")

	# Sampling at room level: brute-only mix spawns brutes
	var room3 := _make_room(4, [0, 0, 1.0, 0, 0])
	for e in _enemies(room3):
		if e.archetype != Enemy.Archetype.HEAVY_BRUTE:
			_fail("brute-only mix produced a non-brute")
	print("[FORGE TEST] mixed-slot and mix-sampling checks done")

	# Floor-5 apex champion: first slot in the EXIT room is a buffed brute
	var room4 := _make_room(3, [1.0, 0, 0, 0, 0], DungeonGenerator.RoomType.EXIT, 90.0)
	var champ: Enemy = _enemies(room4)[0]
	var want_hp := 90.0 * 2.0 * 1.7
	if champ.archetype != Enemy.Archetype.HEAVY_BRUTE or absf(champ.max_health - want_hp) > 0.01 \
			or absf(champ.attack_damage - 30.0 * 0.0 - champ.attack_damage) > 0.0 or absf(champ.scale.x - 1.28) > 1e-4:
		_fail("apex champion wrong: arch=%d hp=%.1f (want %.1f) scale=%.2f" % [champ.archetype, champ.max_health, want_hp, champ.scale.x])
	if absf(champ.attack_damage - 20.0 * 1.4 * 1.25) > 0.01:
		_fail("apex champion damage %.2f != %.2f" % [champ.attack_damage, 20.0 * 1.4 * 1.25])
	print("[FORGE TEST] apex champion: brute hp=%.1f dmg=%.1f scale=%.2f" % [champ.max_health, champ.attack_damage, champ.scale.x])

	if failures.is_empty():
		print("[FORGE TEST] test_swarm_room: PASS")
		quit(0)
	else:
		quit(1)
