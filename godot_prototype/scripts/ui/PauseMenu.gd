## In-run pause menu (Esc): Resume, Return to Main Menu, Quit Game.
## Pauses the tree while open. Leaving the run and quitting ask for a second click so a stray
## click cannot throw a run away. Main owns what "leave" and "quit" actually do.
class_name PauseMenu
extends CanvasLayer

signal resumed
signal main_menu_requested
signal quit_requested

var is_open: bool = false
var _root: Control
var _info: Label
var _b_resume: Button
var _b_menu: Button
var _b_quit: Button
var _armed: Button = null
var _paused_before: bool = false

const MENU_TEXT := "Return to Main Menu"
const QUIT_TEXT := "Quit Game"

func _init() -> void:
	layer = 35
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false

func _ready() -> void:
	_build()

func _build() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	_root.add_child(ForgeUI.dimmer(0.66))

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(center)
	var card := ForgeUI.panel(36)
	center.add_child(card)
	var col := ForgeUI.vbox(12)
	card.add_child(col)

	var over := ForgeUI.overline("Paused")
	over.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(over)
	var title := ForgeUI.label("Take a breather", 30, ForgeUI.TEXT, true)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(title)
	_info = ForgeUI.label("", 14, ForgeUI.MUTED)
	_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(_info)
	col.add_child(ForgeUI.spacer(10))

	_b_resume = ForgeUI.button("Resume", true, Vector2(320, 52))
	_b_menu = ForgeUI.button(MENU_TEXT, false, Vector2(320, 48))
	_b_quit = ForgeUI.button(QUIT_TEXT, false, Vector2(320, 48))
	for b in [_b_resume, _b_menu, _b_quit]:
		col.add_child(b)
	_b_resume.pressed.connect(resume)
	_b_menu.pressed.connect(func(): _confirm(_b_menu, MENU_TEXT, "Leave this run? Click again"))
	_b_quit.pressed.connect(func(): _confirm(_b_quit, QUIT_TEXT, "Quit the game? Click again"))

	col.add_child(ForgeUI.spacer(2))
	var hint := ForgeUI.label("Esc to resume", 13, ForgeUI.DIM)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(hint)

## Two-step buttons: the first click arms the button, the second one fires it.
func _confirm(b: Button, normal_text: String, armed_text: String) -> void:
	if _armed == b:
		_disarm()
		if b == _b_menu:
			main_menu_requested.emit()
		else:
			quit_requested.emit()
		return
	_disarm()
	_armed = b
	b.text = armed_text

func _disarm() -> void:
	if _armed != null:
		_armed.text = MENU_TEXT if _armed == _b_menu else QUIT_TEXT
		_armed = null

func open(info: String = "") -> void:
	if is_open:
		return
	_info.text = info
	_disarm()
	is_open = true
	visible = true
	_paused_before = get_tree().paused
	get_tree().paused = true
	ForgeUI.fade_in(_root, 0.15)
	_b_resume.call_deferred("grab_focus")

func resume() -> void:
	if not is_open:
		return
	_close()
	resumed.emit()

## Closes without emitting `resumed` (used when the run is being left or the game quit).
func close_silently() -> void:
	if is_open:
		_close()

func _close() -> void:
	is_open = false
	visible = false
	_disarm()
	get_tree().paused = _paused_before

func _unhandled_input(event: InputEvent) -> void:
	if not is_open:
		return
	if event.is_action_pressed("ui_cancel") and not event.is_echo():
		if _armed != null:
			_disarm() # first Esc cancels a pending confirmation
		else:
			resume()
		get_viewport().set_input_as_handled()
