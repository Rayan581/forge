class_name SlamShockwave
extends Node2D

## Short-lived expanding ring spawned at the moment a Heavy Brute's ground slam lands.
## Purely visual: damage is applied by Enemy._do_slam(). Frees itself when finished.

var max_radius: float = 90.0
var duration: float = 0.4
var color: Color = Color(1.0, 0.45, 0.2)
var age: float = 0.0

func setup(p_radius: float, p_duration: float = 0.4, p_color: Color = Color(1.0, 0.45, 0.2)) -> void:
	max_radius = p_radius
	duration = p_duration
	color = p_color
	z_index = 9

func _process(delta: float) -> void:
	age += delta
	if age >= duration:
		queue_free()
		return
	queue_redraw()

func _draw() -> void:
	var t := clampf(age / duration, 0.0, 1.0)
	var r := max_radius * (0.35 + 0.65 * t)
	var a := 1.0 - t
	draw_circle(Vector2.ZERO, r, Color(color.r, color.g, color.b, 0.22 * a))
	draw_arc(Vector2.ZERO, r, 0, TAU, 48, Color(color.r, color.g, color.b, 0.9 * a), 5.0 * a + 1.0)
	draw_arc(Vector2.ZERO, r * 0.7, 0, TAU, 40, Color(1, 0.9, 0.7, 0.6 * a), 2.0)
