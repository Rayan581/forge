## FORGE main menu.
##
## Front screen: title, one-line pitch, four actions. All longer text (how to play, controls, the
## project blurb, data & privacy) lives in the tabbed Field Guide overlay instead of blocking the
## path to the game. The whole UI is built in code from ForgeUI so it matches the consent and
## floor-rating screens.
class_name MainMenu
extends CanvasLayer

signal start_run_requested
signal exit_game_requested
## Consent or "rate each floor" changed from the Data & Privacy tab (already saved to settings).
signal settings_changed

enum Tab { HOW_TO_PLAY, CONTROLS, ABOUT, PRIVACY }

const TAB_TITLES := ["How to Play", "Controls", "About", "Data & Privacy"]
const BACKDROP := "res://assets/ui/menu_backdrop.png"

var settings: GameSettings = null

var _root: Control
var _front: Control
var _guide: Control
var _guide_panel: PanelContainer
var _tab_buttons: Array[Button] = []
var _pages: Array[Control] = []
var _btn_play: Button
var _status_chip: Button
var _title: Label
var _embers: CPUParticles2D
var _portal: Sprite2D
var _hero: AnimatedSprite2D
var _time: float = 0.0
var _consent_toggle: CheckButton
var _rate_toggle: CheckButton
var _privacy_status: Label
var _starting: bool = false

func _ready() -> void:
	layer = 5
	_build()
	_guide.visible = false
	refresh_settings()
	_btn_play.call_deferred("grab_focus")

## Main passes the shared settings object (consent etc.).
func setup(p_settings: GameSettings) -> void:
	settings = p_settings
	refresh_settings()

func is_guide_open() -> bool:
	return _guide != null and _guide.visible

# ------------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------------

func _build() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	_build_backdrop()
	_build_showcase()
	_build_front()
	_build_guide()

func _build_backdrop() -> void:
	var base := ColorRect.new()
	base.color = ForgeUI.BG
	base.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(base)

	if ResourceLoader.exists(BACKDROP):
		var bg := TextureRect.new()
		bg.texture = load(BACKDROP)
		bg.set_anchors_preset(Control.PRESET_FULL_RECT)
		bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		bg.modulate = Color(0.75, 0.72, 0.78)
		_root.add_child(bg)

	# Left-to-right shade so the title column reads cleanly over the art.
	_root.add_child(_gradient_rect(
		[Color(ForgeUI.BG, 0.96), Color(ForgeUI.BG, 0.78), Color(ForgeUI.BG, 0.25)],
		[0.0, 0.45, 1.0], Vector2(0, 0), Vector2(1, 0)))
	# Bottom fade + warm glow rising from the "forge".
	_root.add_child(_gradient_rect(
		[Color(ForgeUI.BG, 0.0), Color(ForgeUI.BG, 0.85)], [0.55, 1.0], Vector2(0, 0), Vector2(0, 1)))
	var glow := _gradient_rect(
		[Color(ForgeUI.EMBER, 0.0), Color(ForgeUI.EMBER, 0.10)], [0.6, 1.0], Vector2(0, 0), Vector2(0, 1))
	_root.add_child(glow)

	_root.add_child(_radial_sprite(Color(ForgeUI.EMBER, 0.16), Vector2(330, 200), Vector2(5.5, 2.2)))

	_embers = CPUParticles2D.new()
	_embers.amount = 70
	_embers.lifetime = 7.0
	_embers.preprocess = 7.0
	_embers.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	_embers.emission_rect_extents = Vector2(700, 8)
	_embers.position = Vector2(640, 740)
	_embers.direction = Vector2(0, -1)
	_embers.spread = 18.0
	_embers.gravity = Vector2(6, -12)
	_embers.initial_velocity_min = 22.0
	_embers.initial_velocity_max = 60.0
	_embers.scale_amount_min = 1.5
	_embers.scale_amount_max = 3.5
	_embers.angular_velocity_min = -40.0
	_embers.angular_velocity_max = 40.0
	var ramp := Gradient.new()
	ramp.set_color(0, Color(1.0, 0.75, 0.35, 0.0))
	ramp.set_color(1, Color(0.9, 0.3, 0.1, 0.0))
	ramp.add_point(0.15, Color(1.0, 0.78, 0.38, 0.9))
	ramp.add_point(0.7, Color(0.95, 0.45, 0.18, 0.55))
	_embers.color_ramp = ramp
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_embers.material = mat
	_root.add_child(_embers)

