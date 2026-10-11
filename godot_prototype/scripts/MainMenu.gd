class_name MainMenu
extends CanvasLayer

signal start_run_requested
signal exit_game_requested

var font_cinzel: Font = null
var font_inter: Font = null

@onready var main_box: VBoxContainer = $Control/CenterContainer/MainBox
@onready var briefing_panel: PanelContainer = $Control/BriefingPanel
@onready var btn_start: Button = $Control/CenterContainer/MainBox/MenuButtons/BtnStart
@onready var btn_briefing_start: Button = $Control/BriefingPanel/MarginContainer/VBoxContainer/ActionsHBox/BtnBriefingStart
@onready var btn_briefing_back: Button = $Control/BriefingPanel/MarginContainer/VBoxContainer/ActionsHBox/BtnBriefingBack
@onready var btn_exit: Button = $Control/CenterContainer/MainBox/MenuButtons/BtnExit

func _ready() -> void:
	if ResourceLoader.exists("res://assets/fonts/Cinzel.ttf"):
		font_cinzel = load("res://assets/fonts/Cinzel.ttf")
	if ResourceLoader.exists("res://assets/fonts/Inter.ttf"):
		font_inter = load("res://assets/fonts/Inter.ttf")
		
	_apply_typography()
	
	btn_start.pressed.connect(_on_btn_start_pressed)
	btn_briefing_start.pressed.connect(_on_btn_briefing_start_pressed)
	btn_briefing_back.pressed.connect(_on_btn_briefing_back_pressed)
	btn_exit.pressed.connect(_on_btn_exit_pressed)
	
	briefing_panel.visible = false
	main_box.visible = true

func _apply_typography() -> void:
	if font_cinzel:
		$Control/CenterContainer/MainBox/TitleLabel.add_theme_font_override("font", font_cinzel)
		$Control/CenterContainer/MainBox/MenuButtons/BtnStart.add_theme_font_override("font", font_cinzel)
		$Control/CenterContainer/MainBox/MenuButtons/BtnExit.add_theme_font_override("font", font_cinzel)
		$Control/BriefingPanel/MarginContainer/VBoxContainer/BriefingTitle.add_theme_font_override("font", font_cinzel)
		btn_briefing_start.add_theme_font_override("font", font_cinzel)
		btn_briefing_back.add_theme_font_override("font", font_cinzel)
		
	if font_inter:
		$Control/CenterContainer/MainBox/SubtitleLabel.add_theme_font_override("font", font_inter)
		$Control/CenterContainer/MainBox/MetaLabel.add_theme_font_override("font", font_inter)
		$Control/BriefingPanel/MarginContainer/VBoxContainer/BriefingBody.add_theme_font_override("font", font_inter)

func _on_btn_start_pressed() -> void:
	# Show Cold-Start Calibration Briefing Screen
	main_box.visible = false
	briefing_panel.visible = true
	briefing_panel.modulate.a = 0.0
	var tw = create_tween()
	tw.tween_property(briefing_panel, "modulate:a", 1.0, 0.25)

func _on_btn_briefing_back_pressed() -> void:
	briefing_panel.visible = false
	main_box.visible = true

func _on_btn_briefing_start_pressed() -> void:
	var tw = create_tween()
	tw.tween_property(self, "offset:y", -720.0, 0.45).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	await tw.finished
	visible = false
	offset.y = 0.0
	emit_signal("start_run_requested")

func _on_btn_exit_pressed() -> void:
	get_tree().quit()
