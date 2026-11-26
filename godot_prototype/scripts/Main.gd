class_name Main
extends Node2D

var difficulty_manager: DifficultyManager
var telemetry_logger: TelemetryLogger
var dungeon_generator: DungeonGenerator
var ppo_policy: PPOPolicy

const POLICY_WEIGHTS_PATH := "res://ai/policy_weights.json"

var current_dungeon_level: int = 1
var active_rooms: Dictionary = {} # Vector2i -> Room
var current_player_room_pos: Vector2i = Vector2i.ZERO
var auto_kill_enabled: bool = false # Defense Panel testing toggle

# Camera Trauma Shake System
var camera_trauma: float = 0.0
var trauma_decay: float = 3.6 # Recovers 0.4 trauma in ~0.11s (crisp hit punch)
var max_shake_offset: Vector2 = Vector2(15.0, 11.0)
var max_shake_roll: float = 0.04

# Snapshot of telemetry + a clock at the moment the current level began
var level_start_time_msec: int = 0
var level_start_deaths: int = 0
var level_start_damage_taken: float = 0.0

var room_scene = preload("res://scenes/Room.tscn")
var damage_floater_scene = preload("res://scenes/DamageFloater.tscn")

@onready var player: Player = $Player
@onready var dungeon_container: Node2D = $DungeonContainer
@onready var defense_overlay: DefenseOverlay = $DefenseOverlay
@onready var camera: Camera2D = $Camera2D
@onready var level_splash: LevelSplash = $LevelSplash
@onready var main_menu: MainMenu = $MainMenu

var game_started: bool = false

# Playtest study: consent + post-floor difficulty rating (see GameSettings, ConsentScreen, FloorRating).
var settings: GameSettings
var floor_rating: FloorRating
var consent_screen: ConsentScreen = null
var pause_menu: PauseMenu
## True from the moment the exit portal is used until the next floor is built (blocks re-entry while
## the rating prompt / calibration banner is up).
var _floor_transition: bool = false

func _ready() -> void:
	difficulty_manager = DifficultyManager.new()
	# Initialize Level 1 calibration parameters
	difficulty_manager.apply_calibration_level(1)
	
	telemetry_logger = TelemetryLogger.new()
	settings = GameSettings.new().load_from_disk()
	telemetry_logger.consent_given = settings.consent_given
	dungeon_generator = DungeonGenerator.new()
	_apply_cmdline_mode()

	ppo_policy = PPOPolicy.new()
	ppo_policy.load_weights(POLICY_WEIGHTS_PATH) # falls back to rule-based heuristic if missing
	
	# Connect Player signals
	player.health_changed.connect(_on_player_health_changed)
	player.player_damaged.connect(_on_player_damaged)
	player.player_healed.connect(_on_player_healed)
	player.player_died.connect(_on_player_died)
	player.player_moved.connect(_on_player_moved)
	
	# Connect Defense Overlay signals
	defense_overlay.setup(difficulty_manager, telemetry_logger)
	defense_overlay.regenerate_room_requested.connect(_on_rebuild_dungeon_requested)
	defense_overlay.parameters_updated.connect(_on_parameters_updated)
	defense_overlay.auto_kill_toggled.connect(_on_auto_kill_toggled)
	
	# Connect Main Menu signals
	main_menu.start_run_requested.connect(_on_start_run_requested)
	main_menu.settings_changed.connect(_on_settings_changed)
	main_menu.setup(settings)

	floor_rating = FloorRating.new()
	add_child(floor_rating)
	pause_menu = PauseMenu.new()
	add_child(pause_menu)
	pause_menu.main_menu_requested.connect(_return_to_main_menu)
	pause_menu.quit_requested.connect(_quit_game)
	if not settings.consent_decided:
		_show_consent_screen()
	
	# Hide player completely until Start Run is clicked from Menu
	player.visible = false
	player.position = Vector2(-9999, -9999)
	player.set_physics_process(false)
	defense_overlay.visible = false

