class_name Hazard
extends Area2D

signal player_hit_hazard

@export var damage_amount: float = 12.0
@export var damage_interval: float = 0.75

var target_player: Player = null
var tick_timer: float = 0.0

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)

func _process(delta: float) -> void:
	if target_player:
		tick_timer -= delta
		if tick_timer <= 0.0:
			tick_timer = damage_interval
			target_player.take_damage(damage_amount)
			emit_signal("player_hit_hazard")

func _on_body_entered(body: Node2D) -> void:
	if body is Player:
		target_player = body
		tick_timer = 0.1 # Immediate damage upon entry

func _on_body_exited(body: Node2D) -> void:
	if body == target_player:
		target_player = null

func _draw() -> void:
	# Draw Spike Hazard Grid (32x32)
	var size = 32.0
	var rect = Rect2(-size/2, -size/2, size, size)
	draw_rect(rect, Color(0.35, 0.15, 0.12, 0.85))
	draw_rect(rect, Color(0.7, 0.25, 0.15), false, 1.5)
	
	# Spikes
	var spike_color = Color(0.85, 0.85, 0.85)
	for ox in [-8, 8]:
		for oy in [-8, 8]:
			var pt = Vector2(ox, oy)
			draw_line(pt + Vector2(-4, 4), pt + Vector2(0, -6), spike_color, 2.0)
			draw_line(pt + Vector2(4, 4), pt + Vector2(0, -6), spike_color, 2.0)
