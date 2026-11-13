# FORGE Project — Action Items & Status

## Completed Items
- [x] Replace all placeholders in `FORGE_Proposal.md` (team members, supervisor, date, WBS assignments)
- [x] Harmonize reward function in §5.5.2 with `train_ppo_difficulty.py` code
- [x] Align action space dimensions (Gate 1: 7-dim POC vs Gate 3: 8-dim committed deliverable)
- [x] Remove `gym-pcgrl` fork references across document and classify custom `DungeonDifficultyEnv`
- [x] Remove FastAPI / REST microservice references and reflect embedded GDScript neural runtime
- [x] Reframe player profile narrative (rolling observation deltas at Gate 1, EMA profile vector at Gate 3)
- [x] Add honest framing for SHAP feature attribution (Gate 1 weighted linear proxy vs Gate 4 regressor SHAP)
- [x] Correct telemetry format (§5.7 JSON prototype, SQLite at Gate 3)
- [x] Add exploration percentage metric to telemetry specifications
- [x] Add formal functional requirements (FR-01 to FR-07 in §4.3.2)
- [x] Add measurable non-functional requirements (NFR-01 to NFR-06 in §4.3.3 and §5.6)
- [x] Add AI-resilience diagnostic and Prior FYP structural overlap audit in §4.1
- [x] Standardize UAT protocol to 10 participants, single-blind counterbalanced within-subjects design
- [x] Fix gate numbering in §6.1 and Gantt schedule
- [x] Cite Reference [9] in §2.1
- [x] Add Professional, Societal & Ethical Compliance section (§8.4)
- [x] Create `CHANGES.md` change control register
- [x] Add fixed set of 3–5 placement calibration maps in Godot prototype (`godot_prototype/`)

## Upcoming Implementation Milestones (Gate 2 & 3)
- [ ] Migrate `TelemetryLogger.gd` from JSON to embedded SQLite
- [ ] Implement remaining 4 enemy archetypes and activate 8th action dimension (`archetype_complexity`)
- [ ] Calculating difficulty and skill level

## To implement for final FYP 1
- [ ] Enemy types
- [ ] sqlite migration
- [ ] - No need to set all the tiles of a room with an item with the corresponding matching tile, i.e., healing type tile with a healing item. Currently if there is an item (let's say healing item) in a room, all the tiles in that room are healing type tiles. We don't need to set the tiles for each that specific item. Similarly with the finish portal room, all the tiles are purple, no need to do that. 
- [ ] The finish room shouldn't be placed closer to the starting room.
- [ ] The sizes of the rooms should be dynamic, not static so that there is more diversity in the map generation.
- [ ] I have downloaded assets for the game. See the assets and use the appropriate for everything including the characters, rooms, tiles, walls, items, etc. The character sprite have animations, so make sure to incorporate them. I want to use enemy-skeleton1 sprites from the Enemy_Animations_Set/ for the main character. Use one of the skeletons from the 2D Pixel Dungeon Asset Pack/Character_animation/monsters_idle for the crawlers and maybe priests for the pyromancer.
- [ ] For the enemy types that you'll be adding now, search and download appropriate pixel art sprites for them from the internet. 
- [ ] Fix the simulator and retrain PPO
