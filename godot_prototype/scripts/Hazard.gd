class_name Hazard
extends Area2D

signal player_hit_hazard

@export var damage_amount: float = 12.0
@export var damage_interval: float = 0.75

var target_player: Player = null
var tick_timer: float = 0.0

@onready var sprite: AnimatedSprite2D = get_node_or_null("AnimatedSprite2D")
var base_scale: Vector2 = Vector2(2, 2)

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)
	if not sprite and has_node("AnimatedSprite2D"):
		sprite = $AnimatedSprite2D
	if sprite:
		base_scale = sprite.scale
		sprite.play(&"idle") # spikes are always armed: damage logic is unchanged

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
			# Spike stab: retract-and-punch-out animation plus a scale punch
			if sprite:
				sprite.play(&"stab")
				var tw = create_tween()
				tw.tween_property(sprite, "scale", base_scale * 1.15, 0.06)
				tw.tween_property(sprite, "scale", base_scale, 0.1)
				tw.tween_callback(func(): if is_instance_valid(sprite) and not sprite.is_playing(): sprite.play(&"idle"))

func _on_body_entered(body: Node2D) -> void:
	if body is Player:
		target_player = body
		tick_timer = 0.05 # Immediate damage upon stepping on spikes

func _on_body_exited(body: Node2D) -> void:
	if body == target_player:
		target_player = null