## Right half of the screen: the exit portal turning behind the skeleton hero, flanked by the five
## enemy archetypes (the game's own sprite frames, nearest-filtered pixel art).
func _build_showcase() -> void:
	var stage := Node2D.new()
	stage.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_root.add_child(stage)

	stage.add_child(_radial_sprite(Color(0.62, 0.35, 0.95, 0.30), Vector2(960, 330), 2.2))
	stage.add_child(_radial_sprite(Color(ForgeUI.EMBER, 0.20), Vector2(960, 610), Vector2(4.2, 0.9)))

	if ResourceLoader.exists("res://assets/sprites/portal_exit.png"):
		_portal = Sprite2D.new()
		_portal.texture = load("res://assets/sprites/portal_exit.png")
		_portal.position = Vector2(960, 330)
		_portal.scale = Vector2(3.4, 3.4)
		_portal.modulate = Color(1, 1, 1, 0.9)
		stage.add_child(_portal)

	# [frames, x, ground y, scale, faces left, brightness]
	var cast := [
		["res://assets/sprites/enemies/swarmer/swarmer_frames.tres", 690, 588, 5.0, false, 0.6],
		["res://assets/sprites/crawler/crawler_frames.tres", 772, 574, 6.0, false, 0.7],
		["res://assets/sprites/enemies/skirmisher/skirmisher_frames.tres", 852, 596, 5.5, false, 0.64],
		["res://assets/sprites/pyromancer/pyromancer_frames.tres", 1100, 578, 6.0, true, 0.7],
		["res://assets/sprites/enemies/brute/brute_frames.tres", 1196, 588, 5.0, true, 0.64],
	]
	for c in cast:
		var spr := _actor(c[0], Vector2(c[1], c[2]), c[3], c[4])
		if spr:
			spr.modulate = Color(c[5], c[5], c[5] * 1.08)
			stage.add_child(spr)
	_hero = _actor("res://assets/sprites/player/player_frames.tres", Vector2(976, 646), 6.5, false)
	if _hero:
		stage.add_child(_hero)

## AnimatedSprite2D playing "idle", positioned by its feet (ground point).
func _actor(frames_path: String, ground: Vector2, scl: float, face_left: bool) -> AnimatedSprite2D:
	if not ResourceLoader.exists(frames_path):
		return null
	var a := AnimatedSprite2D.new()
	a.sprite_frames = load(frames_path)
	a.scale = Vector2(scl, scl)
	a.flip_h = face_left
	a.centered = true
	var tex := a.sprite_frames.get_frame_texture("idle", 0)
	var h := float(tex.get_height()) if tex else 16.0
	a.position = ground - Vector2(0, h * scl * 0.5)
	a.play("idle")
	a.speed_scale = randf_range(0.8, 1.1)
	# Soft contact shadow under the feet.
	var sh := _radial_sprite(Color(0, 0, 0, 0.55), Vector2(0, h * 0.5 - 1), Vector2(0.22, 0.06))
	sh.show_behind_parent = true
	a.add_child(sh)
	return a

## Sprite with a soft radial falloff texture (glows and shadows). Base texture is 128 px.
func _radial_sprite(color: Color, pos: Vector2, scl: Variant) -> Sprite2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 1.0])
	g.colors = PackedColorArray([color, Color(color, 0.0)])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	gt.width = 128
	gt.height = 128
	var sp := Sprite2D.new()
	sp.texture = gt
	sp.position = pos
	sp.scale = scl if scl is Vector2 else Vector2(scl, scl)
	sp.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	return sp

