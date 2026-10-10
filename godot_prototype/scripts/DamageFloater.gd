class_name DamageFloater
extends Node2D

@onready var label: Label = $Label

func setup(amount: float, is_player_damage: bool, is_heal: bool = false) -> void:
	if not label:
		label = $Label
		
	if is_heal:
		label.text = "+%d" % int(amount)
		label.add_theme_color_override("font_color", Color(0.25, 0.95, 0.45, 1.0))
		label.add_theme_color_override("font_outline_color", Color(0.05, 0.25, 0.1, 1.0))
	elif is_player_damage:
		label.text = "-%d" % int(amount)
		label.add_theme_color_override("font_color", Color(1.0, 0.28, 0.28, 1.0))
		label.add_theme_color_override("font_outline_color", Color(0.35, 0.05, 0.05, 1.0))
	else:
		# Enemy took damage from player
		label.text = "%d" % int(amount)
		label.add_theme_color_override("font_color", Color(1.0, 0.88, 0.32, 1.0))
		label.add_theme_color_override("font_outline_color", Color(0.35, 0.2, 0.05, 1.0))
		
	label.add_theme_constant_override("outline_size", 4)
	
	if ResourceLoader.exists("res://assets/fonts/Inter.ttf"):
		var font_res = load("res://assets/fonts/Inter.ttf")
		if font_res:
			label.add_theme_font_override("font", font_res)
			
	label.add_theme_font_size_override("font_size", 16)
	
	# Tween juice: pop scale and float upward
	scale = Vector2(0.5, 0.5)
	var tween = create_tween()
	
	# Pop scale
	tween.tween_property(self, "scale", Vector2(1.25, 1.25), 0.1).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "scale", Vector2(1.0, 1.0), 0.08)
	
	# Float upward and fade out simultaneously
	var drift_x = randf_range(-14.0, 14.0)
	var float_tween = create_tween()
	float_tween.set_parallel(true)
	float_tween.tween_property(self, "position:y", position.y - randf_range(36.0, 52.0), 0.7).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	float_tween.tween_property(self, "position:x", position.x + drift_x, 0.7)
	float_tween.tween_property(self, "modulate:a", 0.0, 0.7).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	float_tween.chain().tween_callback(queue_free)
