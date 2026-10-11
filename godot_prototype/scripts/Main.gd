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

func _ready() -> void:
	difficulty_manager = DifficultyManager.new()
	# Initialize Level 1 calibration parameters
	difficulty_manager.apply_calibration_level(1)
	
	telemetry_logger = TelemetryLogger.new()
	dungeon_generator = DungeonGenerator.new()

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
	
	# Hide player completely until Start Run is clicked from Menu
	player.visible = false
	player.position = Vector2(-9999, -9999)
	player.set_physics_process(false)
	defense_overlay.visible = false

func _on_start_run_requested() -> void:
	game_started = true
	player.visible = true
	player.set_physics_process(true)
	defense_overlay.visible = true
	call_deferred("build_new_dungeon", 1)

func _process(delta: float) -> void:
	telemetry_logger.update_time(delta)
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
	add_camera_trauma(0.42) # Screen trauma punch on hit
	spawn_damage_floater(player.global_position, amount, true)

func _on_player_healed(amount: float) -> void:
	spawn_damage_floater(player.global_position, amount, false, true)

func _on_enemy_damaged(amount: float, pos: Vector2) -> void:
	spawn_damage_floater(pos, amount, false)

func build_new_dungeon(level_num: int) -> void:
	current_dungeon_level = level_num
	var is_calibrating = difficulty_manager.is_in_calibration(level_num)
	var cal_data: Dictionary = {}
	
	if is_calibrating:
		cal_data = difficulty_manager.apply_calibration_level(level_num)
	
	defense_overlay.sync_ui_with_manager()
	
	# Clear old rooms
	for child in dungeon_container.get_children():
		child.queue_free()
	active_rooms.clear()
	
	# 1. Procedurally generate dungeon layout on grid
	var room_count = difficulty_manager.room_count_target
	var generated_data = dungeon_generator.generate_dungeon(difficulty_manager, room_count)
	
	# 2. Instantiate Room scenes for each generated room
	for pos in generated_data.keys():
		var r_data = generated_data[pos]
		var r_inst = room_scene.instantiate()
		dungeon_container.add_child(r_inst)
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

	# 5. Snapshot the clock + telemetry for this level
	level_start_time_msec = Time.get_ticks_msec()
	level_start_deaths = telemetry_logger.total_deaths
	level_start_damage_taken = telemetry_logger.damage_taken

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
	var start_pos = dungeon_generator.start_room_pos
	if dungeon_generator.rooms.has(start_pos):
		var start_world_pos = dungeon_generator.rooms[start_pos].world_pos
		player.reset(start_world_pos)
		current_player_room_pos = start_pos
		defense_overlay.update_minimap_player(start_pos)
		var is_calibrating = difficulty_manager.is_in_calibration(current_dungeon_level)
		defense_overlay.update_room_info(current_dungeon_level, start_pos, is_calibrating)

func _on_dungeon_escaped() -> void:
	# 1. Measure level performance
	var completion_time_sec = float(Time.get_ticks_msec() - level_start_time_msec) / 1000.0
	var deaths_this_level = telemetry_logger.total_deaths - level_start_deaths
	var damage_taken_this_level = telemetry_logger.damage_taken - level_start_damage_taken

	var next_level = current_dungeon_level + 1

	# Special milestone: Exiting Floor 5 finishes Cold-Start calibration!
	if current_dungeon_level == 5:
		print("[FORGE][COLD-START] 5 calibration levels completed! Baseline established.")
		# Show PPO Activation celebration banner
		if level_splash:
			level_splash.show_ppo_activation_banner()
			# Allow player to read the activation message before loading floor 6
			await get_tree().create_timer(2.2).timeout

	# 2. PPO adaptation step:
	# During levels 1-4, next level parameters are loaded from calibration.
	# From level 5 completion onward (generating floor 6+), the PPO policy drives difficulty!
	if next_level >= 6:
		var obs = difficulty_manager.build_observation(
			completion_time_sec, deaths_this_level, damage_taken_this_level,
			player.max_health, current_dungeon_level
		)
		var action = ppo_policy.predict(obs)
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

	# 3. Advance to next level
	call_deferred("build_new_dungeon", next_level)

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
	call_deferred("build_new_dungeon", current_dungeon_level)
