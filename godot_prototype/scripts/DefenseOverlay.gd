class_name DefenseOverlay
extends CanvasLayer

signal parameters_updated
signal regenerate_room_requested
signal auto_kill_toggled(enabled: bool)

var difficulty_manager: DifficultyManager
var telemetry_logger: TelemetryLogger

var font_cinzel: Font = null
var font_inter: Font = null

@onready var panel_container: PanelContainer = $Control/DefensePanel
@onready var toggle_btn: Button = $Control/TopBar/TogglePanelBtn
@onready var score_label: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ReportBox/ScoreHBox/ScoreLabel
@onready var tier_label: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ReportBox/ScoreHBox/TierLabel
@onready var drivers_container: VBoxContainer = $Control/DefensePanel/MarginContainer/VBoxContainer/ReportBox/DriversList
@onready var ppo_stats_label: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ReportBox/PPOStatsLabel
@onready var minimap: MiniMap = $Control/MiniMap

# Sliders & Value Labels
@onready var slider_hp: HSlider = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/SliderHP
@onready var label_hp: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/LabelHPValue
@onready var slider_dmg: HSlider = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/SliderDmg
@onready var label_dmg: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/LabelDmgValue
@onready var slider_spd: HSlider = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/SliderSpd
@onready var label_spd: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/LabelSpdValue
@onready var slider_aggro: HSlider = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/SliderAggro
@onready var label_aggro: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/LabelAggroValue
@onready var slider_haz: HSlider = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/SliderHaz
@onready var label_haz: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/LabelHazValue
@onready var slider_scarce: HSlider = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/SliderScarce
@onready var label_scarce: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/ParamGrid/LabelScarceValue

# Profile Preset Buttons
@onready var btn_novice: Button = $Control/DefensePanel/MarginContainer/VBoxContainer/PresetsHBox/BtnNovice
@onready var btn_inter: Button = $Control/DefensePanel/MarginContainer/VBoxContainer/PresetsHBox/BtnIntermediate
@onready var btn_expert: Button = $Control/DefensePanel/MarginContainer/VBoxContainer/PresetsHBox/BtnExpert
@onready var btn_regen: Button = $Control/DefensePanel/MarginContainer/VBoxContainer/BtnRegenerate
@onready var btn_auto_kill: CheckButton = $Control/DefensePanel/MarginContainer/VBoxContainer/BtnAutoKill

# HUD Elements
@onready var hp_bar: ProgressBar = $Control/TopBar/HPBar
@onready var hp_text: Label = $Control/TopBar/HPText
@onready var room_label: Label = $Control/TopBar/RoomLabel
@onready var hud_diff_label: Label = $Control/TopBar/DifficultyBadge
@onready var telemetry_summary_label: Label = $Control/DefensePanel/MarginContainer/VBoxContainer/TelemetryBox/TelemetrySummaryLabel

var is_panel_open: bool = false
var _current_floor: int = 1
## Experimental-condition toggles (created in code). At most one is on: FORGE = both off.
var static_btn: CheckButton
var bsp_btn: CheckButton
## False in playtest builds (BuildInfo): the panel, its Tab shortcut and on-screen difficulty
## numbers are hidden so testers play exactly what the policy generated.
var dev_tools: bool = true

