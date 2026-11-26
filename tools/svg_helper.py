"""Small helper library for building clean, consistent SVG diagrams."""
import math

FONT = "Liberation Sans, Arial, sans-serif"

PALETTE = {
    "ink":        "#152238",
    "ink_soft":   "#3d4b63",
    "line":       "#8a97ab",
    "bg":         "#ffffff",
    "panel":      "#f4f6fa",
    "navy":       "#1e3a5f",
    "navy_fill":  "#e8eef7",
    "teal":       "#0d7d8f",
    "teal_fill":  "#e2f4f2",
    "amber":      "#b4690e",
    "amber_fill": "#fbe9d3",
    "rose":       "#9c3848",
    "rose_fill":  "#f7e3e6",
    "slate_fill": "#eef1f5",
    "slate_line": "#5b6b82",
}


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def rect_boundary_point(cx, cy, w, h, dx, dy, pad=0):
    """Point where a ray from rect center (cx,cy) toward (dx,dy) exits the rect."""
    hw, hh = w / 2 + pad, h / 2 + pad
    if dx == 0 and dy == 0:
        return cx, cy
    tx = hw / abs(dx) if dx != 0 else float("inf")
    ty = hh / abs(dy) if dy != 0 else float("inf")
    t = min(tx, ty)
    return cx + dx * t, cy + dy * t


def node_box(cx, cy, w, h, lines, fill, stroke, text_color=None, rx=10,
             font_size=15.5, bold_first=False, line_height=19, stroke_w=1.6,
             sub_lines=None, sub_color=None, sub_size=12.5):
    """Rounded rect node with (optionally multi-line) centered label."""
    text_color = text_color or PALETTE["ink"]
    sub_color = sub_color or PALETTE["ink_soft"]
    n = len(lines)
    total_h = n * line_height
    start_y = cy - total_h / 2 + line_height * 0.78
    out = [f'<rect x="{cx-w/2:.1f}" y="{cy-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" '
           f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>']
    for i, ln in enumerate(lines):
        w_flag = "700" if (bold_first and i == 0) else "600"
        fs = font_size if (bold_first and i == 0) else font_size - 1
        out.append(f'<text x="{cx:.1f}" y="{start_y + i*line_height:.1f}" text-anchor="middle" '
                   f'font-family="{FONT}" font-size="{fs}" font-weight="{w_flag}" fill="{text_color}">{esc(ln)}</text>')
    if sub_lines:
        sy = start_y + n * line_height + 2
        for j, ln in enumerate(sub_lines):
            out.append(f'<text x="{cx:.1f}" y="{sy + j*(sub_size+3):.1f}" text-anchor="middle" '
                       f'font-family="{FONT}" font-size="{sub_size}" fill="{sub_color}">{esc(ln)}</text>')
    return "\n".join(out)


def arrow_defs():
    return '''
    <marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#33465f"/>
    </marker>
    <marker id="arrowTeal" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#0d7d8f"/>
    </marker>
    <marker id="arrowAmber" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#b4690e"/>
    </marker>
    <marker id="arrowRose" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#9c3848"/>
    </marker>
    '''


def straight_arrow(x1, y1, x2, y2, color="#33465f", marker="url(#arrow)", dash=None, width=2.0):
    d = f'stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width}" {d} marker-end="{marker}"/>')


def curved_arrow(x1, y1, x2, y2, bend=40, color="#33465f", marker="url(#arrow)", dash=None, width=2.0):
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1
    nx, ny = -dy / length, dx / length
    cx, cy = mx + nx * bend, my + ny * bend
    d = f'stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="{width}" {d} marker-end="{marker}"/>')


def label(x, y, text, size=12.5, color=None, anchor="middle", weight="600", italic=False, bg=None, pad_x=6, pad_y=3):
    color = color or PALETTE["ink_soft"]
    style = ' font-style="italic"' if italic else ""
    pieces = []
    if bg:
        w = len(text) * size * 0.56 + pad_x * 2
        if anchor == "middle":
            bx = x - w / 2
        elif anchor == "start":
            bx = x - pad_x
        else:
            bx = x - w + pad_x
        pieces.append(f'<rect x="{bx:.1f}" y="{y-size:.1f}" width="{w:.1f}" height="{size+pad_y*2:.1f}" '
                      f'rx="4" fill="{bg}" opacity="0.92"/>')
    pieces.append(f'<text x="{x:.1f}" y="{y+pad_y:.1f}" text-anchor="{anchor}" font-family="{FONT}" '
                  f'font-size="{size}" font-weight="{weight}" fill="{color}"{style}>{esc(text)}</text>')
    return "\n".join(pieces)


def svg_header(width, height, bg=None):
    bg = bg or PALETTE["bg"]
    return (f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="{FONT}">\n<defs>{arrow_defs()}</defs>\n'
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>\n')


def svg_footer():
    return "</svg>"
