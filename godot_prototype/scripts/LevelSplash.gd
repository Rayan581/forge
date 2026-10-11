class_name LevelSplash
extends CanvasLayer

var font_cinzel: Font = null
var font_inter: Font = null

@onready var container: PanelContainer = $Control/CenterContainer/SplashPanel
@onready var title_label: Label = $Control/CenterContainer/SplashPanel/MarginContainer/VBoxContainer/TitleLabel
@onready var subtitle_label: Label = $Control/CenterContainer/SplashPanel/MarginContainer/VBoxContainer/SubtitleLabel
@onready var desc_label: Label = $Control/CenterContainer/SplashPanel/MarginContainer/VBoxContainer/DescLabel
@onready var challenge_label: Label = $Control/CenterContainer/SplashPanel/MarginContainer/VBoxContainer/ChallengeBadge

var current_tween: Tween = null

func _ready() -> void:
	if ResourceLoader.exists("res://assets/fonts/Cinzel.ttf"):
		font_cinzel = load("res://assets/fonts/Cinzel.ttf")
	if ResourceLoader.exists("res://assets/fonts/Inter.ttf"):
		font_inter = load("res://assets/fonts/Inter.ttf")
		
	if font_cinzel:
		title_label.add_theme_font_override("font", font_cinzel)
		challenge_label.add_theme_font_override("font", font_cinzel)
	if font_inter:
		subtitle_label.add_theme_font_override("font", font_inter)
		desc_label.add_theme_font_override("font", font_inter)
		
	container.modulate.a = 0.0
	visible = false

func show_level_announcement(level_num: int, is_calibrating: bool, cal_data: Dictionary, diff_score: int, diff_label: String) -> void:
	if current_tween and current_tween.is_valid():
		current_tween.kill()
		
	visible = true
	container.modulate.a = 0.0
	container.scale = Vector2(0.92, 0.92)
	
	if is_calibrating and not cal_data.is_empty():
		title_label.text = cal_data.get("title", "Level " + str(level_num))
		title_label.modulate = Color(0.95, 0.78, 0.35) # Gold
		subtitle_label.text = cal_data.get("subtitle", "Cold-Start Calibration Stage")
		subtitle_label.modulate = Color(0.4, 0.8, 1.0) # Light blue
		desc_label.text = cal_data.get("description", "")
		challenge_label.text = "Target Challenge: %s (%d/100) · Rooms: %d" % [
			diff_label, diff_score, cal_data.get("rooms", 4)
		]
	else:
		title_label.text = "Floor " + str(level_num) + ": Adaptive Realm"
		title_label.modulate = Color(0.4, 0.85, 0.6) # Emerald green
		subtitle_label.text = "Adaptive Closed-Loop PPO Mode Engaged"
		subtitle_label.modulate = Color(0.5, 0.9, 0.7)
		desc_label.text = "Room topology, enemy aggression, and hazard density synthesized in real time from your past combat telemetry."
		challenge_label.text = "Conditioned Challenge: %s (%d/100)" % [diff_label, diff_score]
		
	current_tween = create_tween()
	# Slide/Pop in
	current_tween.parallel().tween_property(container, "modulate:a", 1.0, 0.35).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	current_tween.parallel().tween_property(container, "scale", Vector2(1.0, 1.0), 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	# Hold for reading
	current_tween.tween_interval(2.3)
	# Fade out
	current_tween.parallel().tween_property(container, "modulate:a", 0.0, 0.45).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	current_tween.parallel().tween_property(container, "scale", Vector2(1.04, 1.04), 0.45)
	await current_tween.finished
	visible = false

func show_ppo_activation_banner() -> void:
	if current_tween and current_tween.is_valid():
		current_tween.kill()
		
	visible = true
	container.modulate.a = 0.0
	container.scale = Vector2(0.92, 0.92)
	
	title_label.text = "CALIBRATION COMPLETE"
	title_label.modulate = Color(0.3, 0.9, 0.95) # Cyan
	subtitle_label.text = "Player Baseline Established (CR₀) · Engaging PPO Policy"
	subtitle_label.modulate = Color(0.6, 0.85, 1.0)
	desc_label.text = "Cold-Start phase finished. The neural PPO generator is now actively tailoring room density, enemy velocity, and hazard placements to your individual flow state."
	challenge_label.text = "★ Level 6+ · Full Adaptive Closed-Loop Active ★"
	
	current_tween = create_tween()
	current_tween.parallel().tween_property(container, "modulate:a", 1.0, 0.4).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	current_tween.parallel().tween_property(container, "scale", Vector2(1.0, 1.0), 0.4).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	current_tween.tween_interval(3.2)
	current_tween.parallel().tween_property(container, "modulate:a", 0.0, 0.5)
	await current_tween.finished
	visible = false
