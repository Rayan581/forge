"""
Generate high quality pixel-art sprites and dungeon tile textures for FORGE prototype.
Outputs to x:/FAST Tasks/FYP/godot_prototype/assets/sprites/
"""
import os
import math
from PIL import Image, ImageDraw

OUTPUT_DIR = r"x:\FAST Tasks\FYP\godot_prototype\assets\sprites"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_player_sprite():
    size = (48, 48)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = 24, 24
    
    # 1. Soft Shadow
    draw.ellipse([cx - 15, cy + 9, cx + 15, cy + 19], fill=(0, 0, 0, 90))
    
    # 2. Cloak / Cape background
    draw.polygon([(cx - 10, cy - 2), (cx + 10, cy - 2), (cx + 12, cy + 16), (cx - 12, cy + 16)], fill=(20, 45, 90))
    draw.polygon([(cx - 8, cy), (cx + 8, cy), (cx + 10, cy + 15), (cx - 10, cy + 15)], fill=(32, 65, 125))
    
    # 3. Armored Torso / Breastplate
    draw.rounded_rectangle([cx - 10, cy - 6, cx + 10, cy + 10], radius=4, fill=(45, 75, 135), outline=(25, 45, 80), width=1)
    # Gold breastplate emblem / trim
    draw.line([(cx, cy - 4), (cx, cy + 6)], fill=(220, 180, 50), width=2)
    draw.line([(cx - 5, cy), (cx + 5, cy)], fill=(220, 180, 50), width=2)
    
    # 4. Pauldrons (Shoulders)
    draw.ellipse([cx - 15, cy - 8, cx - 7, cy + 2], fill=(120, 140, 170), outline=(50, 60, 80), width=1)
    draw.ellipse([cx - 13, cy - 6, cx - 9, cy - 1], fill=(180, 200, 230)) # highlight
    draw.ellipse([cx + 7, cy - 8, cx + 15, cy + 2], fill=(120, 140, 170), outline=(50, 60, 80), width=1)
    draw.ellipse([cx + 9, cy - 6, cx + 13, cy - 1], fill=(180, 200, 230)) # highlight
    
    # 5. Knight Helmet / Head
    draw.ellipse([cx - 9, cy - 19, cx + 9, cy - 3], fill=(130, 150, 175), outline=(40, 50, 70), width=1)
    # Helmet dome highlight
    draw.ellipse([cx - 6, cy - 17, cx + 1, cy - 11], fill=(190, 210, 235))
    # Visor Slit
    draw.rounded_rectangle([cx - 7, cy - 11, cx + 7, cy - 7], radius=2, fill=(20, 25, 35))
    # Glowing visor eye-slit (amber gold)
    draw.line([(cx - 5, cy - 9), (cx + 5, cy - 9)], fill=(255, 210, 60), width=2)
    draw.point([(cx - 2, cy - 9), (cx + 2, cy - 9)], fill=(255, 255, 220))
    # Helmet Crest / Feather plume
    draw.polygon([(cx - 2, cy - 22), (cx + 2, cy - 22), (cx + 1, cy - 17), (cx - 1, cy - 17)], fill=(210, 50, 60))
    
    # 6. Belt & Buckle
    draw.line([(cx - 9, cy + 8), (cx + 9, cy + 8)], fill=(75, 45, 25), width=2)
    draw.rectangle([cx - 2, cy + 7, cx + 2, cy + 9], fill=(230, 190, 60))
    
    # 7. Sword on Right Hip / Hand
    # Sword blade pointing down-right
    draw.line([(cx + 13, cy), (cx + 19, cy + 12)], fill=(210, 225, 240), width=2)
    draw.line([(cx + 14, cy + 1), (cx + 18, cy + 11)], fill=(255, 255, 255), width=1) # shine
    # Crossguard
    draw.line([(cx + 10, cy + 2), (cx + 15, cy - 2)], fill=(220, 175, 45), width=2)
    # Pommel
    draw.point((cx + 11, cy - 2), fill=(240, 200, 60))
    
    # 8. Left Shield on Hand
    draw.ellipse([cx - 16, cy + 1, cx - 9, cy + 9], fill=(45, 80, 145), outline=(220, 180, 50), width=1)
    draw.point((cx - 13, cy + 5), fill=(255, 220, 80))
    
    img.save(os.path.join(OUTPUT_DIR, "player.png"))
    print("Created player.png")

