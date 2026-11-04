# Character / item sprite sources

User-supplied asset packs (licence as supplied with the downloaded packs; not re-checked here):

| Used for | Source file(s) |
|---|---|
| Player (animated: idle, move, attack, hurt, death) | `Enemy_Animations_Set/enemies-skeleton1_{idle,movement,attack,take_damage,death}.png` -> `player/` |
| Crawler | `2D Pixel Dungeon Asset Pack/Character_animation/monsters_idle/skeleton1/v1` -> `crawler/` (red corner guide pixels removed) |
| Pyromancer | `.../priests_idle/priest2/v1` -> `pyromancer/` |
| Health pickup | `.../items and trap_animation/flasks/flasks_1_*` -> `items/` |
| Spike hazard | `.../items and trap_animation/peaks/peaks_*` -> `hazards/` |

Brute / skirmisher / swarmer art is documented in `enemies/CREDITS.md` (0x72, CC0).
`tools/build_sprite_frames.py` regenerates the strips and `*_frames.tres` from the source packs.