## `-- --mode=forge|static|bsp` picks the experimental condition for scripted runs (developer builds
## only; playtest builds always run FORGE). The Defense Panel can switch it too.
func _apply_cmdline_mode() -> void:
	for arg in OS.get_cmdline_user_args():
		if not arg.begins_with("--mode="):
			continue
		var mode: String = arg.substr(7).to_lower()
		if not BuildInfo.dev_tools_enabled():
			print("[FORGE] --mode=%s ignored in the playtest build (FORGE only)" % mode)
			return
		if mode not in [DifficultyManager.GENERATOR_FORGE, DifficultyManager.GENERATOR_STATIC, DifficultyManager.GENERATOR_BSP]:
			printerr("[FORGE] unknown --mode=%s (use forge, static or bsp)" % mode)
			return
		difficulty_manager.set_generator_mode(mode)
		if difficulty_manager.is_baseline_mode():
			difficulty_manager.apply_baseline(1)
		else:
			difficulty_manager.apply_calibration_level(1)
		print("[FORGE] generator mode: %s (command line)" % mode)

func _show_consent_screen() -> void:
	consent_screen = ConsentScreen.new()
	add_child(consent_screen)
	consent_screen.decided.connect(_on_consent_decided)

func _on_consent_decided(consent: bool) -> void:
	settings.set_consent(consent)
	consent_screen = null
	_on_settings_changed()

func _on_settings_changed() -> void:
	telemetry_logger.consent_given = settings.consent_given
	main_menu.refresh_settings()

## Esc during a run opens the pause menu (everything else that owns Esc is closed or handles it first).
func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("ui_cancel") or event.is_echo():
		return
	if _can_pause():
		pause_menu.open("Floor %d  ·  %s" % [current_dungeon_level, _fmt_time(telemetry_logger.elapsed_seconds)])
		get_viewport().set_input_as_handled()

func _can_pause() -> bool:
	return game_started and not _floor_transition and not pause_menu.is_open \
		and not floor_rating.is_open and consent_screen == null and not main_menu.visible \
		and not get_tree().paused

func _fmt_time(sec: float) -> String:
	var t := int(sec)
	return "%02d:%02d" % [t / 60, t % 60]

## Pause menu -> Return to Main Menu: store what was played, then start from a clean slate.
func _return_to_main_menu() -> void:
	pause_menu.close_silently()
	_save_session_if_played()
	telemetry_logger.start_new_session() # the next run is its own session
	if difficulty_manager.is_baseline_mode():
		difficulty_manager.apply_baseline(1)
	else:
		difficulty_manager.apply_calibration_level(1)
	defense_overlay.sync_ui_with_manager()
	for child in dungeon_container.get_children():
		child.queue_free()
	active_rooms.clear()
	game_started = false
	_floor_transition = false
	current_dungeon_level = 1
	level_splash.visible = false
	player.visible = false
	player.position = Vector2(-9999, -9999)
	player.set_physics_process(false)
	defense_overlay.visible = false
	main_menu.show_menu()

## Pause menu -> Quit Game.
func _quit_game() -> void:
	pause_menu.close_silently()
	_save_session_if_played()
	telemetry_logger.close()
	get_tree().quit()

func _save_session_if_played() -> void:
	if game_started and telemetry_logger.elapsed_seconds > 0.5:
		telemetry_logger.save_to_file()

## Closing the window mid-run keeps the data of the session so far.
func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST and telemetry_logger != null:
		_save_session_if_played()
		telemetry_logger.close()

func _on_start_run_requested() -> void:
	game_started = true
	floor_rating.reset_for_new_run() # "Don't ask again" lasts for one run only
	player.visible = true
	player.set_physics_process(true)
	defense_overlay.visible = true
	call_deferred("build_new_dungeon", 1)

func _process(delta: float) -> void:
	telemetry_logger.update_time(delta)
	telemetry_logger.record_frame(delta) # [telemetry] frame-time stats per floor
	defense_overlay.update_telemetry_ui()
	
	# Camera follows player smoothly with trauma shake
	if is_instance_valid(player):
		camera.global_position = player.global_position
		
		if camera_trauma > 0.0:
			camera_trauma = maxf(0.0, camera_trauma - trauma_decay * delta)
			var shake_amount = camera_trauma * camera_trauma
			camera.offset = Vector2(
				max_shake_offset.x * shake_amount * randf_range(-1.0, 1.0),
				max_shake_offset.y * shake_amount * randf_range(-1.0, 1.0)
			)
			camera.rotation = max_shake_roll * shake_amount * randf_range(-1.0, 1.0)
		else:
			camera.offset = Vector2.ZERO
			camera.rotation = 0.0

func add_camera_trauma(amount: float) -> void:
	camera_trauma = clampf(camera_trauma + amount, 0.0, 1.0)