func _process(delta: float) -> void:
	if not visible:
		return
	_time += delta
	if _portal:
		_portal.rotation += delta * 0.35
		var pulse := 3.4 + sin(_time * 1.6) * 0.06
		_portal.scale = Vector2(pulse, pulse)

func _gradient_rect(colors: Array, offsets: Array, from: Vector2, to: Vector2) -> TextureRect:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(offsets)
	g.colors = PackedColorArray(colors)
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill_from = from
	gt.fill_to = to
	gt.width = 64
	gt.height = 64
	var r := TextureRect.new()
	r.texture = gt
	r.set_anchors_preset(Control.PRESET_FULL_RECT)
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_SCALE
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r

func _build_front() -> void:
	_front = Control.new()
	_front.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(_front)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 120)
	margin.add_theme_constant_override("margin_top", 40)
	margin.add_theme_constant_override("margin_bottom", 70)
	_front.add_child(margin)

	var col := ForgeUI.vbox(0)
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	margin.add_child(col)

	col.add_child(ForgeUI.overline("A dungeon that learns you"))
	col.add_child(ForgeUI.spacer(4))
	_title = ForgeUI.label("FORGE", 112, ForgeUI.GOLD, true)
	var tf := ForgeUI.spaced(ForgeUI.cinzel(), 10)
	if tf:
		_title.add_theme_font_override("font", tf)
	_title.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.55))
	_title.add_theme_constant_override("shadow_offset_x", 0)
	_title.add_theme_constant_override("shadow_offset_y", 6)
	col.add_child(_title)
	col.add_child(ForgeUI.label("Every floor is forged from how you play.", 19, ForgeUI.MUTED))
	col.add_child(ForgeUI.spacer(44))

	var buttons := ForgeUI.vbox(12)
	buttons.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	col.add_child(buttons)
	_btn_play = ForgeUI.button("Enter the Dungeon", true, Vector2(320, 58))
	_btn_play.pressed.connect(_on_play)
	buttons.add_child(_btn_play)
	buttons.add_child(ForgeUI.spacer(4))
	var b_how := ForgeUI.button("How to Play", false, Vector2(320, 48))
	b_how.pressed.connect(func(): open_guide(Tab.HOW_TO_PLAY))
	buttons.add_child(b_how)
	var b_priv := ForgeUI.button("Data & Privacy", false, Vector2(320, 48))
	b_priv.pressed.connect(func(): open_guide(Tab.PRIVACY))
	buttons.add_child(b_priv)
	var b_quit := ForgeUI.button("Quit", false, Vector2(320, 48))
	b_quit.pressed.connect(_on_quit)
	buttons.add_child(b_quit)

	# Footer: version + institution (left), data-sharing status chip (right).
	var footer := ForgeUI.label("v%s  ·  FAST-NUCES Islamabad  ·  Final Year Project" % BuildInfo.version(), 12, ForgeUI.DIM)
	footer.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	footer.position = Vector2(120, 720 - 44)
	_front.add_child(footer)

	_status_chip = Button.new()
	_status_chip.flat = true
	_status_chip.focus_mode = Control.FOCUS_NONE
	_status_chip.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	if ForgeUI.inter():
		_status_chip.add_theme_font_override("font", ForgeUI.inter())
	_status_chip.add_theme_font_size_override("font_size", 12)
	_status_chip.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_status_chip.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_status_chip.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_status_chip.offset_right = -40
	_status_chip.offset_bottom = -30
	_status_chip.pressed.connect(func(): open_guide(Tab.PRIVACY))
	_front.add_child(_status_chip)

