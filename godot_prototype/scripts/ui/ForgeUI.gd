## Shared look for FORGE menus and overlays: palette, fonts, and widget factories.
## Every screen (main menu, consent, floor rating) is built from these so they stay consistent.
class_name ForgeUI
extends RefCounted

# Palette: deep night-blue stone, ember gold accent.
const BG := Color("0a0e16")
const PANEL := Color(0.07, 0.09, 0.135, 0.96)
const PANEL_SOFT := Color(1.0, 1.0, 1.0, 0.035)
const BORDER := Color("273149")
const GOLD := Color("f2c14e")
const GOLD_HI := Color("ffd774")
const EMBER := Color("e8743b")
const TEXT := Color("e8ecf4")
const MUTED := Color("97a2b8")
const DIM := Color("5e6a84")
const INK := Color("1b1406")
const GREEN := Color("6fd39b")

static var _cinzel: Font = null
static var _inter: Font = null

static func cinzel() -> Font:
	if _cinzel == null and ResourceLoader.exists("res://assets/fonts/Cinzel.ttf"):
		_cinzel = load("res://assets/fonts/Cinzel.ttf")
	return _cinzel

static func inter() -> Font:
	if _inter == null and ResourceLoader.exists("res://assets/fonts/Inter.ttf"):
		_inter = load("res://assets/fonts/Inter.ttf")
	return _inter

## Cinzel with extra letter spacing, for titles and small all-caps overlines.
static func spaced(base: Font, spacing: int) -> Font:
	if base == null:
		return null
	var fv := FontVariation.new()
	fv.base_font = base
	fv.spacing_glyph = spacing
	return fv

static func label(text: String, size: int, color: Color = TEXT, heading: bool = false) -> Label:
	var l := Label.new()
	l.text = text
	var f := cinzel() if heading else inter()
	if f:
		l.add_theme_font_override("font", f)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l