func _ready() -> void:
	# Load Google Fonts
	if ResourceLoader.exists("res://assets/fonts/Cinzel.ttf"):
		font_cinzel = load("res://assets/fonts/Cinzel.ttf")
	if ResourceLoader.exists("res://assets/fonts/Inter.ttf"):
		font_inter = load("res://assets/fonts/Inter.ttf")
		
	_apply_typography()

	toggle_btn.pressed.connect(_on_toggle_panel_pressed)
	btn_novice.pressed.connect(func(): _on_preset_selected(DifficultyManager.ProfileTier.NOVICE))
	btn_inter.pressed.connect(func(): _on_preset_selected(DifficultyManager.ProfileTier.INTERMEDIATE))
	btn_expert.pressed.connect(func(): _on_preset_selected(DifficultyManager.ProfileTier.EXPERT))
	btn_regen.pressed.connect(func(): emit_signal("regenerate_room_requested"))
	btn_auto_kill.toggled.connect(_on_auto_kill_toggled)

	# Static non-adaptive baseline toggle (created in code so the scene file stays unchanged)
	static_btn = CheckButton.new()
	static_btn.text = "Static Baseline (+8% / floor)"
	btn_auto_kill.get_parent().add_child(static_btn)
	btn_auto_kill.get_parent().move_child(static_btn, btn_auto_kill.get_index() + 1)
	static_btn.toggled.connect(_on_static_baseline_toggled)
	# BSP non-adaptive baseline toggle (BSP layouts + fixed Intermediate preset)
	bsp_btn = CheckButton.new()
	bsp_btn.text = "BSP Baseline (fixed Intermediate)"
	btn_auto_kill.get_parent().add_child(bsp_btn)
	btn_auto_kill.get_parent().move_child(bsp_btn, static_btn.get_index() + 1)
	bsp_btn.toggled.connect(_on_bsp_baseline_toggled)
	
	slider_hp.value_changed.connect(_on_slider_changed)
	slider_dmg.value_changed.connect(_on_slider_changed)
	slider_spd.value_changed.connect(_on_slider_changed)
	slider_aggro.value_changed.connect(_on_slider_changed)
	slider_haz.value_changed.connect(_on_slider_changed)
	slider_scarce.value_changed.connect(_on_slider_changed)
	
	set_panel_visible(false)
	_apply_build_flavour()

func _apply_build_flavour() -> void:
	dev_tools = BuildInfo.dev_tools_enabled()
	toggle_btn.visible = dev_tools
	hud_diff_label.visible = dev_tools
	if has_node("Control/TopBar/VSeparator2"):
		get_node("Control/TopBar/VSeparator2").visible = dev_tools
	if not dev_tools:
		set_panel_visible(false)

## Telemetry: the current floor no longer reflects the policy's settings/outcome.
func _flag_override(reason: String) -> void:
	if telemetry_logger:
		telemetry_logger.mark_manual_override(reason)

func _apply_typography() -> void:
	# Apply Cinzel (Epic medieval font) to headers, badges, and action buttons
	if font_cinzel:
		if has_node("Control/DefensePanel/MarginContainer/VBoxContainer/HeaderLabel"):
			var hdr = get_node("Control/DefensePanel/MarginContainer/VBoxContainer/HeaderLabel")
			hdr.add_theme_font_override("font", font_cinzel)
			hdr.add_theme_font_size_override("font_size", 16)
		toggle_btn.add_theme_font_override("font", font_cinzel)
		room_label.add_theme_font_override("font", font_cinzel)
		hud_diff_label.add_theme_font_override("font", font_cinzel)
		score_label.add_theme_font_override("font", font_cinzel)
		tier_label.add_theme_font_override("font", font_cinzel)
		btn_novice.add_theme_font_override("font", font_cinzel)
		btn_inter.add_theme_font_override("font", font_cinzel)
		btn_expert.add_theme_font_override("font", font_cinzel)
		btn_regen.add_theme_font_override("font", font_cinzel)
		
	# Apply Inter (Crisp modern sans-serif) to numeric telemetry, data values, and sliders
	if font_inter:
		hp_text.add_theme_font_override("font", font_inter)
		telemetry_summary_label.add_theme_font_override("font", font_inter)
		ppo_stats_label.add_theme_font_override("font", font_inter)
		label_hp.add_theme_font_override("font", font_inter)
		label_dmg.add_theme_font_override("font", font_inter)
		label_spd.add_theme_font_override("font", font_inter)
		label_aggro.add_theme_font_override("font", font_inter)
		label_haz.add_theme_font_override("font", font_inter)
		label_scarce.add_theme_font_override("font", font_inter)