func _build_guide() -> void:
	_guide = Control.new()
	_guide.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(_guide)
	_guide.add_child(ForgeUI.dimmer(0.72))

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_guide.add_child(center)
	_guide_panel = ForgeUI.panel(0)
	_guide_panel.custom_minimum_size = Vector2(900, 540)
	center.add_child(_guide_panel)

	var col := ForgeUI.vbox(0)
	_guide_panel.add_child(col)

	# Header: tabs + close.
	var header_margin := MarginContainer.new()
	header_margin.add_theme_constant_override("margin_left", 22)
	header_margin.add_theme_constant_override("margin_right", 14)
	header_margin.add_theme_constant_override("margin_top", 10)
	col.add_child(header_margin)
	var header := ForgeUI.hbox(4)
	header_margin.add_child(header)
	var group := ButtonGroup.new()
	for i in range(TAB_TITLES.size()):
		var tb := ForgeUI.tab_button(TAB_TITLES[i], group)
		var idx := i
		tb.pressed.connect(func(): _show_tab(idx))
		header.add_child(tb)
		_tab_buttons.append(tb)
	var grow := Control.new()
	grow.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(grow)
	var close := ForgeUI.button("✕", false, Vector2(40, 40))
	close.add_theme_font_size_override("font_size", 15)
	if ForgeUI.inter():
		close.add_theme_font_override("font", ForgeUI.inter())
	close.tooltip_text = "Close (Esc)"
	close.pressed.connect(close_guide)
	header.add_child(close)
	col.add_child(ForgeUI.rule(0))

	var body := MarginContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	for side in ["margin_left", "margin_right"]:
		body.add_theme_constant_override(side, 40)
	body.add_theme_constant_override("margin_top", 30)
	body.add_theme_constant_override("margin_bottom", 26)
	col.add_child(body)
	var stack := Control.new()
	stack.custom_minimum_size = Vector2(820, 410)
	body.add_child(stack)

	_pages = [_page_how_to_play(), _page_controls(), _page_about(), _page_privacy()]
	for p in _pages:
		p.set_anchors_preset(Control.PRESET_FULL_RECT)
		stack.add_child(p)

func _page_how_to_play() -> Control:
	var page := ForgeUI.vbox(22)
	var head := ForgeUI.vbox(6)
	head.add_child(ForgeUI.overline("Your goal"))
	head.add_child(ForgeUI.label("Descend as deep as you can", 28, ForgeUI.TEXT, true))
	page.add_child(head)

	var cards := ForgeUI.hbox(16)
	page.add_child(cards)
	cards.add_child(_step_card("01", "Clear the rooms", "Defeat every enemy in a room. Grab red flasks to heal and watch for floor spikes."))
	cards.add_child(_step_card("02", "Find the portal", "Clear the exit room, then step into the purple portal to reach the next floor."))
	cards.add_child(_step_card("03", "It adapts to you", "Floors 1–5 learn how you play. From floor 6 on, every floor is generated for you."))

	var foes := ForgeUI.hbox(10)
	foes.add_child(ForgeUI.label("Foes", 13, ForgeUI.DIM))
	for n in ["Crawler", "Pyromancer", "Brute", "Skirmisher", "Swarmer"]:
		foes.add_child(_chip(n))
	page.add_child(foes)
	return page

func _step_card(num: String, title: String, text: String) -> PanelContainer:
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", ForgeUI.box(12, ForgeUI.PANEL_SOFT, ForgeUI.BORDER, 1, 22))
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var v := ForgeUI.vbox(10)
	card.add_child(v)
	v.add_child(ForgeUI.label(num, 26, ForgeUI.GOLD, true))
	v.add_child(ForgeUI.label(title, 19, ForgeUI.TEXT, true))
	v.add_child(ForgeUI.paragraph(text, 14, 220))
	return card

func _chip(text: String) -> PanelContainer:
	var p := PanelContainer.new()
	var s := ForgeUI.box(20, Color(1, 1, 1, 0.04), ForgeUI.BORDER, 1, 0)
	s.content_margin_left = 12
	s.content_margin_right = 12
	s.content_margin_top = 3
	s.content_margin_bottom = 3
	p.add_theme_stylebox_override("panel", s)
	p.add_child(ForgeUI.label(text, 13, ForgeUI.MUTED))
	return p

