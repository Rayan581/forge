# tests/render_ingame.gd - NOT part of the CI suite. Renders a staged frame of a real generated
# floor (player, all 5 archetypes, flasks, spikes) to a PNG. Needs a display, e.g.
#   xvfb-run -a -s "-screen 0 1280x720x24" godot --rendering-driver opengl3 --path godot_prototype \
#       --script res://tests/render_ingame.gd -- /home/claude/forge-plan/screens/visuals_ingame.png
extends SceneTree

func _initialize() -> void:
	_run()

func _run() -> void:
	var out := "/tmp/visuals_ingame.png"
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		out = args[0]
	seed(7)
	var main: Main = load("res://scenes/Main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	main._on_start_run_requested()
	for i in 12:
		await process_frame
	main.level_splash.dismiss_banner()
	main.defense_overlay.visible = false
	main.main_menu.visible = false
	main.level_splash.visible = false
	var p: Player = main.player
	var room: Room = null
	for r in main.dungeon_container.get_children():
		if r is Room and r.room_data.grid_pos == main.current_player_room_pos:
			room = r
	var cont: Node2D = room.entities_container
	for c in cont.get_children():
		c.queue_free()
	await process_frame
	var base := p.global_position
	var lineup := [
		[Enemy.Archetype.MELEE_CRAWLER, Vector2(-170, -40)],
		[Enemy.Archetype.RANGED_PYROMANCER, Vector2(-90, -90)],
		[Enemy.Archetype.HEAVY_BRUTE, Vector2(150, -50)],
		[Enemy.Archetype.AGILE_SKIRMISHER, Vector2(90, 90)],
		[Enemy.Archetype.SWARMER, Vector2(-120, 80)],
		[Enemy.Archetype.SWARMER, Vector2(-90, 105)],
		[Enemy.Archetype.SWARMER, Vector2(-150, 105)],
		[Enemy.Archetype.MELEE_CRAWLER, Vector2(60, -110)],
	]
	var es: Array = []
	for item in lineup:
		var e: Enemy = load("res://scenes/Enemy.tscn").instantiate()
		e.set_archetype(item[0])
		e.configure_parameters(60.0, 20.0, 125.0, 240.0)
		cont.add_child(e)
		e.global_position = base + item[1]
		e.set_physics_process(false)
		es.append(e)
	es[2].current_health = es[2].max_health * 0.6
	for pos in [Vector2(-40, 60), Vector2(30, 70)]:
		var hz = load("res://scenes/Hazard.tscn").instantiate()
		cont.add_child(hz)
		hz.global_position = base + pos
	for pos in [Vector2(60, 20), Vector2(-60, -10)]:
		var pk = load("res://scenes/Pickup.tscn").instantiate()
		cont.add_child(pk)
		pk.global_position = base + pos
	# poses
	es[1].sprite.play(&"move"); es[3].sprite.play(&"move"); es[0].sprite.play(&"move")
	await create_timer(0.35).timeout
	var shots := {"": 0.0, "_attack": 0.0}
	await RenderingServer.frame_post_draw
	root.get_viewport().get_texture().get_image().save_png(out)
	# attack frame: swing toward the right side
	p.perform_attack()
	await create_timer(0.14).timeout
	await RenderingServer.frame_post_draw
	root.get_viewport().get_texture().get_image().save_png(out.replace(".png", "_attack.png"))
	quit(0)