func _input(event: InputEvent) -> void:
	if not dev_tools or not visible:
		return
	if event.is_action_pressed("toggle_defense_panel") and not event.is_echo():
		toggle_panel()

func setup(p_diff: DifficultyManager, p_telemetry: TelemetryLogger) -> void:
	difficulty_manager = p_diff
	telemetry_logger = p_telemetry
	sync_ui_with_manager()

func toggle_panel() -> void:
	set_panel_visible(not is_panel_open)

func set_panel_visible(p_visible: bool) -> void:
	is_panel_open = p_visible
	panel_container.visible = is_panel_open
	toggle_btn.text = "✖ Close Panel (Tab)" if is_panel_open else "⚙ Defense Panel (Tab)"

func _on_toggle_panel_pressed() -> void:
	toggle_panel()

func _on_auto_kill_toggled(enabled: bool) -> void:
	if enabled:
		_flag_override("auto-kill") # kill() deals the enemy's remaining HP, inflating damage/kills
	emit_signal("auto_kill_toggled", enabled)
	if minimap:
		minimap.set_reveal_exit(enabled)

func _on_static_baseline_toggled(enabled: bool) -> void:
	_set_condition(DifficultyManager.GENERATOR_STATIC if enabled else DifficultyManager.GENERATOR_FORGE,
		"static baseline toggled")

func _on_bsp_baseline_toggled(enabled: bool) -> void:
	_set_condition(DifficultyManager.GENERATOR_BSP if enabled else DifficultyManager.GENERATOR_FORGE,
		"bsp baseline toggled")

## Switch FORGE / static / BSP and rebuild the current floor with the new condition.
func _set_condition(mode: String, reason: String) -> void:
	_flag_override(reason)
	difficulty_manager.set_generator_mode(mode)
	if difficulty_manager.is_baseline_mode():
		difficulty_manager.apply_baseline(_current_floor)
	elif difficulty_manager.is_in_calibration(_current_floor):
		difficulty_manager.apply_calibration_level(_current_floor)
	sync_ui_with_manager()
	update_room_info(_current_floor, Vector2i.ZERO, difficulty_manager.is_in_calibration(_current_floor))
	emit_signal("parameters_updated")
	emit_signal("regenerate_room_requested")

func _on_preset_selected(tier: DifficultyManager.ProfileTier) -> void:
	_flag_override("preset")
	difficulty_manager.apply_preset(tier)
	sync_ui_with_manager()
	emit_signal("parameters_updated")
	emit_signal("regenerate_room_requested")

func _on_slider_changed(_val: float) -> void:
	_flag_override("slider")
	difficulty_manager.current_profile = DifficultyManager.ProfileTier.CUSTOM
	difficulty_manager.enemy_health = slider_hp.value
	difficulty_manager.enemy_damage = slider_dmg.value
	difficulty_manager.enemy_speed = slider_spd.value
	difficulty_manager.enemy_aggro = slider_aggro.value
	difficulty_manager.hazard_density = slider_haz.value / 100.0
	difficulty_manager.resource_scarcity = slider_scarce.value / 100.0
	
	update_labels()
	update_report_ui()
	emit_signal("parameters_updated")

func sync_ui_with_manager() -> void:
	if not difficulty_manager:
		return
	if static_btn:
		static_btn.set_pressed_no_signal(difficulty_manager.static_baseline_mode)
	if bsp_btn:
		bsp_btn.set_pressed_no_signal(difficulty_manager.bsp_baseline_mode)
	# set_value_no_signal: setting .value fires value_changed, whose handler writes ALL
	# sliders back into the manager -- including ones not yet synced -- which used to
	# overwrite every calibration/PPO parameter except enemy_health with stale values.
	slider_hp.set_value_no_signal(difficulty_manager.enemy_health)
	slider_dmg.set_value_no_signal(difficulty_manager.enemy_damage)
	slider_spd.set_value_no_signal(difficulty_manager.enemy_speed)
	slider_aggro.set_value_no_signal(difficulty_manager.enemy_aggro)
	slider_haz.set_value_no_signal(difficulty_manager.hazard_density * 100.0)
	slider_scarce.set_value_no_signal(difficulty_manager.resource_scarcity * 100.0)
	
	update_labels()
	update_report_ui()