func spawn_damage_floater(pos: Vector2, amount: float, is_player_damage: bool, is_heal: bool = false) -> void:
	var floater = damage_floater_scene.instantiate()
	floater.global_position = pos + Vector2(randf_range(-6.0, 6.0), -12.0)
	add_child(floater)
	floater.setup(amount, is_player_damage, is_heal)

func _on_player_damaged(amount: float) -> void:
	telemetry_logger.record_damage_taken(amount)
	add_camera_trauma(0.42) # Screen trauma punch on hit
	spawn_damage_floater(player.global_position, amount, true)

func _on_player_healed(amount: float) -> void:
	spawn_damage_floater(player.global_position, amount, false, true)

func _on_enemy_damaged(amount: float, pos: Vector2) -> void:
	telemetry_logger.record_damage_dealt(amount)
	spawn_damage_floater(pos, amount, false)

## rebuild = true regenerates the CURRENT floor (Defense Panel): telemetry keeps counting the same
## floor attempt instead of silently discarding what happened before the rebuild.
func build_new_dungeon(level_num: int, rebuild: bool = false) -> void:
	var same_floor_rebuild := rebuild and level_num == telemetry_logger.floor_num
	current_dungeon_level = level_num
	var is_calibrating = difficulty_manager.is_in_calibration(level_num)
	var cal_data: Dictionary = {}
	
	if is_calibrating:
		cal_data = difficulty_manager.apply_calibration_level(level_num)
	elif difficulty_manager.is_baseline_mode():
		difficulty_manager.apply_baseline(level_num)
	
	defense_overlay.sync_ui_with_manager()
	
	# Clear old rooms
	for child in dungeon_container.get_children():
		child.queue_free()
	active_rooms.clear()
	
	# 1. Procedurally generate dungeon layout on grid
	var room_count = difficulty_manager.room_count_target
	dungeon_generator.layout_mode = difficulty_manager.layout_mode()
	var generated_data = dungeon_generator.generate_dungeon(difficulty_manager, room_count)
	if dungeon_generator.layout_mode == DungeonGenerator.LAYOUT_BSP:
		difficulty_manager.room_count_target = generated_data.size() # BSP picks its own room count
	
	# 2. Instantiate Room scenes for each generated room
	for pos in generated_data.keys():
		var r_data = generated_data[pos]
		var r_inst = room_scene.instantiate()
		dungeon_container.add_child(r_inst)
		r_inst.telemetry_logger = telemetry_logger
		r_inst.initialize_room(r_data, difficulty_manager)
		
		# Connect room signals
		r_inst.room_entered.connect(_on_room_entered)
		r_inst.room_cleared.connect(_on_room_cleared)
		r_inst.enemy_killed.connect(_on_enemy_killed)
		r_inst.enemy_damaged_in_room.connect(_on_enemy_damaged)
		r_inst.player_hit_hazard.connect(_on_player_hit_hazard)
		r_inst.player_collected_pickup.connect(_on_pickup_collected)
		r_inst.dungeon_escaped.connect(_on_dungeon_escaped)
		
		active_rooms[pos] = r_inst
		
	# 3. Setup MiniMap
	var start_pos = dungeon_generator.start_room_pos
	current_player_room_pos = start_pos
	defense_overlay.setup_minimap(generated_data, start_pos)
	defense_overlay.update_room_info(current_dungeon_level, start_pos, is_calibrating)
	
	# 4. Place player in start room
	var start_world_pos = generated_data[start_pos].world_pos
	player.reset(start_world_pos)

	# 5. Snapshot the clock + telemetry for this level (a same-floor rebuild keeps the original
	#    snapshot, so time/deaths/damage cover the whole attempt and match the session totals)
	if same_floor_rebuild:
		telemetry_logger.restart_floor_layout(generated_data.size()) # [telemetry] keeps counters, flags override
	else:
		level_start_time_msec = Time.get_ticks_msec()
		level_start_deaths = telemetry_logger.total_deaths
		level_start_damage_taken = telemetry_logger.damage_taken
		telemetry_logger.begin_floor(level_num, generated_data.size()) # [telemetry] reset per-floor counters, rooms_total
	telemetry_logger.record_room_visited(start_pos) # [telemetry] the start room counts as visited
	_floor_transition = false

	# 6. Display Level Splash banner
	var diff_report = difficulty_manager.calculate_difficulty_score()
	if level_splash:
		level_splash.show_level_announcement(
			current_dungeon_level, is_calibrating, cal_data,
			diff_report.score, diff_report.label
		)

	# 7. Testing aid: Auto-Kill wipe if enabled
	if auto_kill_enabled:
		_kill_all_enemies_in_all_rooms()