## Wrapping paragraph with a fixed width (wrapping labels need a width to lay out).
static func paragraph(text: String, size: int, width: float, color: Color = MUTED) -> Label:
	var l := label(text, size, color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(width, 0)
	l.add_theme_constant_override("line_spacing", 3)
	return l

## Small spaced all-caps label above a title.
static func overline(text: String, color: Color = EMBER) -> Label:
	var l := label(text.to_upper(), 12, color)
	var f := spaced(inter(), 3)
	if f:
		l.add_theme_font_override("font", f)
	return l

static func box(radius: int = 14, bg: Color = PANEL, border: Color = BORDER, border_w: int = 1, pad: int = 0) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(border_w)
	s.set_corner_radius_all(radius)
	s.set_content_margin_all(pad)
	s.anti_aliasing = true
	return s

static func panel(pad: int = 32) -> PanelContainer:
	var p := PanelContainer.new()
	var s := box(16, PANEL, BORDER, 1, pad)
	s.shadow_color = Color(0, 0, 0, 0.55)
	s.shadow_size = 28
	s.shadow_offset = Vector2(0, 10)
	p.add_theme_stylebox_override("panel", s)
	return p

static func vbox(sep: int) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", sep)
	return v

static func hbox(sep: int) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", sep)
	return h

static func spacer(h: float) -> Control:
	var c := Control.new()
	c.custom_minimum_size = Vector2(0, h)
	return c

## primary = filled gold call-to-action; otherwise a quiet outlined button that lights up gold.
static func button(text: String, primary: bool = false, min_size: Vector2 = Vector2(300, 50)) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = min_size
	b.focus_mode = Control.FOCUS_ALL
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	var f := spaced(cinzel(), 1)
	if f:
		b.add_theme_font_override("font", f)
	b.add_theme_font_size_override("font_size", 19 if primary else 16)
	if primary:
		b.add_theme_stylebox_override("normal", box(10, GOLD, GOLD, 0, 12))
		b.add_theme_stylebox_override("hover", box(10, GOLD_HI, GOLD_HI, 0, 12))
		b.add_theme_stylebox_override("focus", box(10, Color(0, 0, 0, 0), Color(1, 0.95, 0.8, 0.9), 2, 12))
		b.add_theme_stylebox_override("pressed", box(10, GOLD.darkened(0.15), GOLD, 0, 12))
		for c in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
			b.add_theme_color_override(c, INK)
	else:
		b.add_theme_stylebox_override("normal", box(10, PANEL_SOFT, BORDER, 1, 12))
		b.add_theme_stylebox_override("hover", box(10, Color(GOLD, 0.09), Color(GOLD, 0.75), 1, 12))
		b.add_theme_stylebox_override("focus", box(10, Color(0, 0, 0, 0), Color(GOLD, 0.75), 1, 12))
		b.add_theme_stylebox_override("pressed", box(10, Color(GOLD, 0.16), GOLD, 1, 12))
		b.add_theme_stylebox_override("disabled", box(10, Color(0, 0, 0, 0), Color(BORDER, 0.5), 1, 12))
		b.add_theme_color_override("font_color", TEXT)
		b.add_theme_color_override("font_hover_color", GOLD_HI)
		b.add_theme_color_override("font_focus_color", GOLD_HI)
		b.add_theme_color_override("font_pressed_color", GOLD_HI)
		b.add_theme_color_override("font_hover_pressed_color", GOLD_HI)
		b.add_theme_color_override("font_disabled_color", DIM)
	return b

## Tab header button: plain text, gold underline when selected.
static func tab_button(text: String, group: ButtonGroup) -> Button:
	var b := Button.new()
	b.text = text
	b.toggle_mode = true
	b.button_group = group
	b.focus_mode = Control.FOCUS_ALL
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	if inter():
		b.add_theme_font_override("font", inter())
	b.add_theme_font_size_override("font_size", 15)
	var idle := box(0, Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 0)
	idle.content_margin_left = 14
	idle.content_margin_right = 14
	idle.content_margin_top = 10
	idle.content_margin_bottom = 12
	var active := idle.duplicate() as StyleBoxFlat
	active.border_color = GOLD
	active.border_width_bottom = 2
	var hover := idle.duplicate() as StyleBoxFlat
	hover.border_color = Color(GOLD, 0.35)
	hover.border_width_bottom = 2
	b.add_theme_stylebox_override("normal", idle)
	b.add_theme_stylebox_override("hover", hover)
	b.add_theme_stylebox_override("pressed", active)
	b.add_theme_stylebox_override("hover_pressed", active)
	b.add_theme_stylebox_override("focus", hover)
	b.add_theme_color_override("font_color", MUTED)
	b.add_theme_color_override("font_hover_color", TEXT)
	b.add_theme_color_override("font_focus_color", TEXT)
	b.add_theme_color_override("font_pressed_color", GOLD)
	b.add_theme_color_override("font_hover_pressed_color", GOLD)
	return b

## A keyboard/mouse key drawn as a small keycap.
static func keycap(text: String) -> PanelContainer:
	var p := PanelContainer.new()
	var s := box(6, Color(1, 1, 1, 0.06), Color(1, 1, 1, 0.16), 1, 0)
	s.border_width_bottom = 3
	s.content_margin_left = 10
	s.content_margin_right = 10
	s.content_margin_top = 4
	s.content_margin_bottom = 4
	p.add_theme_stylebox_override("panel", s)
	var l := label(text, 13, TEXT)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.custom_minimum_size = Vector2(16, 0)
	p.add_child(l)
	return p

## Thin horizontal rule.
static func rule(width: float = 0.0, color: Color = BORDER) -> ColorRect:
	var r := ColorRect.new()
	r.color = color
	r.custom_minimum_size = Vector2(width, 1)
	return r

## Full-screen translucent backdrop that also swallows clicks to whatever is below.
static func dimmer(alpha: float = 0.72) -> ColorRect:
	var d := ColorRect.new()
	d.color = Color(BG, alpha)
	d.set_anchors_preset(Control.PRESET_FULL_RECT)
	d.mouse_filter = Control.MOUSE_FILTER_STOP
	return d

## Toggle styled like the rest of the UI (CheckButton with readable label colours).
static func toggle(text: String, on: bool) -> CheckButton:
	var c := CheckButton.new()
	c.text = text
	c.button_pressed = on
	c.focus_mode = Control.FOCUS_ALL
	c.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	if inter():
		c.add_theme_font_override("font", inter())
	c.add_theme_font_size_override("font_size", 15)
	for k in ["font_color", "font_hover_color", "font_focus_color", "font_pressed_color", "font_hover_pressed_color"]:
		c.add_theme_color_override(k, TEXT)
	c.add_theme_color_override("font_disabled_color", DIM)
	var clear := box(8, Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 6)
	c.add_theme_stylebox_override("normal", clear)
	c.add_theme_stylebox_override("pressed", clear)
	c.add_theme_stylebox_override("hover", box(8, PANEL_SOFT, Color(0, 0, 0, 0), 0, 6))
	c.add_theme_stylebox_override("hover_pressed", box(8, PANEL_SOFT, Color(0, 0, 0, 0), 0, 6))
	c.add_theme_stylebox_override("focus", box(8, Color(0, 0, 0, 0), Color(GOLD, 0.6), 1, 6))
	return c

## Fades a control in. Alpha only: position tweens would fight the parent container's layout.
static func fade_in(node: CanvasItem, duration: float = 0.28) -> Tween:
	node.modulate.a = 0.0
	var tw := node.create_tween()
	tw.tween_property(node, "modulate:a", 1.0, duration).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	return tw