def create_melee_crawler_sprite():
    size = (48, 48)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = 24, 25
    
    # 1. Shadow
    draw.ellipse([cx - 16, cy + 8, cx + 16, cy + 18], fill=(0, 0, 0, 100))
    
    # 2. Back spikes / chitin plates
    draw.polygon([(cx - 12, cy - 8), (cx - 18, cy - 16), (cx - 8, cy - 10)], fill=(70, 15, 25))
    draw.polygon([(cx + 12, cy - 8), (cx + 18, cy - 16), (cx + 8, cy - 10)], fill=(70, 15, 25))
    draw.polygon([(cx, cy - 10), (cx, cy - 20), (cx + 4, cy - 10)], fill=(90, 20, 30))
    
    # 3. Beast Claws / Forelegs
    for (lx, ly, rx, ry) in [
        (cx - 14, cy + 2, cx - 20, cy + 10),
        (cx + 14, cy + 2, cx + 20, cy + 10),
        (cx - 12, cy + 8, cx - 18, cy + 16),
        (cx + 12, cy + 8, cx + 18, cy + 16),
    ]:
        draw.line([(lx, ly), (rx, ry)], fill=(40, 10, 15), width=3)
        draw.polygon([(rx - 1, ry - 1), (rx + 2, ry + 2), (rx - 2, ry + 2)], fill=(200, 190, 180)) # claw
    
    # 4. Main Body / Demonic Carapace
    draw.ellipse([cx - 14, cy - 10, cx + 14, cy + 10], fill=(160, 28, 42), outline=(60, 10, 18), width=2)
    # Carapace chitin layers
    draw.arc([cx - 10, cy - 8, cx + 10, cy + 2], start=20, end=160, fill=(210, 50, 65), width=2)
    draw.arc([cx - 8, cy - 3, cx + 8, cy + 7], start=20, end=160, fill=(210, 50, 65), width=2)
    
    # 5. Demonic Horns
    draw.polygon([(cx - 8, cy - 9), (cx - 15, cy - 18), (cx - 4, cy - 10)], fill=(220, 195, 140), outline=(80, 50, 20))
    draw.polygon([(cx + 8, cy - 9), (cx + 15, cy - 18), (cx + 4, cy - 10)], fill=(220, 195, 140), outline=(80, 50, 20))
    
    # 6. Glowing Eyes
    draw.ellipse([cx - 8, cy - 4, cx - 3, cy + 1], fill=(255, 215, 30))
    draw.point((cx - 5, cy - 2), fill=(10, 0, 0)) # pupil
    draw.point((cx - 6, cy - 3), fill=(255, 255, 220)) # reflection
    
    draw.ellipse([cx + 3, cy - 4, cx + 8, cy + 1], fill=(255, 215, 30))
    draw.point((cx + 5, cy - 2), fill=(10, 0, 0)) # pupil
    draw.point((cx + 4, cy - 3), fill=(255, 255, 220))
    
    # 7. Snarl / Fangs
    draw.polygon([(cx - 6, cy + 4), (cx + 6, cy + 4), (cx, cy + 8)], fill=(30, 5, 8))
    draw.polygon([(cx - 4, cy + 4), (cx - 2, cy + 7), (cx - 1, cy + 4)], fill=(240, 240, 230))
    draw.polygon([(cx + 1, cy + 4), (cx + 2, cy + 7), (cx + 4, cy + 4)], fill=(240, 240, 230))
    
    img.save(os.path.join(OUTPUT_DIR, "enemy_crawler.png"))
    print("Created enemy_crawler.png")

