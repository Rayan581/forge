## Post-floor difficulty rating: "How hard did that floor feel?" (1 = very easy .. 5 = very hard).
## The game is paused while it is open. `ask()` returns the rating, or 0 when the player skips.
## Keyboard: 1-5 to answer, Esc to skip. Stored by Main via TelemetryLogger.set_perceived_difficulty().
class_name FloorRating
extends CanvasLayer

signal answered(value: int)

const LABELS := ["Very easy", "Easy", "Just right", "Hard", "Very hard"]
# Hover accent per answer, cool -> warm.
const TINTS := [Color("5fc9c0"), Color("8fd07a"), Color("f2c14e"), Color("e8913b"), Color("e0584b")]

var is_open: bool = false
var _floor_label: Label
var _root: Control
var _buttons: Array[Button] = []
var _paused_before: bool = false

func _init() -> void:
	layer = 40
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false

func _ready() -> void:
	_build()

func _build() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	_root.add_child(ForgeUI.dimmer(0.6))

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(center)

	var card := ForgeUI.panel(36)
	center.add_child(card)
	var col := ForgeUI.vbox(10)
	card.add_child(col)

	_floor_label = ForgeUI.overline("Floor cleared")
	_floor_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(_floor_label)
	var title := ForgeUI.label("How hard did that floor feel?", 30, ForgeUI.TEXT, true)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(title)
	var sub := ForgeUI.label("Your honest gut feeling helps the study. There is no wrong answer.", 14, ForgeUI.MUTED)
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(sub)
	col.add_child(ForgeUI.spacer(14))

	var row := ForgeUI.hbox(12)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_child(row)
	for i in range(5):
		var b := _answer_button(i)
		row.add_child(b)
		_buttons.append(b)

	col.add_child(ForgeUI.spacer(10))
	var foot := ForgeUI.hbox(10)
	foot.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_child(foot)
	var hint := ForgeUI.label("Press 1–5", 13, ForgeUI.DIM)
	foot.add_child(hint)
	var dot := ForgeUI.label("·", 13, ForgeUI.DIM)
	foot.add_child(dot)
	var skip := Button.new()
	skip.text = "Skip (Esc)"
	skip.flat = true
	skip.focus_mode = Control.FOCUS_NONE
	skip.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	if ForgeUI.inter():
		skip.add_theme_font_override("font", ForgeUI.inter())
	skip.add_theme_font_size_override("font_size", 13)
	skip.add_theme_color_override("font_color", ForgeUI.DIM)
	skip.add_theme_color_override("font_hover_color", ForgeUI.TEXT)
	skip.pressed.connect(func(): _finish(0))
	foot.add_child(skip)

func _answer_button(i: int) -> Button:
	var b := Button.new()
	b.custom_minimum_size = Vector2(122, 108)
	b.focus_mode = Control.FOCUS_ALL
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	var tint: Color = TINTS[i]
	b.add_theme_stylebox_override("normal", ForgeUI.box(12, ForgeUI.PANEL_SOFT, ForgeUI.BORDER, 1, 10))
	b.add_theme_stylebox_override("hover", ForgeUI.box(12, Color(tint, 0.12), tint, 2, 10))
	b.add_theme_stylebox_override("focus", ForgeUI.box(12, Color(tint, 0.12), tint, 2, 10))
	b.add_theme_stylebox_override("pressed", ForgeUI.box(12, Color(tint, 0.25), tint, 2, 10))
	# Number + caption drawn by child labels (Button text is single-line).
	var v := ForgeUI.vbox(4)
	v.set_anchors_preset(Control.PRESET_FULL_RECT)
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(v)
	var num := ForgeUI.label(str(i + 1), 34, ForgeUI.TEXT, true)
	num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	num.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(num)
	var cap := ForgeUI.label(LABELS[i], 13, ForgeUI.MUTED)
	cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(cap)
	b.mouse_entered.connect(func(): num.add_theme_color_override("font_color", tint))
	b.mouse_exited.connect(func(): num.add_theme_color_override("font_color", ForgeUI.TEXT))
	b.focus_entered.connect(func(): num.add_theme_color_override("font_color", tint))
	b.focus_exited.connect(func(): num.add_theme_color_override("font_color", ForgeUI.TEXT))
	b.pressed.connect(func(): _finish(i + 1))
	return b

## Shows the prompt, pauses the game until the player answers. Returns 1..5, or 0 if skipped.
func ask(floor_num: int) -> int:
	_floor_label.text = ("Floor %d cleared" % floor_num).to_upper()
	is_open = true
	visible = true
	_paused_before = get_tree().paused
	get_tree().paused = true
	ForgeUI.fade_in(_root, 0.22)
	var value: int = await answered
	return value

## Same as clicking answer `value` (1..5) or skip (0). Used by keyboard input and tests.
func choose(value: int) -> void:
	_finish(value)

func _finish(value: int) -> void:
	if not is_open:
		return
	is_open = false
	visible = false
	get_tree().paused = _paused_before
	answered.emit(clampi(value, 0, 5))

func _unhandled_input(event: InputEvent) -> void:
	if not is_open or not (event is InputEventKey) or not event.pressed or event.echo:
		return
	var k: int = (event as InputEventKey).keycode
	if k >= KEY_1 and k <= KEY_5:
		_finish(k - KEY_1 + 1)
		get_viewport().set_input_as_handled()
	elif k >= KEY_KP_1 and k <= KEY_KP_5:
		_finish(k - KEY_KP_1 + 1)
		get_viewport().set_input_as_handled()
	elif k == KEY_ESCAPE:
		_finish(0)
		get_viewport().set_input_as_handled()