func _page_controls() -> Control:
	var page := ForgeUI.vbox(18)
	var head := ForgeUI.vbox(6)
	head.add_child(ForgeUI.overline("Keyboard & mouse"))
	head.add_child(ForgeUI.label("Controls", 28, ForgeUI.TEXT, true))
	page.add_child(head)
	page.add_child(_control_row("Move", [["W", "A", "S", "D"], ["↑", "←", "↓", "→"]]))
	page.add_child(_control_row("Attack", [["Left click"], ["J"]]))
	page.add_child(_control_row("Dodge roll", [["Space"], ["Shift"]]))
	if BuildInfo.dev_tools_enabled():
		page.add_child(_control_row("Developer panel", [["Tab"]]))
	page.add_child(ForgeUI.spacer(6))
	page.add_child(ForgeUI.paragraph("Tip: dodging makes you briefly untouchable. Time it through fireballs and Brute slams.", 14, 760, ForgeUI.DIM))
	return page

func _control_row(action: String, alternatives: Array) -> Control:
	var row := ForgeUI.hbox(0)
	var name_l := ForgeUI.label(action, 16, ForgeUI.TEXT)
	name_l.custom_minimum_size = Vector2(200, 0)
	row.add_child(name_l)
	var keys := ForgeUI.hbox(8)
	row.add_child(keys)
	for i in range(alternatives.size()):
		if i > 0:
			var orl := ForgeUI.label("or", 13, ForgeUI.DIM)
			orl.custom_minimum_size = Vector2(28, 0)
			orl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			keys.add_child(orl)
		for k in alternatives[i]:
			keys.add_child(ForgeUI.keycap(str(k)))
	var wrap := ForgeUI.vbox(12)
	wrap.add_child(row)
	wrap.add_child(ForgeUI.rule(0, Color(ForgeUI.BORDER, 0.6)))
	return wrap

func _page_about() -> Control:
	var page := ForgeUI.vbox(14)
	page.add_child(ForgeUI.overline("The project"))
	page.add_child(ForgeUI.label("Personalized Procedural Content Generation", 26, ForgeUI.TEXT, true))
	page.add_child(ForgeUI.label("via Reinforcement Learning", 18, ForgeUI.GOLD, true))
	page.add_child(ForgeUI.spacer(4))
	page.add_child(ForgeUI.paragraph(
		"After every floor, a PPO policy looks at how the last one went and tunes the next: enemy " +
		"health, damage, speed and aggression, hazards, healing, room count and which enemies appear. " +
		"The aim is a challenge that stays right for you instead of one fixed difficulty curve.",
		15, 800))
	page.add_child(ForgeUI.spacer(6))
	var facts := ForgeUI.hbox(36)
	facts.add_child(_fact("Institution", "FAST-NUCES Islamabad"))
	facts.add_child(_fact("Department", "Artificial Intelligence"))
	facts.add_child(_fact("Build", BuildInfo.version()))
	page.add_child(facts)
	page.add_child(ForgeUI.spacer(6))
	page.add_child(ForgeUI.paragraph("Art and font credits are listed in the project's CREDITS files.", 13, 800, ForgeUI.DIM))
	return page

func _fact(k: String, v: String) -> VBoxContainer:
	var b := ForgeUI.vbox(4)
	b.add_child(ForgeUI.label(k.to_upper(), 11, ForgeUI.DIM))
	b.add_child(ForgeUI.label(v, 15, ForgeUI.TEXT))
	return b