def create_ranged_pyromancer_sprite():
    size = (48, 48)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = 24, 25
    
    # 1. Shadow with subtle fiery aura
    draw.ellipse([cx - 14, cy + 9, cx + 14, cy + 19], fill=(0, 0, 0, 90))
    draw.ellipse([cx - 16, cy + 8, cx + 16, cy + 20], fill=(230, 70, 20, 35))
    
    # 2. Flowing Robes (Deep violet / obsidian)
    draw.polygon([(cx - 11, cy - 4), (cx + 11, cy - 4), (cx + 15, cy + 16), (cx - 15, cy + 16)], fill=(55, 20, 75))
    draw.polygon([(cx - 9, cy), (cx + 9, cy), (cx + 13, cy + 15), (cx - 13, cy + 15)], fill=(75, 30, 95))
    # Fiery runic robe trim
    draw.line([(cx - 15, cy + 15), (cx + 15, cy + 15)], fill=(240, 110, 30), width=2)
    draw.line([(cx - 13, cy + 13), (cx + 13, cy + 13)], fill=(255, 190, 50), width=1)
    
    # 3. Robe sleeves
    draw.polygon([(cx - 11, cy - 2), (cx - 18, cy + 6), (cx - 13, cy + 8), (cx - 8, cy + 2)], fill=(55, 20, 75))
    draw.polygon([(cx + 11, cy - 2), (cx + 18, cy + 6), (cx + 13, cy + 8), (cx + 8, cy + 2)], fill=(55, 20, 75))
    
    # 4. Cultist Hood & Cowl
    draw.ellipse([cx - 10, cy - 19, cx + 10, cy - 2], fill=(45, 15, 60), outline=(25, 8, 35), width=2)
    # Hood peak
    draw.polygon([(cx - 5, cy - 18), (cx + 5, cy - 18), (cx, cy - 23)], fill=(45, 15, 60))
    # Dark Cowl opening
    draw.ellipse([cx - 7, cy - 14, cx + 7, cy - 4], fill=(15, 5, 20))
    
    # 5. Glowing Fiery Eyes
    draw.ellipse([cx - 6, cy - 10, cx - 2, cy - 7], fill=(255, 60, 20))
    draw.point((cx - 4, cy - 9), fill=(255, 240, 120))
    draw.ellipse([cx + 2, cy - 10, cx + 6, cy - 7], fill=(255, 60, 20))
    draw.point((cx + 4, cy - 9), fill=(255, 240, 120))
    
    # 6. Floating Fiery Orbs / Spells in hands
    # Left Flame
    draw.ellipse([cx - 20, cy + 3, cx - 14, cy + 9], fill=(255, 80, 20, 200))
    draw.ellipse([cx - 19, cy + 4, cx - 15, cy + 8], fill=(255, 200, 40))
    draw.point((cx - 17, cy + 6), fill=(255, 255, 240))
    # Right Flame
    draw.ellipse([cx + 14, cy + 3, cx + 20, cy + 9], fill=(255, 80, 20, 200))
    draw.ellipse([cx + 15, cy + 4, cx + 19, cy + 8], fill=(255, 200, 40))
    draw.point((cx + 17, cy + 6), fill=(255, 255, 240))
    
    img.save(os.path.join(OUTPUT_DIR, "enemy_pyromancer.png"))
    print("Created enemy_pyromancer.png")

def create_fireball_projectile():
    size = (24, 24)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = 12, 12
    # Outer fire aura
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(240, 60, 20, 120))
    # Mid flame
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(255, 120, 20, 220))
    # Hot inner flame
    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(255, 220, 40, 255))
    # Core
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 255, 240, 255))
    
    img.save(os.path.join(OUTPUT_DIR, "projectile_fireball.png"))
    print("Created projectile_fireball.png")

