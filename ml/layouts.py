"""Stage 6a: dungeon layouts. A Python port of the game's generator, the NEW BSP baseline generator,
solvability checks and layout-variety metrics.

Both generators output the SAME room model the game uses (``DungeonGenerator.gd``): one room per
grid cell ``(x, y)``, doors only between grid neighbours, sizes from WIDTH_STEPS / HEIGHT_STEPS,
start room, exit room = deepest room by door-graph BFS. So the BSP generator can later be ported to
GDScript and fed to ``Room.gd`` unchanged (the Godot client is not touched here).

* ``random_walk_layout`` - port of ``DungeonGenerator._random_layout`` + the 24-attempt depth search
  + ``_pick_exit`` + ``_assign_sizes`` (FORGE's current generator).
* ``bsp_layout`` - Binary Space Partitioning (GDScript port: godot_prototype/scripts/BSPGenerator.gd): recursively split a rectangle (split ratio 0.35-0.65,
  min leaf size, depth limit) until it has 5-9 leaves; one room per leaf; room size from the leaf's
  size. Rooms are placed on the grid bottom-up: the two children of a split are laid side by side
  (vertical split -> left/right, horizontal -> top/bottom) and joined by ONE door between the pair of
  rooms that face each other across the split line. The result is connected by construction (a
  tree), never overlaps, and follows the split structure of the BSP tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

WIDTH_STEPS = [608, 672, 736, 800, 864, 928, 992, 1056, 1120]
HEIGHT_STEPS = [416, 480, 544, 608, 672]
LAYOUT_ATTEMPTS = 24
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}


@dataclass
class Room:
    pos: tuple
    doors: dict = field(default_factory=lambda: dict(N=False, S=False, E=False, W=False))
    size: tuple = (800, 544)
    depth: int = 0
    kind: str = "combat"


@dataclass
class Layout:
    rooms: dict  # (x, y) -> Room
    start: tuple
    exit: tuple
    generator: str

    def neighbours(self, pos):
        for d, (dx, dy) in DIRS.items():
            if self.rooms[pos].doors[d]:
                yield (pos[0] + dx, pos[1] + dy)


def _connect(rooms, a, d):
    dx, dy = DIRS[d]
    b = (a[0] + dx, a[1] + dy)
    if b not in rooms:
        rooms[b] = Room(b)
    rooms[a].doors[d] = True
    rooms[b].doors[OPP[d]] = True
    return b


def bfs_depths(rooms, start) -> dict:
    depths = {start: 0}
    q = [start]
    while q:
        cur = q.pop(0)
        for d, (dx, dy) in DIRS.items():
            if rooms[cur].doors[d]:
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in rooms and nxt not in depths:
                    depths[nxt] = depths[cur] + 1
                    q.append(nxt)
    return depths


def _pick_exit(rooms, depths, max_d, start=(0, 0)):
    best, best_key = start, -1
    for pos in rooms:
        if depths.get(pos, -1) != max_d:
            continue
        dx, dy = pos[0] - start[0], pos[1] - start[1]
        key = abs(dx) + abs(dy) + (100 if (dx != 0 and dy != 0) else 0)
        if key > best_key:
            best, best_key = pos, key
    return best


def _assign_sizes(rooms, rng, n):
    cap_w = len(WIDTH_STEPS) - (1 if n >= 8 else 0)
    cap_h = len(HEIGHT_STEPS) - (1 if n >= 8 else 0)
    bias = {"exit": (3, 1), "combat": (1, 0), "treasure": (-1, 0), "start": (-1, 0)}
    for r in rooms.values():
        bw, bh = bias.get(r.kind, (0, 0))
        wi = int(np.clip(rng.integers(0, cap_w) + bw, 0, cap_w - 1))
        hi = int(np.clip(rng.integers(0, cap_h) + bh, 0, cap_h - 1))
        r.size = (WIDTH_STEPS[wi], HEIGHT_STEPS[hi])


def _finish(rooms, start, generator, rng, sizes=True) -> Layout:
    depths = bfs_depths(rooms, start)
    max_d = max(depths.values())
    for p, r in rooms.items():
        r.depth = depths.get(p, -1)
    ex = _pick_exit(rooms, depths, max_d, start)
    rooms[start].kind = "start"
    rooms[ex].kind = "exit"
    if sizes:
        _assign_sizes(rooms, rng, len(rooms))
    return Layout(rooms, start, ex, generator)


# ---------------------------------------------------------------------------------------------
# FORGE generator (port of DungeonGenerator.gd)
# ---------------------------------------------------------------------------------------------
def _random_walk(count, rng):
    rooms = {(0, 0): Room((0, 0))}
    queue = [(0, 0)]
    dirs = list(DIRS)
    while len(rooms) < count and queue:
        pick = len(queue) - 1 if rng.random() < 0.5 else int(rng.integers(0, len(queue)))
        parent = queue[pick]
        rng.shuffle(dirs)
        placed = False
        for d in dirs:
            dx, dy = DIRS[d]
            if (parent[0] + dx, parent[1] + dy) not in rooms:
                queue.append(_connect(rooms, parent, d))
                placed = True
                break
        if not placed:
            queue.pop(pick)
    return rooms


def random_walk_layout(count: int, rng: np.random.Generator) -> Layout:
    min_depth = 2 if count >= 3 else (1 if count == 2 else 0)
    goal = max(min_depth, int(np.ceil(count * 0.5)))
    best, best_score = None, -1
    for attempt in range(LAYOUT_ATTEMPTS):
        rooms = _random_walk(count, rng)
        depths = bfs_depths(rooms, (0, 0))
        max_d = max(depths.values())
        cand = _pick_exit(rooms, depths, max_d)
        hidden = cand[0] != 0 and cand[1] != 0
        score = max_d * 2 + (1 if hidden else 0)
        if max_d >= min_depth and score > best_score:
            best, best_score = rooms, score
        if max_d >= goal and (hidden or attempt >= LAYOUT_ATTEMPTS // 2):
            best = rooms
            break
    if best is None:
        best = {(0, 0): Room((0, 0))}
        pos = (0, 0)
        for _ in range(count - 1):
            pos = _connect(best, pos, "E")
    return _finish(best, (0, 0), "forge", rng)


# ---------------------------------------------------------------------------------------------
# BSP generator (new baseline)
# ---------------------------------------------------------------------------------------------
@dataclass
class _Node:
    x: float
    y: float
    w: float
    h: float
    left: "_Node | None" = None
    right: "_Node | None" = None
    vertical: bool = True  # True: split line is vertical (children left / right)

    def leaves(self):
        if self.left is None:
            return [self]
        return self.left.leaves() + self.right.leaves()


def _split(node: _Node, rng, min_leaf, depth, max_depth):
    if depth >= max_depth:
        return
    can_v, can_h = node.w >= 2 * min_leaf, node.h >= 2 * min_leaf
    if not (can_v or can_h):
        return
    if can_v and can_h:
        vertical = node.w / node.h > 1.25 or (node.h / node.w <= 1.25 and rng.random() < 0.5)
    else:
        vertical = can_v
    ratio = float(rng.uniform(0.35, 0.65))
    if vertical:
        cut = float(np.clip(node.w * ratio, min_leaf, node.w - min_leaf))
        node.left = _Node(node.x, node.y, cut, node.h)
        node.right = _Node(node.x + cut, node.y, node.w - cut, node.h)
    else:
        cut = float(np.clip(node.h * ratio, min_leaf, node.h - min_leaf))
        node.left = _Node(node.x, node.y, node.w, cut)
        node.right = _Node(node.x, node.y + cut, node.w, node.h - cut)
    node.vertical = vertical
    _split(node.left, rng, min_leaf, depth + 1, max_depth)
    _split(node.right, rng, min_leaf, depth + 1, max_depth)


def _place(node: _Node, rng):
    """Bottom-up grid placement. Returns (cells: {cell: leaf}, doors: [(cell_a, dir, cell_b)])."""
    if node.left is None:
        return {(0, 0): node}, []
    a_cells, a_doors = _place(node.left, rng)
    b_cells, b_doors = _place(node.right, rng)
    if node.vertical:  # b goes to the right of a; join a's east-most to b's west-most cell
        ax = max(c[0] for c in a_cells)
        a_edge = [c for c in a_cells if c[0] == ax]
        bx = min(c[0] for c in b_cells)
        b_edge = [c for c in b_cells if c[0] == bx]
        ca = a_edge[int(rng.integers(len(a_edge)))]
        cb = b_edge[int(rng.integers(len(b_edge)))]
        off = (ca[0] + 1 - cb[0], ca[1] - cb[1])
        d = "E"
    else:  # b goes below a
        ay = max(c[1] for c in a_cells)
        a_edge = [c for c in a_cells if c[1] == ay]
        by = min(c[1] for c in b_cells)
        b_edge = [c for c in b_cells if c[1] == by]
        ca = a_edge[int(rng.integers(len(a_edge)))]
        cb = b_edge[int(rng.integers(len(b_edge)))]
        off = (ca[0] - cb[0], ca[1] + 1 - cb[1])
        d = "S"
    shift = lambda c: (c[0] + off[0], c[1] + off[1])  # noqa: E731
    b_cells = {shift(c): leaf for c, leaf in b_cells.items()}
    b_doors = [(shift(x), dd, shift(y)) for x, dd, y in b_doors]
    # a straight join can make b overlap a; if so push b further out along the split axis
    step = (1, 0) if node.vertical else (0, 1)
    gap = 0
    while set(b_cells) & set(a_cells):
        gap += 1
        b_cells = {(c[0] + step[0], c[1] + step[1]): leaf for c, leaf in b_cells.items()}
        b_doors = [((x[0] + step[0], x[1] + step[1]), dd, (y[0] + step[0], y[1] + step[1]))
                   for x, dd, y in b_doors]  # fmt: skip
    cb_new = (ca[0] + step[0] * (1 + gap), ca[1] + step[1] * (1 + gap))
    doors = a_doors + b_doors
    if gap == 0:
        doors.append((ca, d, cb_new))
        cells = {**a_cells, **b_cells}
    else:  # bridge the gap with corridor rooms (rare; keeps the graph connected)
        cells = {**a_cells, **b_cells}
        prev = ca
        for g in range(1, gap + 1):
            mid = (ca[0] + step[0] * g, ca[1] + step[1] * g)
            cells[mid] = None
            doors.append((prev, d, mid))
            prev = mid
        doors.append((prev, d, cb_new))
    return cells, doors


def _bsp_once(rng, min_rooms, max_rooms):
    W = float(rng.uniform(80, 120))
    H = float(rng.uniform(60, 90))
    min_leaf = float(rng.uniform(22, 30))
    root = _Node(0.0, 0.0, W, H)
    _split(root, rng, min_leaf, 0, max_depth=4)
    return root


def bsp_layout(rng: np.random.Generator, min_rooms: int = 5, max_rooms: int = 9) -> Layout:
    for _ in range(200):
        root = _bsp_once(rng, min_rooms, max_rooms)
        cells, doors = _place(root, rng)
        if min_rooms <= len(cells) <= max_rooms:
            break
    rooms = {c: Room(c) for c in cells}
    for a, d, b in doors:
        rooms[a].doors[d] = True
        rooms[b].doors[OPP[d]] = True
    # room size from the leaf size (larger leaf -> larger room); corridor rooms get small sizes
    leaves = [lf for lf in cells.values() if lf is not None]
    ws = np.array([lf.w for lf in leaves])
    hs = np.array([lf.h for lf in leaves])
    n_cap = (
        1 if len(cells) >= 8 else 0
    )  # like _assign_sizes / BSPGenerator.gd: no largest step at 8+
    cap_w, cap_h = len(WIDTH_STEPS) - n_cap, len(HEIGHT_STEPS) - n_cap
    for c, lf in cells.items():
        if lf is None:
            rooms[c].size = (WIDTH_STEPS[0], HEIGHT_STEPS[0])
            continue
        fw = (lf.w - ws.min()) / max(ws.max() - ws.min(), 1e-9)
        fh = (lf.h - hs.min()) / max(hs.max() - hs.min(), 1e-9)
        rooms[c].size = (
            WIDTH_STEPS[int(round(fw * (cap_w - 1)))],
            HEIGHT_STEPS[int(round(fh * (cap_h - 1)))],
        )
    # start = a random dead-end room (degree 1) of the tree; exit = deepest room from it
    ends = sorted(c for c, r in rooms.items() if sum(r.doors.values()) == 1) or sorted(rooms)
    start = ends[int(rng.integers(len(ends)))]
    lay = _finish(rooms, start, "bsp", rng, sizes=False)
    return lay


# ---------------------------------------------------------------------------------------------
# Solvability and variety
# ---------------------------------------------------------------------------------------------
def solvable(lay: Layout) -> dict:
    depths = bfs_depths(lay.rooms, lay.start)
    doors_ok = all(
        (not r.doors[d]) or ((p[0] + DIRS[d][0], p[1] + DIRS[d][1]) in lay.rooms)
        for p, r in lay.rooms.items()
        for d in DIRS
    )
    sym_ok = all(
        (not r.doors[d]) or lay.rooms[(p[0] + DIRS[d][0], p[1] + DIRS[d][1])].doors[OPP[d]]
        for p, r in lay.rooms.items()
        for d in DIRS
        if (p[0] + DIRS[d][0], p[1] + DIRS[d][1]) in lay.rooms
    )
    checks = dict(
        connected=len(depths) == len(lay.rooms),
        exit_reachable=lay.exit in depths,
        exit_not_start=lay.exit != lay.start,
        doors_valid=doors_ok and sym_ok,
        no_overlap=len(set(lay.rooms)) == len(lay.rooms),
    )
    checks["ok"] = all(checks.values())
    return checks


def metrics(lay: Layout) -> dict:
    deg = np.array([sum(r.doors.values()) for r in lay.rooms.values()])
    areas = np.array([r.size[0] * r.size[1] for r in lay.rooms.values()], dtype=float)
    depths = bfs_depths(lay.rooms, lay.start)
    return dict(
        rooms=len(lay.rooms),
        path_len=depths.get(lay.exit, -1),
        dead_ends=int(np.sum(deg == 1)),
        branching=float(deg[deg > 1].mean()) if np.any(deg > 1) else 0.0,
        size_var=float(np.var(areas / 1e5)),
        bbox=int(
            (max(p[0] for p in lay.rooms) - min(p[0] for p in lay.rooms) + 1)
            * (max(p[1] for p in lay.rooms) - min(p[1] for p in lay.rooms) + 1)
        ),  # fmt: skip
    )


def occupancy(lay: Layout, size: int = 21) -> np.ndarray:
    """Room cells on a fixed canvas centred on the start room (for pairwise layout distance)."""
    g = np.zeros((size, size), dtype=bool)
    c = size // 2
    for p in lay.rooms:
        x, y = p[0] - lay.start[0] + c, p[1] - lay.start[1] + c
        if 0 <= x < size and 0 <= y < size:
            g[y, x] = True
    return g


def pairwise_distance(lays, max_pairs: int = 3000, seed: int = 0) -> float:
    """Mean normalised Hamming distance (Jaccard distance) between occupancy grids, over the
    8 symmetries of the square (so a mirrored copy counts as the same shape)."""
    rng = np.random.default_rng(seed)
    grids = [occupancy(lay) for lay in lays]
    n = len(grids)
    if n < 2:
        return 0.0
    pairs = [(int(rng.integers(n)), int(rng.integers(n))) for _ in range(max_pairs)]
    vals = []
    for i, j in pairs:
        if i == j:
            continue
        a = grids[i]
        best = 1.0
        for k in range(4):
            for flip in (False, True):
                b = np.rot90(grids[j], k)
                b = np.fliplr(b) if flip else b
                union = np.logical_or(a, b).sum()
                inter = np.logical_and(a, b).sum()
                best = min(best, 1.0 - inter / max(union, 1))
        vals.append(best)
    return float(np.mean(vals))


def variety_table(n: int, seed: int, room_counts_forge, static_rooms=6, bsp_min=5, bsp_max=9):
    """Layouts for FORGE (room counts as the policy picks them), static (6 rooms) and BSP."""
    rng = np.random.default_rng(seed)
    gens = {
        "forge_ppo": [
            random_walk_layout(int(room_counts_forge[i % len(room_counts_forge)]), rng)
            for i in range(n)
        ],  # fmt: skip
        "static_8pct": [random_walk_layout(static_rooms, rng) for _ in range(n)],
        "bsp": [bsp_layout(rng, bsp_min, bsp_max) for _ in range(n)],
    }
    rows = {}
    for name, lays in gens.items():
        ms = [metrics(lay) for lay in lays]
        sol = [solvable(lay)["ok"] for lay in lays]
        sig = {tuple(sorted(occupancy(lay).flatten().nonzero()[0])) for lay in lays}
        rows[name] = dict(
            n=n,
            solvable_pct=100.0 * float(np.mean(sol)),
            rooms_mean=float(np.mean([m["rooms"] for m in ms])),
            rooms_std=float(np.std([m["rooms"] for m in ms])),
            path_len=float(np.mean([m["path_len"] for m in ms])),
            dead_ends=float(np.mean([m["dead_ends"] for m in ms])),
            branching=float(np.mean([m["branching"] for m in ms])),
            size_var=float(np.mean([m["size_var"] for m in ms])),
            unique_shapes_pct=100.0 * len(sig) / n,
            pairwise_dist=pairwise_distance(lays, seed=seed),
        )
    return rows, gens
