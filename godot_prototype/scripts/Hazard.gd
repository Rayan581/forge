class_name Hazard
extends Area2D

signal player_hit_hazard

@export var damage_amount: float = 12.0
@export var damage_interval: float = 0.75

var target_player: Player = null
var tick_timer: float = 0.0

@onready var sprite: Sprite2D = get_node_or_null("Sprite2D")

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)
	if not sprite and has_node("Sprite2D"):
		sprite = $Sprite2D

func _process(delta: float) -> void:
	if target_player:
		tick_timer -= delta
		if tick_timer <= 0.0:
			tick_timer = damage_interval
			var push_dir = (target_player.global_position - global_position).normalized()
			if push_dir == Vector2.ZERO:
				push_dir = Vector2.UP
			target_player.take_damage(damage_amount, push_dir * 0.75)
			emit_signal("player_hit_hazard")
			# Spike prick juice: punch scale and flash
			if sprite:
				var tw = create_tween()
				tw.tween_property(sprite, "scale", Vector2(1.25, 1.25), 0.06)
				tw.tween_property(sprite, "scale", Vector2(1.0, 1.0), 0.1)

func _on_body_entered(body: Node2D) -> void:
	if body is Player:
		target_player = body
		tick_timer = 0.05 # Immediate damage upon stepping on spikes

func _on_body_exited(body: Node2D) -> void:
	if body == target_player:
		target_player = null