def create_floor_tiles():
    # 64x64 Seamless Stone Brick Floor
    def make_brick_tile(base_rgb, mortar_rgb, highlight_rgb, shadow_rgb):
        img = Image.new("RGBA", (64, 64), mortar_rgb)
        draw = ImageDraw.Draw(img)
        
        # Brick rows: 4 rows of 16px high
        # Row 0: y=1 to 14
        # Row 1: y=17 to 30
        # Row 2: y=33 to 46
        # Row 3: y=49 to 62
        brick_bounds = [
            # row 0 (offset 0)
            (1, 1, 30, 14), (33, 1, 62, 14),
            # row 1 (offset 16)
            (1, 17, 14, 30), (17, 17, 46, 30), (49, 17, 62, 30),
            # row 2 (offset 8)
            (1, 33, 24, 46), (27, 33, 56, 46), (59, 33, 62, 46),
            # row 3 (offset 20)
            (1, 49, 18, 62), (21, 49, 50, 62), (53, 49, 62, 62)
        ]
        
        for idx, (x1, y1, x2, y2) in enumerate(brick_bounds):
            # Subtle variation per brick
            var = ((idx * 7) % 11) - 5
            r = max(0, min(255, base_rgb[0] + var))
            g = max(0, min(255, base_rgb[1] + var))
            b = max(0, min(255, base_rgb[2] + var))
            draw.rectangle([x1, y1, x2, y2], fill=(r, g, b))
            # Bevel highlights (top and left)
            draw.line([(x1, y1), (x2, y1)], fill=highlight_rgb, width=1)
            draw.line([(x1, y1), (x1, y2)], fill=highlight_rgb, width=1)
            # Bevel shadows (bottom and right)
            draw.line([(x1, y2), (x2, y2)], fill=shadow_rgb, width=1)
            draw.line([(x2, y1), (x2, y2)], fill=shadow_rgb, width=1)
            
            # Surface grain/texture dots
            px = x1 + 4 + (idx * 3) % (max(2, x2 - x1 - 8))
            py = y1 + 3 + (idx * 2) % (max(2, y2 - y1 - 6))
            draw.point((px, py), fill=highlight_rgb)
            draw.point((px + 1, py + 1), fill=shadow_rgb)
            
        return img, draw

    # 1. Standard Dungeon Stone Floor
    stone_img, _ = make_brick_tile(
        base_rgb=(34, 38, 48),
        mortar_rgb=(18, 20, 26),
        highlight_rgb=(48, 54, 68),
        shadow_rgb=(22, 24, 32)
    )
    stone_img.save(os.path.join(OUTPUT_DIR, "tile_floor_stone.png"))
    print("Created tile_floor_stone.png")

    # 2. Start Room (Royal Indigo / Celestial Slate with center rune)
    start_img, draw = make_brick_tile(
        base_rgb=(30, 42, 60),
        mortar_rgb=(16, 22, 34),
        highlight_rgb=(46, 64, 90),
        shadow_rgb=(20, 28, 42)
    )
    # Engraved Runic Circle
    draw.ellipse([20, 20, 44, 44], outline=(70, 110, 160), width=1)
    draw.ellipse([24, 24, 40, 40], outline=(100, 150, 220), width=1)
    draw.polygon([(32, 25), (38, 38), (26, 38)], outline=(110, 170, 240))
    start_img.save(os.path.join(OUTPUT_DIR, "tile_floor_start.png"))
    print("Created tile_floor_start.png")

    # 3. Hazard Room (Volcanic / Ember Stone)
    haz_img, draw = make_brick_tile(
        base_rgb=(46, 26, 28),
        mortar_rgb=(24, 12, 14),
        highlight_rgb=(70, 36, 40),
        shadow_rgb=(28, 14, 16)
    )
    # Magma crack lines
    draw.line([(8, 12), (18, 24), (24, 20), (38, 34), (48, 32), (56, 48)], fill=(240, 70, 30), width=1)
    draw.line([(18, 24), (20, 36), (30, 44)], fill=(255, 140, 40), width=1)
    haz_img.save(os.path.join(OUTPUT_DIR, "tile_floor_hazard.png"))
    print("Created tile_floor_hazard.png")

    # 4. Treasure Room (Ancient Overgrown Moss Stone)
    tre_img, draw = make_brick_tile(
        base_rgb=(30, 44, 36),
        mortar_rgb=(16, 24, 20),
        highlight_rgb=(46, 68, 54),
        shadow_rgb=(18, 28, 22)
    )
    # Emerald moss patches & golden flakes
    draw.ellipse([8, 14, 20, 22], fill=(45, 90, 55, 140))
    draw.ellipse([42, 36, 54, 46], fill=(50, 100, 60, 140))
    draw.point([(14, 18), (48, 40), (28, 52)], fill=(240, 210, 80))
    tre_img.save(os.path.join(OUTPUT_DIR, "tile_floor_treasure.png"))
    print("Created tile_floor_treasure.png")

    # 5. Exit Room (Arcane Obsidian Stone)
    exit_img, draw = make_brick_tile(
        base_rgb=(42, 28, 52),
        mortar_rgb=(22, 14, 28),
        highlight_rgb=(66, 44, 82),
        shadow_rgb=(26, 16, 32)
    )
    # Arcane glow veins
    draw.line([(12, 52), (24, 40), (40, 40), (52, 20)], fill=(170, 70, 230), width=1)
    exit_img.save(os.path.join(OUTPUT_DIR, "tile_floor_exit.png"))
    print("Created tile_floor_exit.png")