func _on_room_entered(room_node: Room) -> void:
	if room_node and room_node.room_data:
		current_player_room_pos = room_node.room_data.grid_pos
		telemetry_logger.record_room_visited(current_player_room_pos) # [telemetry] exploration %
		defense_overlay.update_minimap_player(current_player_room_pos)
		var is_calibrating = difficulty_manager.is_in_calibration(current_dungeon_level)
		defense_overlay.update_room_info(current_dungeon_level, current_player_room_pos, is_calibrating)

func _on_room_cleared(_room_node: Room) -> void:
	telemetry_logger.record_room_cleared()
	telemetry_logger.save_to_file()
	defense_overlay.update_minimap_player(current_player_room_pos)

func _on_player_moved() -> void:
	if level_splash:
		level_splash.dismiss_banner()

func _on_player_health_changed(curr: float, max_val: float) -> void:
	defense_overlay.update_player_hp(curr, max_val)

func _on_player_died() -> void:
	add_camera_trauma(0.65) # Strong shake on death
	telemetry_logger.record_death()
	telemetry_logger.save_to_file()
	
	# Small delay then respawn in start room
	await get_tree().create_timer(1.2).timeout
	if not game_started:
		return # the player left to the main menu during the respawn delay
	var start_pos = dungeon_generator.start_room_pos
	if dungeon_generator.rooms.has(start_pos):
		var start_world_pos = dungeon_generator.rooms[start_pos].world_pos
		player.reset(start_world_pos)
		current_player_room_pos = start_pos
		defense_overlay.update_minimap_player(start_pos)
		var is_calibrating = difficulty_manager.is_in_calibration(current_dungeon_level)
		defense_overlay.update_room_info(current_dungeon_level, start_pos, is_calibrating)

