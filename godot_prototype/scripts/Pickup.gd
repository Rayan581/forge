class_name Pickup
extends Area2D

signal pickup_collected(pickup_type: String)

@export var heal_amount: float = 35.0
var bob_offset: float = 0.0

@onready var sprite: AnimatedSprite2D = get_node_or_null("AnimatedSprite2D")
var base_scale: Vector2 = Vector2(2, 2)

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	if not sprite and has_node("AnimatedSprite2D"):
		sprite = $AnimatedSprite2D
	if sprite:
		base_scale = sprite.scale
		sprite.frame = randi() % 4 # desync multiple flasks
		sprite.play(&"idle")

func _process(delta: float) -> void:
	bob_offset += delta * 3.5
	if sprite:
		sprite.position.y = -6.0 + sin(bob_offset) * 3.0
		var pulse = 1.0 + sin(bob_offset * 1.8) * 0.04
		sprite.scale = base_scale * pulse
		queue_redraw()

func _draw() -> void:
	# Ground shadow that shrinks as the flask bobs up
	var lift := (sin(bob_offset) + 1.0) * 0.5
	draw_set_transform(Vector2(0, 8), 0.0, Vector2(1.0, 0.4))
	draw_circle(Vector2.ZERO, 9.0 - lift * 2.0, Color(0, 0, 0, 0.4 - lift * 0.1))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

func _on_body_entered(body: Node2D) -> void:
	if body is Player:
		if body.current_health < body.max_health:
			body.heal(heal_amount)
			emit_signal("pickup_collected", "health")
			queue_free()