func _page_privacy() -> Control:
	var page := ForgeUI.vbox(14)
	page.add_child(ForgeUI.overline("Your data"))
	page.add_child(ForgeUI.label("Data & Privacy", 28, ForgeUI.TEXT, true))
	_privacy_status = ForgeUI.label("", 15, ForgeUI.MUTED)
	page.add_child(_privacy_status)
	page.add_child(ForgeUI.spacer(2))

	_consent_toggle = ForgeUI.toggle("Share anonymous gameplay data with the FORGE study", false)
	_consent_toggle.toggled.connect(_on_consent_toggled)
	page.add_child(_consent_toggle)
	_rate_toggle = ForgeUI.toggle("Ask me to rate how hard each floor felt (1–5)", true)
	_rate_toggle.toggled.connect(_on_rate_toggled)
	page.add_child(_rate_toggle)
	page.add_child(ForgeUI.spacer(4))
	page.add_child(ForgeUI.paragraph(
		"Recorded per floor: time, deaths, damage, kills, the difficulty settings you played and your rating. " +
		"Never recorded: your name, accounts, IP address or hardware identifiers. A random ID groups your sessions. " +
		"Everything is stored on this PC; the study only uses sessions where sharing was on.",
		14, 800))
	page.add_child(ForgeUI.spacer(6))
	var open_btn := ForgeUI.button("Open data folder", false, Vector2(220, 42))
	open_btn.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	open_btn.pressed.connect(func(): OS.shell_open(ProjectSettings.globalize_path("user://")))
	page.add_child(open_btn)
	return page

# ------------------------------------------------------------------------------------------------
# Behaviour
# ------------------------------------------------------------------------------------------------

func open_guide(tab: int = Tab.HOW_TO_PLAY) -> void:
	_guide.visible = true
	_show_tab(tab)
	ForgeUI.fade_in(_guide, 0.2)
	_tab_buttons[tab].grab_focus()

func close_guide() -> void:
	_guide.visible = false
	_btn_play.grab_focus()

func _show_tab(tab: int) -> void:
	for i in range(_pages.size()):
		_pages[i].visible = (i == tab)
	_tab_buttons[tab].set_pressed_no_signal(true)

## Re-reads settings into the chip and the privacy tab (call after the consent screen).
func refresh_settings() -> void:
	if _status_chip == null:
		return
	var sharing := settings != null and settings.consent_given
	var decided := settings != null and settings.consent_decided
	if sharing:
		_status_chip.text = "●  Sharing gameplay data"
		_status_chip.add_theme_color_override("font_color", ForgeUI.GREEN)
	else:
		_status_chip.text = "○  Not sharing gameplay data" if decided else "○  Data sharing not set"
		_status_chip.add_theme_color_override("font_color", ForgeUI.DIM)
	_status_chip.add_theme_color_override("font_hover_color", ForgeUI.TEXT)
	_status_chip.visible = settings != null
	_consent_toggle.set_pressed_no_signal(sharing)
	_rate_toggle.set_pressed_no_signal(settings == null or settings.rate_floors)
	_rate_toggle.disabled = not sharing
	_privacy_status.text = ("You are sharing anonymous gameplay data. Thank you!" if sharing
		else "You are not sharing data. The game works exactly the same either way.")

func _on_consent_toggled(on: bool) -> void:
	if settings == null:
		return
	settings.set_consent(on)
	refresh_settings()
	settings_changed.emit()

func _on_rate_toggled(on: bool) -> void:
	if settings == null:
		return
	settings.rate_floors = on
	settings.save_to_disk()
	settings_changed.emit()

func _on_play() -> void:
	if _starting:
		return
	_starting = true
	var tw := create_tween().set_parallel(true)
	tw.tween_property(_root, "modulate:a", 0.0, 0.4).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	tw.tween_property(_front, "position:x", -40.0, 0.4).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	await tw.finished
	visible = false
	_embers.emitting = false
	_root.modulate.a = 1.0
	_front.position.x = 0.0
	_starting = false
	start_run_requested.emit()

func _on_quit() -> void:
	exit_game_requested.emit()
	get_tree().quit()

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("ui_cancel") and is_guide_open():
		close_guide()
		get_viewport().set_input_as_handled()