func _on_dungeon_escaped() -> void:
	if _floor_transition:
		return
	_floor_transition = true
	# 1. Measure level performance
	var completion_time_sec = float(Time.get_ticks_msec() - level_start_time_msec) / 1000.0
	var deaths_this_level = telemetry_logger.total_deaths - level_start_deaths
	var damage_taken_this_level = telemetry_logger.damage_taken - level_start_damage_taken
	var diff_report = difficulty_manager.calculate_difficulty_score()

	# [telemetry] one row per finished floor: params this floor was played with + outcome
	telemetry_logger.record_floor(difficulty_manager, {
		"floor_num": current_dungeon_level,
		"completion_time": completion_time_sec,
		"deaths": deaths_this_level,
		"damage_taken": damage_taken_this_level,
		"player_max_hp": player.max_health,
		"difficulty_score": diff_report.score,
	})

	# Post-floor difficulty rating (pauses the game; only for players who agreed to share data)
	await _ask_floor_rating(current_dungeon_level)

	var next_level = current_dungeon_level + 1

	# Baselines: no calibration, no PPO. Static follows the fixed +8 % per floor rule; BSP keeps the
	# Intermediate preset on every floor and only the BSP layout changes.
	if difficulty_manager.is_baseline_mode():
		difficulty_manager.apply_baseline(next_level)
		defense_overlay.sync_ui_with_manager()
		if difficulty_manager.bsp_baseline_mode:
			print("[FORGE][BSP] Level %d cleared in %.1fs, %d deaths -> next: Intermediate preset, BSP layout" % [
				current_dungeon_level, completion_time_sec, deaths_this_level])
		else:
			print("[FORGE][STATIC] Level %d cleared in %.1fs, %d deaths -> next: hp=%.0f dmg=%.0f (x%.2f)" % [
				current_dungeon_level, completion_time_sec, deaths_this_level,
				difficulty_manager.enemy_health, difficulty_manager.enemy_damage,
				difficulty_manager.static_scale(next_level)
			])
		telemetry_logger.save_to_file()
		call_deferred("build_new_dungeon", next_level)
		return

	# Record calibration performance for floors 1 to 5
	if difficulty_manager.is_in_calibration(current_dungeon_level):
		telemetry_logger.record_calibration_floor(
			current_dungeon_level,
			completion_time_sec,
			deaths_this_level,
			damage_taken_this_level,
			difficulty_manager.room_count_target,
			diff_report.score
		)

	# Special milestone: Exiting Floor 5 finishes Cold-Start calibration!
	if current_dungeon_level == 5:
		var cr0_profile = telemetry_logger.compute_cr0_baseline(player.max_health)
		print("[FORGE][COLD-START] All 5 calibration floors complete!")
		print("[FORGE][COLD-START] Composite Initial Combat Rating CR0: %.1f/100 (%s)" % [
			cr0_profile.cr0_score, cr0_profile.tier_name
		])
		print("[FORGE][COLD-START] Weighted Metrics -> Pace: %.2f | Deaths: %.2f | Dmg: %.2f" % [
			cr0_profile.weighted_time_ratio, cr0_profile.weighted_death_ratio, cr0_profile.weighted_damage_ratio
		])
		
		# Show PPO Activation celebration banner
		if level_splash:
			level_splash.show_ppo_activation_banner()
			# Allow player to read the activation message before loading floor 6
			await get_tree().create_timer(2.4).timeout

		# Seed Floor 6 difficulty from the 5-level weighted CR0 profile
		var obs_s0 = difficulty_manager.build_observation_from_cr0(cr0_profile, 6)
		var initial_action = ppo_policy.predict(obs_s0)
		telemetry_logger.note_policy_step(obs_s0, initial_action) # [telemetry] obs/action behind floor 6
		difficulty_manager.apply_ppo_action(initial_action)
		defense_overlay.sync_ui_with_manager()

		print("[FORGE][PPO] Floor 6 seeded from CR0: rooms=%d hp=%.0f dmg=%.0f spd=%.0f haz=%.2f" % [
			difficulty_manager.room_count_target, difficulty_manager.enemy_health,
			difficulty_manager.enemy_damage, difficulty_manager.enemy_speed,
			difficulty_manager.hazard_density
		])

	# 2. PPO adaptation step for Floor 7 onward (online step-by-step rolling adaptation)
	elif next_level >= 7:
		var obs = difficulty_manager.build_observation(
			completion_time_sec, deaths_this_level, damage_taken_this_level,
			player.max_health, current_dungeon_level
		)
		var action = ppo_policy.predict(obs)
		telemetry_logger.note_policy_step(obs, action) # [telemetry] obs/action behind the next floor
		difficulty_manager.apply_ppo_action(action)
		defense_overlay.sync_ui_with_manager()

		print("[FORGE][PPO] Level %d cleared in %.1fs, %d deaths -> next: rooms=%d hp=%.0f dmg=%.0f haz=%.2f" % [
			current_dungeon_level, completion_time_sec, deaths_this_level,
			difficulty_manager.room_count_target, difficulty_manager.enemy_health,
			difficulty_manager.enemy_damage, difficulty_manager.hazard_density
		])
	else:
		print("[FORGE][CALIBRATION] Level %d completed in %.1fs with %d deaths. Advancing to Calibration Level %d." % [
			current_dungeon_level, completion_time_sec, deaths_this_level, next_level
		])

	# 3. Save telemetry snapshot and advance to next level
	telemetry_logger.save_to_file()
	call_deferred("build_new_dungeon", next_level)

## Shows the 1-5 "how hard did that floor feel?" prompt and stores the answer on the floor row.
func _ask_floor_rating(floor_num: int) -> void:
	if settings == null or floor_rating == null or not settings.should_ask_rating():
		return # no consent, or the player turned ratings off in the menu
	if floor_rating.stop_asking:
		return # the player ticked "Don't ask again" on an earlier floor of this run
	var value: int = await floor_rating.ask(floor_num)
	if value > 0:
		telemetry_logger.set_perceived_difficulty(floor_num, float(value))

func _on_enemy_killed() -> void:
	add_camera_trauma(0.18) # Satisfying tactile punch on kill
	telemetry_logger.record_enemy_defeated()

func _on_player_hit_hazard() -> void:
	add_camera_trauma(0.30)
	telemetry_logger.record_hazard_hit()

func _on_pickup_collected(_type: String) -> void:
	telemetry_logger.record_pickup_collected()

func _on_parameters_updated() -> void:
	pass

func _on_auto_kill_toggled(enabled: bool) -> void:
	auto_kill_enabled = enabled
	if enabled:
		_kill_all_enemies_in_all_rooms()

func _kill_all_enemies_in_all_rooms() -> void:
	for pos in active_rooms.keys():
		var r = active_rooms[pos]
		if is_instance_valid(r):
			r.kill_all_enemies()

func _on_rebuild_dungeon_requested() -> void:
	call_deferred("build_new_dungeon", current_dungeon_level, true)
