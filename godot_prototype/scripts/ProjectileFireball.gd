class_name ProjectileFireball
extends Area2D

@export var speed: float = 240.0
@export var damage: float = 18.0
var direction: Vector2 = Vector2.RIGHT
var lifetime: float = 3.5
var current_lifetime: float = 0.0

@onready var sprite: Sprite2D = $Sprite2D

func _ready() -> void:
	collision_layer = 0
	collision_mask = 1 | 4 # Layer 1: Player, Layer 3 (mask 4): Dungeon Walls
	body_entered.connect(_on_body_entered)
	rotation = direction.angle()

func setup(p_dir: Vector2, p_damage: float = 18.0, p_speed: float = 240.0) -> void:
	direction = p_dir.normalized()
	damage = p_damage
	speed = p_speed
	rotation = direction.angle()

func _physics_process(delta: float) -> void:
	position += direction * speed * delta
	current_lifetime += delta
	
	# Fiery wobble / pulse animation
	if sprite:
		var wobble = sin(Time.get_ticks_msec() / 60.0) * 0.12
		sprite.scale = Vector2(1.0 + wobble, 1.0 - wobble)
	
	queue_redraw()
	
	if current_lifetime >= lifetime:
		queue_free()

func _on_body_entered(body: Node2D) -> void:
	if body is Player:
		body.take_damage(damage, direction)
		queue_free()
	elif body is StaticBody2D:
		# Hit wall - dissolve impact
		queue_free()

func _draw() -> void:
	# Trailing fiery embers / outer heat aura
	var pulse = sin(Time.get_ticks_msec() / 70.0) * 2.0
	draw_circle(Vector2(-6, 0), 10.0 + pulse, Color(1.0, 0.45, 0.1, 0.35))
	draw_circle(Vector2(-12, 0), 6.0, Color(1.0, 0.25, 0.05, 0.25))
	draw_circle(Vector2(-18, 0), 3.0, Color(0.8, 0.15, 0.05, 0.15))
