class_name Pickup
extends Area2D

signal pickup_collected(pickup_type: String)

@export var heal_amount: float = 35.0
var bob_offset: float = 0.0

func _ready() -> void:
	body_entered.connect(_on_body_entered)

func _process(delta: float) -> void:
	bob_offset += delta * 3.5
	queue_redraw()

func _on_body_entered(body: Node2D) -> void:
	if body is Player:
		if body.current_health < body.max_health:
			body.heal(heal_amount)
			emit_signal("pickup_collected", "health")
			queue_free()

func _draw() -> void:
	var y_shift = sin(bob_offset) * 3.0
	var pos = Vector2(0, y_shift)
	
	# Glow Aura
	draw_circle(pos, 15.0, Color(0.2, 0.9, 0.4, 0.25))
	# Flask Body
	draw_circle(pos + Vector2(0, 2), 9.0, Color(0.15, 0.85, 0.35, 0.9))
	draw_rect(Rect2(pos.x - 3, pos.y - 10, 6, 7), Color(0.8, 0.85, 0.9, 0.85))
	draw_line(pos + Vector2(-4, -10), pos + Vector2(4, -10), Color(0.6, 0.4, 0.2), 2.5) # Cork
	# Cross
	draw_line(pos + Vector2(-4, 2), pos + Vector2(4, 2), Color(1, 1, 1), 2.0)
	draw_line(pos + Vector2(0, -2), pos + Vector2(0, 6), Color(1, 1, 1), 2.0)
