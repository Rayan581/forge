#!/usr/bin/env python3
"""Rebuilds the sprite strips + SpriteFrames .tres used by Player, Enemy, Pickup and Hazard.
Source art: /home/claude/asset_packs (Enemy_Animations_Set + 2D Pixel Dungeon Asset Pack).
Run from anywhere:  python3 tools/build_sprite_frames.py
"""
import os
from PIL import Image

SRC = "/home/claude/asset_packs"
ENEMY_SET = f"{SRC}/Enemy_Animations_Set"
PACK = f"{SRC}/2D Pixel Dungeon Asset Pack"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "godot_prototype")
SPR = os.path.join(ROOT, "assets", "sprites")


def clean_corners(im):
    """The monster/priest frames carry a red 'frame guide' pixel group in each corner."""
    im = im.convert("RGBA")
    w, h = im.size
    for y in range(h):
        for x in range(w):
            near_corner = (x <= 2 or x >= w - 3) and (y <= 2 or y >= h - 3)
            if near_corner and im.getpixel((x, y))[:3] == (188, 76, 81):
                im.putpixel((x, y), (0, 0, 0, 0))
    return im


def make_strip(frames, out_path):
    fw, fh = frames[0].size
    strip = Image.new("RGBA", (fw * len(frames), fh), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f, (i * fw, 0))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    strip.save(out_path)
    return fw, fh


def split(path, fw):
    im = Image.open(path).convert("RGBA")
    return [im.crop((i * fw, 0, (i + 1) * fw, im.height)) for i in range(im.width // fw)]


def write_tres(out_path, sheets, anims):
    """sheets: {key: (res_path, fw, fh)}; anims: [(name, sheet_key, [frame idx], fps, loop)]"""
    ext, subs, body = [], [], []
    keys = list(sheets)
    for i, k in enumerate(keys):
        ext.append(f'[ext_resource type="Texture2D" path="{sheets[k][0]}" id="{i + 1}_{k}"]')
    n = 0
    for (name, k, idxs, fps, loop) in anims:
        _, fw, fh = sheets[k]
        fr = []
        for idx in idxs:
            n += 1
            subs.append(f'[sub_resource type="AtlasTexture" id="AtlasTexture_{n}"]\n'
                        f'atlas = ExtResource("{keys.index(k) + 1}_{k}")\n'
                        f'region = Rect2({idx * fw}, 0, {fw}, {fh})')
            fr.append('{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_%d")\n}' % n)
        body.append('{\n"frames": [%s],\n"loop": %s,\n"name": &"%s",\n"speed": %.1f\n}'
                    % (", ".join(fr), "true" if loop else "false", name, fps))
    text = f'[gd_resource type="SpriteFrames" load_steps={len(ext) + len(subs) + 1} format=3]\n\n'
    text += "\n".join(ext) + "\n\n" + "\n\n".join(subs) + "\n\n[resource]\nanimations = [" + ", ".join(body) + "]\n"
    with open(out_path, "w") as f:
        f.write(text)


def res(p):
    return "res://" + os.path.relpath(p, ROOT).replace(os.sep, "/")


# ---------------- Player: skeleton1 (32x32 strips) ----------------
pdir = os.path.join(SPR, "player")
os.makedirs(pdir, exist_ok=True)
sheets = {}
counts = {}
for name, src in [("idle", "idle"), ("move", "movement"), ("attack", "attack"), ("hurt", "take_damage"), ("death", "death")]:
    frs = split(f"{ENEMY_SET}/enemies-skeleton1_{src}.png", 32)
    out = os.path.join(pdir, f"player_{name}.png")
    make_strip(frs, out)
    sheets[name] = (res(out), 32, 32)
    counts[name] = len(frs)
write_tres(os.path.join(pdir, "player_frames.tres"), sheets, [
    ("idle", "idle", list(range(counts["idle"])), 8.0, True),
    ("move", "move", list(range(counts["move"])), 14.0, True),
    # frames 0-2 are the anticipation (idle-like); the slash arc is on source frames 6-7,
    # i.e. index 3-4 here. 6 frames @ 30 fps = 0.2 s, arc (hit) at 0.10 s.
    ("attack", "attack", list(range(3, counts["attack"])), 30.0, False),
    ("hurt", "hurt", list(range(counts["hurt"])), 20.0, False),
    ("death", "death", list(range(counts["death"])), 16.0, False),
])

# ---------------- Crawler / Pyromancer (16x16, idle only) ----------------
def idle16(folder, prefix, outdir, outname):
    frs = [clean_corners(Image.open(f"{folder}/{prefix}_{i}.png")) for i in range(1, 5)]
    out = os.path.join(SPR, outdir, f"{outname}_idle.png")
    make_strip(frs, out)
    return (res(out), 16, 16)

M = f"{PACK}/Character_animation/monsters_idle"
PR = f"{PACK}/Character_animation/priests_idle"
for outdir, folder, prefix, fps_idle, fps_move in [
    ("crawler", f"{M}/skeleton1/v1", "skeleton_v1", 6.0, 12.0),
    ("pyromancer", f"{PR}/priest2/v1", "priest2_v1", 6.0, 9.0),
]:
    sh = {"idle": idle16(folder, prefix, outdir, outdir)}
    write_tres(os.path.join(SPR, outdir, f"{outdir}_frames.tres"), sh, [
        ("idle", "idle", [0, 1, 2, 3], fps_idle, True),
        ("move", "idle", [0, 1, 2, 3], fps_move, True),
        ("attack", "idle", [0, 1, 2, 3], 16.0, False),
        ("hurt", "idle", [0], 5.0, False),
        ("death", "idle", [0], 5.0, False),
    ])

# ---------------- New archetypes (existing strips) ----------------
for arch, fw, fh in [("brute", 32, 32), ("skirmisher", 16, 20), ("swarmer", 16, 16)]:
    d = os.path.join(SPR, "enemies", arch)
    sh = {"idle": (res(f"{d}/{arch}_idle.png"), fw, fh), "run": (res(f"{d}/{arch}_run.png"), fw, fh)}
    write_tres(os.path.join(d, f"{arch}_frames.tres"), sh, [
        ("idle", "idle", [0, 1, 2, 3], 6.0, True),
        ("move", "run", [0, 1, 2, 3], 10.0, True),
        ("attack", "run", [0, 1, 2, 3], 14.0, False),
        ("hurt", "idle", [0], 5.0, False),
        ("death", "idle", [0], 5.0, False),
    ])

# ---------------- Items / hazards ----------------
I = f"{PACK}/items and trap_animation"
fl = [Image.open(f"{I}/flasks/flasks_1_{i}.png").convert("RGBA") for i in range(1, 5)]
out = os.path.join(SPR, "items", "potion_health.png")
make_strip(fl, out)
write_tres(os.path.join(SPR, "items", "potion_frames.tres"), {"s": (res(out), 16, 16)},
           [("idle", "s", [0, 1, 2, 3], 6.0, True)])

# peaks_1 extended, 2 mid, 3 retracted, 4 emerging.
pk = [Image.open(f"{I}/peaks/peaks_{i}.png").convert("RGBA") for i in range(1, 5)]
out = os.path.join(SPR, "hazards", "spikes.png")
make_strip(pk, out)
write_tres(os.path.join(SPR, "hazards", "spikes_frames.tres"), {"s": (res(out), 16, 16)}, [
    ("idle", "s", [0], 1.0, True),                      # armed: fully extended
    ("stab", "s", [1, 3, 2, 3, 1, 0], 18.0, False),     # retract then punch out (played on each hit)
])
print("built")
