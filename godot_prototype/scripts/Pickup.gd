class_name Pickup
extends Area2D

signal pickup_collected(pickup_type: String)

@export var heal_amount: float = 35.0
var bob_offset: float = 0.0

@onready var sprite: Sprite2D = get_node_or_null("Sprite2D")

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	if not sprite and has_node("Sprite2D"):
		sprite = $Sprite2D

func _process(delta: float) -> void:
	bob_offset += delta * 3.5
	if sprite:
		sprite.position.y = sin(bob_offset) * 3.5
		var pulse = 1.0 + sin(bob_offset * 1.8) * 0.06
		sprite.scale = Vector2(pulse, pulse)

func _on_body_entered(body: Node2D) -> void:
	if body is Player:
		if body.current_health < body.max_health:
			body.heal(heal_amount)
			emit_signal("pickup_collected", "health")
			queue_free()