def create_wall_textures():
    # 64x32 Top Wall Tile (Front facing with heavy top stone cap)
    img_h = Image.new("RGBA", (64, 32), (18, 20, 26))
    draw_h = ImageDraw.Draw(img_h)
    
    # 1. Top Beveled Stone Coping (y=0 to 8)
    draw_h.rectangle([0, 0, 63, 2], fill=(85, 98, 125)) # Top highlight lip
    draw_h.rectangle([0, 3, 63, 7], fill=(58, 68, 88))  # Coping face
    draw_h.rectangle([0, 8, 63, 9], fill=(22, 26, 34))  # Under-coping shadow
    
    # 2. Wall Blocks (y=10 to 28)
    # Brick 1
    draw_h.rectangle([1, 10, 30, 28], fill=(38, 44, 56))
    draw_h.line([(1, 10), (30, 10)], fill=(52, 60, 78))
    draw_h.line([(1, 10), (1, 28)], fill=(52, 60, 78))
    draw_h.line([(1, 28), (30, 28)], fill=(22, 26, 34))
    draw_h.line([(30, 10), (30, 28)], fill=(22, 26, 34))
    
    # Brick 2
    draw_h.rectangle([33, 10, 62, 28], fill=(42, 48, 62))
    draw_h.line([(33, 10), (62, 10)], fill=(56, 64, 82))
    draw_h.line([(33, 10), (33, 28)], fill=(56, 64, 82))
    draw_h.line([(33, 28), (62, 28)], fill=(22, 26, 34))
    draw_h.line([(62, 10), (62, 28)], fill=(22, 26, 34))
    
    # 3. Base Drop Shadow (y=29 to 31)
    draw_h.rectangle([0, 29, 63, 31], fill=(10, 12, 16))
    
    img_h.save(os.path.join(OUTPUT_DIR, "tile_wall_top.png"))
    print("Created tile_wall_top.png")

def create_hazard_spike_sprite():
    size = (32, 32)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 1. Iron Plate Grate Base
    draw.rectangle([2, 2, 29, 29], fill=(50, 40, 42), outline=(30, 20, 22), width=2)
    draw.line([(3, 3), (28, 3)], fill=(80, 65, 68), width=1) # Top shine
    # Grate slots
    draw.line([(8, 6), (8, 25)], fill=(18, 12, 14), width=2)
    draw.line([(16, 6), (16, 25)], fill=(18, 12, 14), width=2)
    draw.line([(24, 6), (24, 25)], fill=(18, 12, 14), width=2)
    
    # 2. Four Deadly Metal Spikes
    spikes = [(8, 8), (23, 8), (8, 23), (23, 23)]
    for sx, sy in spikes:
        # Base ring
        draw.ellipse([sx - 4, sy - 2, sx + 4, sy + 4], fill=(25, 20, 22))
        # Spike pyramid
        draw.polygon([(sx - 4, sy + 3), (sx + 4, sy + 3), (sx, sy - 7)], fill=(180, 185, 195))
        # Shaded side
        draw.polygon([(sx, sy + 3), (sx + 4, sy + 3), (sx, sy - 7)], fill=(120, 125, 135))
        # Tip gleam
        draw.point((sx, sy - 7), fill=(255, 255, 255))
        # Blood splatter on tip
        draw.line([(sx - 1, sy - 4), (sx + 1, sy - 4)], fill=(180, 25, 30), width=1)
        
    img.save(os.path.join(OUTPUT_DIR, "hazard_spikes.png"))
    print("Created hazard_spikes.png")

