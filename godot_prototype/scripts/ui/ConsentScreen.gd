## First-launch consent prompt for the FORGE playtest study.
## Both answers have equal visual weight on purpose (no nudging). Emits `decided(true/false)`;
## the caller stores it in GameSettings. Changeable later in Main Menu -> Data & Privacy.
class_name ConsentScreen
extends CanvasLayer

signal decided(consent: bool)

var _root: Control

func _init() -> void:
	layer = 30
	process_mode = Node.PROCESS_MODE_ALWAYS

func _ready() -> void:
	_build()
	ForgeUI.fade_in(_root, 0.35)

func _build() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	_root.add_child(ForgeUI.dimmer(0.82))

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(center)
	var card := ForgeUI.panel(40)
	center.add_child(card)
	var col := ForgeUI.vbox(12)
	card.add_child(col)

	col.add_child(ForgeUI.overline("Before you play"))
	col.add_child(ForgeUI.label("Help us study adaptive difficulty", 30, ForgeUI.TEXT, true))
	col.add_child(ForgeUI.paragraph(
		"FORGE is a Final Year Project at FAST-NUCES Islamabad. With your permission, the anonymous " +
		"gameplay statistics from this computer can be used to train and evaluate the system.",
		15, 600))
	col.add_child(ForgeUI.spacer(6))

	var lists := ForgeUI.hbox(28)
	col.add_child(lists)
	lists.add_child(_list("What is recorded", ForgeUI.GREEN, [
		"Per floor: time, deaths, damage, kills",
		"The difficulty settings you played",
		"Your 1–5 difficulty rating after a floor",
	]))
	lists.add_child(_list("Never recorded", ForgeUI.EMBER, [
		"Your name, account or e-mail",
		"IP address or hardware identifiers",
		"Anything outside this game",
	]))
	col.add_child(ForgeUI.spacer(4))
	col.add_child(ForgeUI.paragraph(
		"Data stays in the game's folder on this PC until it is handed to the FORGE team. " +
		"A random ID groups your sessions. You can change your answer any time in Data & Privacy.",
		13, 600, ForgeUI.DIM))
	col.add_child(ForgeUI.spacer(10))

	var row := ForgeUI.hbox(14)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_child(row)
	var no := ForgeUI.button("Don't share", false, Vector2(240, 50))
	var yes := ForgeUI.button("Share my gameplay data", false, Vector2(300, 50))
	row.add_child(no)
	row.add_child(yes)
	no.pressed.connect(func(): _decide(false))
	yes.pressed.connect(func(): _decide(true))
	yes.call_deferred("grab_focus")

func _list(title: String, accent: Color, items: Array) -> VBoxContainer:
	var v := ForgeUI.vbox(6)
	v.custom_minimum_size = Vector2(286, 0)
	var t := ForgeUI.label(title, 14, accent)
	v.add_child(t)
	for it in items:
		var h := ForgeUI.hbox(8)
		var dot := ForgeUI.label("•", 14, accent)
		h.add_child(dot)
		h.add_child(ForgeUI.label(str(it), 14, ForgeUI.TEXT))
		v.add_child(h)
	return v

func _decide(consent: bool) -> void:
	decided.emit(consent)
	var tw := create_tween()
	tw.tween_property(_root, "modulate:a", 0.0, 0.2)
	await tw.finished
	queue_free()
