class_name BSPGenerator
extends RefCounted
## Rule-based BSP (Binary Space Partitioning) layout generator: the "strong non-adaptive
## procedural-generation baseline" the committee asked for. Python reference (same algorithm, used by
## the ML evaluation): ml/layouts.py -> bsp_layout().
##
## 1. Split a rectangle recursively (split ratio 0.35-0.65 of the side, a minimum leaf size, depth
##    limit 4). Wide rectangles split vertically, tall ones horizontally, square-ish ones at random.
##    Retried until the tree has min_rooms..max_rooms leaves (default 5-9, the game's room range).
## 2. One room per leaf. Rooms are placed on the game's room grid BOTTOM-UP: the two children of a
##    split are laid side by side (vertical split -> left | right, horizontal -> top / bottom) and
##    joined by ONE door between a room on the facing edge of each child. The result is connected by
##    construction (a tree, like the FORGE generator), rooms never share a cell, and the door graph
##    follows the BSP tree (sibling leaves first, then sibling subtrees).
## 3. Room size comes from the leaf size: a bigger leaf gives a bigger room (WIDTH_STEPS / HEIGHT_STEPS
##    ladders, without the largest step on floors with 8+ rooms, exactly like _assign_sizes).
## 4. Start = a random dead-end room; positions are shifted so the start sits at grid (0, 0), which is
##    what DungeonGenerator._layout_world and Main expect. The exit (deepest room) is picked by
##    DungeonGenerator with the same rule as for FORGE layouts.
##
## Uses the global RNG (randf / randi), so seed(s) makes a layout reproducible, like DungeonGenerator.
## Output is plain data; DungeonGenerator turns it into RoomData (see DungeonGenerator._bsp_layout).

const SPLIT_MIN: float = 0.35
const SPLIT_MAX: float = 0.65
const MAX_DEPTH: int = 4
const ATTEMPTS: int = 200
const OPP := {"N": "S", "S": "N", "E": "W", "W": "E"}

var min_rooms: int = 5
var max_rooms: int = 9
## Number of split attempts the last generate() call needed (diagnostics / tests).
var last_attempts: int = 0


class BSPNode:
	var rect: Rect2
	var left: BSPNode = null
	var right: BSPNode = null
	var vertical: bool = true # split line is vertical -> children are left / right

	func _init(r: Rect2) -> void:
		rect = r

	func is_leaf() -> bool:
		return left == null

	func leaf_count() -> int:
		return 1 if is_leaf() else left.leaf_count() + right.leaf_count()


func _split(node: BSPNode, min_leaf: float, depth: int) -> void:
	if depth >= MAX_DEPTH:
		return
	var w: float = node.rect.size.x
	var h: float = node.rect.size.y
	var can_v: bool = w >= 2.0 * min_leaf
	var can_h: bool = h >= 2.0 * min_leaf
	if not (can_v or can_h):
		return
	var vertical: bool
	if can_v and can_h:
		vertical = w / h > 1.25 or (h / w <= 1.25 and randf() < 0.5)
	else:
		vertical = can_v
	var ratio: float = randf_range(SPLIT_MIN, SPLIT_MAX)
	var p: Vector2 = node.rect.position
	if vertical:
		var cut: float = clampf(w * ratio, min_leaf, w - min_leaf)
		node.left = BSPNode.new(Rect2(p, Vector2(cut, h)))
		node.right = BSPNode.new(Rect2(p + Vector2(cut, 0.0), Vector2(w - cut, h)))
	else:
		var cut: float = clampf(h * ratio, min_leaf, h - min_leaf)
		node.left = BSPNode.new(Rect2(p, Vector2(w, cut)))
		node.right = BSPNode.new(Rect2(p + Vector2(0.0, cut), Vector2(w, h - cut)))
	node.vertical = vertical
	_split(node.left, min_leaf, depth + 1)
	_split(node.right, min_leaf, depth + 1)


func _make_tree() -> BSPNode:
	var root := BSPNode.new(Rect2(Vector2.ZERO, Vector2(randf_range(80.0, 120.0), randf_range(60.0, 90.0))))
	_split(root, randf_range(22.0, 30.0), 0)
	return root