func update_labels() -> void:
	label_hp.text = str(int(slider_hp.value))
	label_dmg.text = str(int(slider_dmg.value))
	label_spd.text = str(int(slider_spd.value))
	label_aggro.text = str(int(slider_aggro.value))
	label_haz.text = str(int(slider_haz.value)) + "%"
	label_scarce.text = str(int(slider_scarce.value)) + "%"

func update_report_ui() -> void:
	if not difficulty_manager:
		return
	var report = difficulty_manager.calculate_difficulty_score()
	score_label.text = "Difficulty: " + str(report.score) + "/100"
	tier_label.text = report.label
	hud_diff_label.text = "Challenge: " + report.label + " (" + str(report.score) + "/100)"
	
	for child in drivers_container.get_children():
		child.queue_free()
		
	var top_count = mini(4, report.drivers.size())
	for i in range(top_count):
		var d = report.drivers[i]
		var lbl = Label.new()
		lbl.text = str(i + 1) + ". " + d.name + " (" + str(d.pct) + "%)"
		if font_inter:
			lbl.add_theme_font_override("font", font_inter)
		lbl.add_theme_font_size_override("font_size", 12)
		lbl.add_theme_color_override("font_color", Color(0.85, 0.9, 0.95))
		drivers_container.add_child(lbl)

	ppo_stats_label.text = "Next dungeon → Rooms: %d | Enemy count ×%.2f" % [
		difficulty_manager.room_count_target, difficulty_manager.enemy_count_scale
	]

func update_player_hp(current: float, max_val: float) -> void:
	hp_bar.max_value = max_val
	hp_bar.value = current
	hp_text.text = str(int(current)) + " / " + str(int(max_val)) + " HP"

func update_room_info(dungeon_level: int, grid_pos: Vector2i, is_calibrating: bool = false) -> void:
	_current_floor = dungeon_level
	if not dev_tools:
		room_label.text = "Floor %d" % dungeon_level
		return
	var mode_tag = "[CALIBRATION %d/5]" % dungeon_level if is_calibrating else "[ADAPTIVE PPO]"
	if difficulty_manager and difficulty_manager.static_baseline_mode:
		mode_tag = "[STATIC +8%/floor]"
	elif difficulty_manager and difficulty_manager.bsp_baseline_mode:
		mode_tag = "[BSP BASELINE]"
	var mix_txt := ""
	if difficulty_manager:
		var m: PackedFloat32Array = difficulty_manager.archetype_mix
		mix_txt = " | Mix C/P/B/S/W: %d/%d/%d/%d/%d%%" % [
			int(round(m[0] * 100.0)), int(round(m[1] * 100.0)), int(round(m[2] * 100.0)),
			int(round(m[3] * 100.0)), int(round(m[4] * 100.0))]
	room_label.text = "Floor %d %s | Room: (%d,%d)%s" % [dungeon_level, mode_tag, grid_pos.x, grid_pos.y, mix_txt]

func setup_minimap(rooms_data: Dictionary, start_pos: Vector2i) -> void:
	if minimap:
		minimap.set_dungeon_data(rooms_data, start_pos)

func update_minimap_player(grid_pos: Vector2i) -> void:
	if minimap:
		minimap.update_player_pos(grid_pos)

func update_telemetry_ui() -> void:
	if not telemetry_logger:
		return
	var t = telemetry_logger.get_summary()
	telemetry_summary_label.text = (
		"Time: " + str(t.elapsed_seconds) + "s | " +
		"Deaths: " + str(t.total_deaths) + " | " +
		"Kills: " + str(t.enemies_defeated) + " | " +
		"Damage Taken: " + str(t.damage_taken) + " | " +
		"Pickups: " + str(t.pickups_collected)
	)