def create_pickup_potion_sprite():
    size = (32, 32)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = 16, 17
    # 1. Soft Emerald Glow
    draw.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=(30, 220, 90, 45))
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(40, 240, 110, 75))
    
    # 2. Cork Stopper
    draw.rectangle([cx - 3, cy - 14, cx + 3, cy - 11], fill=(150, 100, 60))
    draw.line([(cx - 4, cy - 14), (cx + 4, cy - 14)], fill=(180, 130, 80))
    
    # 3. Glass Neck
    draw.rectangle([cx - 4, cy - 10, cx + 4, cy - 7], fill=(200, 225, 235, 180), outline=(100, 140, 155), width=1)
    
    # 4. Rounded Flask Body
    draw.ellipse([cx - 9, cy - 6, cx + 9, cy + 10], fill=(15, 60, 30, 220), outline=(120, 170, 180), width=1)
    # Glowing Emerald Elixir
    draw.ellipse([cx - 8, cy - 3, cx + 8, cy + 9], fill=(25, 205, 85, 240))
    draw.ellipse([cx - 6, cy - 1, cx + 6, cy + 8], fill=(60, 245, 120, 255))
    
    # Bubbles inside
    draw.point([(cx - 3, cy + 4), (cx + 3, cy + 2), (cx, cy + 6)], fill=(200, 255, 220))
    
    # Glass Glint / Specular highlight arc
    draw.arc([cx - 7, cy - 4, cx + 4, cy + 5], start=190, end=280, fill=(255, 255, 255), width=2)
    draw.point((cx - 6, cy - 1), fill=(255, 255, 255))
    
    img.save(os.path.join(OUTPUT_DIR, "pickup_potion.png"))
    print("Created pickup_potion.png")

def create_exit_portal_sprite():
    size = (64, 64)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = 32, 32
    # 1. Outer cosmic vortex glow
    draw.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=(130, 40, 190, 70))
    draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(170, 60, 230, 110))
    
    # 2. Outer Runic Ring
    draw.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], outline=(210, 130, 255), width=2)
    # Runic nodes around ring
    for i in range(8):
        ang = i * (math.pi / 4)
        rx = cx + math.cos(ang) * 22
        ry = cy + math.sin(ang) * 22
        draw.ellipse([rx - 2, ry - 2, rx + 2, ry + 2], fill=(255, 220, 255))
        
    # 3. Inner Swirling Vortex
    draw.ellipse([cx - 17, cy - 17, cx + 17, cy + 17], fill=(60, 15, 95))
    draw.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=(100, 30, 150))
    draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=(170, 70, 230))
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(230, 180, 255))
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 255, 255))
    
    # Swirl arms
    for start_ang in [0, math.pi * 0.66, math.pi * 1.33]:
        points = []
        for step in range(12):
            r = 3 + step * 1.4
            a = start_ang + step * 0.45
            points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        for j in range(len(points) - 1):
            draw.line([points[j], points[j+1]], fill=(240, 200, 255, 180), width=2)
            
    img.save(os.path.join(OUTPUT_DIR, "portal_exit.png"))
    print("Created portal_exit.png")

if __name__ == "__main__":
    create_player_sprite()
    create_melee_crawler_sprite()
    create_ranged_pyromancer_sprite()
    create_fireball_projectile()
    create_floor_tiles()
    create_wall_textures()
    create_hazard_spike_sprite()
    create_pickup_potion_sprite()
    create_exit_portal_sprite()
    print("ALL SPRITES GENERATED SUCCESSFULLY!")