## Bottom-up grid placement. Returns {"cells": {Vector2i: BSPNode}, "doors": [[Vector2i, String, Vector2i]]}.
func _place(node: BSPNode) -> Dictionary:
	if node.is_leaf():
		return {"cells": {Vector2i.ZERO: node}, "doors": []}
	var a: Dictionary = _place(node.left)
	var b: Dictionary = _place(node.right)
	# facing edges: a's east (or south) edge, b's west (or north) edge
	var axis: int = 0 if node.vertical else 1
	var a_max: int = -1 << 30
	var b_min: int = 1 << 30
	for c in a.cells.keys():
		a_max = maxi(a_max, c[axis])
	for c in b.cells.keys():
		b_min = mini(b_min, c[axis])
	var a_edge: Array = []
	var b_edge: Array = []
	for c in a.cells.keys():
		if c[axis] == a_max:
			a_edge.append(c)
	for c in b.cells.keys():
		if c[axis] == b_min:
			b_edge.append(c)
	a_edge.sort()
	b_edge.sort()
	var ca: Vector2i = a_edge[randi() % a_edge.size()]
	var cb: Vector2i = b_edge[randi() % b_edge.size()]
	var step: Vector2i = Vector2i(1, 0) if node.vertical else Vector2i(0, 1)
	var off: Vector2i = ca + step - cb # moves cb right next to ca; b then lies entirely beyond a
	var cells: Dictionary = a.cells.duplicate()
	for c in b.cells.keys():
		cells[c + off] = b.cells[c]
	var doors: Array = a.doors.duplicate()
	for d in b.doors:
		doors.append([d[0] + off, d[1], d[2] + off])
	doors.append([ca, "E" if node.vertical else "S", ca + step])
	return {"cells": cells, "doors": doors}


## One BSP layout as plain data:
## {"sizes": {Vector2i: Vector2}, "doors": {Vector2i: {"N": bool, ...}}, "leaf_rects": {Vector2i: Rect2}}
## with the start room at Vector2i.ZERO.
func generate() -> Dictionary:
	var placed: Dictionary = {}
	last_attempts = 0
	for attempt in range(ATTEMPTS):
		last_attempts = attempt + 1
		var root := _make_tree()
		var n: int = root.leaf_count()
		if n < min_rooms or n > max_rooms:
			continue
		placed = _place(root)
		break
	if placed.is_empty(): # practically unreachable; keep the game running with the last tree
		placed = _place(_make_tree())
	var cells: Dictionary = placed.cells
	var doors: Dictionary = {}
	for c in cells.keys():
		doors[c] = {"N": false, "S": false, "E": false, "W": false}
	for d in placed.doors:
		doors[d[0]][d[1]] = true
		doors[d[2]][OPP[d[1]]] = true
	# start = a random dead end (degree 1); deterministic order for a given seed
	var ends: Array = []
	for c in cells.keys():
		var deg := 0
		for dn in doors[c].keys():
			if doors[c][dn]:
				deg += 1
		if deg == 1:
			ends.append(c)
	if ends.is_empty():
		ends = cells.keys()
	ends.sort()
	var start: Vector2i = ends[randi() % ends.size()]
	# sizes from leaf sizes (relative to the smallest / largest leaf of this dungeon)
	var n_rooms: int = cells.size()
	var cap_w: int = DungeonGenerator.WIDTH_STEPS.size() - (1 if n_rooms >= 8 else 0)
	var cap_h: int = DungeonGenerator.HEIGHT_STEPS.size() - (1 if n_rooms >= 8 else 0)
	var w_lo := INF
	var w_hi := -INF
	var h_lo := INF
	var h_hi := -INF
	for c in cells.keys():
		var r: Rect2 = cells[c].rect
		w_lo = minf(w_lo, r.size.x)
		w_hi = maxf(w_hi, r.size.x)
		h_lo = minf(h_lo, r.size.y)
		h_hi = maxf(h_hi, r.size.y)
	var out_sizes: Dictionary = {}
	var out_doors: Dictionary = {}
	var out_rects: Dictionary = {}
	for c in cells.keys():
		var r: Rect2 = cells[c].rect
		var fw: float = (r.size.x - w_lo) / maxf(w_hi - w_lo, 0.000001)
		var fh: float = (r.size.y - h_lo) / maxf(h_hi - h_lo, 0.000001)
		var wi: int = clampi(int(round(fw * float(cap_w - 1))), 0, cap_w - 1)
		var hi: int = clampi(int(round(fh * float(cap_h - 1))), 0, cap_h - 1)
		var key: Vector2i = c - start
		out_sizes[key] = Vector2(DungeonGenerator.WIDTH_STEPS[wi], DungeonGenerator.HEIGHT_STEPS[hi])
		out_doors[key] = doors[c]
		out_rects[key] = r
	return {"sizes": out_sizes, "doors": out_doors, "leaf_rects": out_rects}
