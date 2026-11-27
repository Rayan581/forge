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
- [x] Migrate `TelemetryLogger.gd` from JSON to embedded SQLite
- [x] Implement remaining 4 enemy archetypes and activate 8th action dimension (`archetype_complexity`)
- [x] Enemy types
- [x] sqlite migration
- [x] - No need to set all the tiles of a room with an item with the corresponding matching tile, i.e., healing type tile with a healing item. Currently if there is an item (let's say healing item) in a room, all the tiles in that room are healing type tiles. We don't need to set the tiles for each that specific item. Similarly with the finish portal room, all the tiles are purple, no need to do that. 
- [x] The finish room shouldn't be placed closer to the starting room.
- [x] The sizes of the rooms should be dynamic, not static so that there is more diversity in the map generation.
- [x] I have downloaded assets for the game. See the assets and use the appropriate for everything including the characters, rooms, tiles, walls, items, etc. The character sprite have animations, so make sure to incorporate them. I want to use enemy-skeleton1 sprites from the Enemy_Animations_Set/ for the main character. Use one of the skeletons from the 2D Pixel Dungeon Asset Pack/Character_animation/monsters_idle for the crawlers and maybe priests for the pyromancer.
- [x] For the enemy types that you'll be adding now, search and download appropriate pixel art sprites for them from the internet. 

## Upcoming Implementation Milestones (Gate 2 & 3)
- [ ] Calculating difficulty and skill level

## To implement for final FYP 1
- [ ] Fix the simulator and retrain PPO

# Supervisor Meeting
- 18/11/2026 - Show a consent screen after the user clicks on the Play button. If the user wants to record this session, show the level difficulty screen only then. 
- 25/11/2026 - Train the judge and improved ppo model and show on Friday.

# Off the Head
- Show controls while playing the game on the level like tutorial controls. 
- Have doors between some rooms and the key should be in one of the rooms in chest. That chest can also contain credits once we implement the credits and items system. 
- Don't show the map overlay, as it helps the player a little too much. 
- The difficulty isn't very well tuned and trained. 
- Sometimes the enemies from the final room may wander and go outside the room. As it is necessary to kill all the enemies in the final room to open the finish portal, it might be hectic and confusing. 
- Even though the apex has high health and damage, it is very easy to beat him. Just dodge his attacks and attack him afterwards.

# ChatGPT's suggestions
- Improve the gameplay first
    - Better melee combat
        - Directional attack animations.
        - Hit-stop on successful hits.
        - Impact particles.
        - Knockback and enemy hit reactions.
    - Better dodge mechanics
        - Visible dodge trail.
        - Clear invincibility feedback.
        - Enemy attacks that can be dodged.
        - More deliberate cooldown and timing.
    - Combat feedback
        - Damage flashes.
        - Screen shake.
        - Floating damage numbers.
        - Death animations and sound effects.
    - Enemy attack patterns
        - Telegraph before attacks.
        - Different attack ranges.
        - Recovery windows.
        - More distinct archetype behaviors.
- Make enemy composition depend on dungeon difficulty and room type, not just enemy count.
- Your random-walk generator creates connected rooms, but connectivity alone doesn't guarantee interesting level design. I'd add a room-generation system with reusable templates.
    - Room types I'd introduce:
        - Combat arena: waves of enemies, limited escape routes.
        - Treasure room: rewards, optional risk.
        - Trap room: environmental hazards and movement challenges.
        - Elite room: stronger enemies with better rewards.
        - Rest room: healing or resource recovery.
        - Challenge room: optional encounter with a special condition.
- Guarantee a minimum path length.
- Introduce optional branches.
- Add loops so the dungeon isn't always a simple branching tree.
- Control how frequently special rooms appear.
- Make room placement respect difficulty and pacing.
- Currently, your documented observations include completion time, deaths, damage taken, enemy stats, hazard density, room count and floor depth. Consider adding:
    - New metric	What it reveals
    - Dodge success rate	Whether the player understands enemy attacks
    - Attack accuracy	Whether the player is landing attacks
    - Damage dealt per minute	Combat effectiveness
    - Health remaining at floor end	How much pressure the player experienced
    - Healing utilization	Whether resource scarcity is appropriate
    - Damage avoided	Defensive skill
    - Exploration percentage	Whether the player explores optional areas
- Research caution: distinguish a player's mechanical skill from their playstyle. A player who takes their time exploring shouldn't automatically be classified as less skilled.

- Give FORGE a proper visual identity
Your assets are already pixel-art oriented, so I'd lean into that rather than introducing realistic 3D assets or a completely different art direction.
Specific improvements:
    Environment
        - Multiple wall and floor variants.
        - Decorative props like barrels, bones, chains and torches.
        - Animated environmental objects.
        - More deliberate room-specific color palettes.
    Lighting and atmosphere
        - Animated torch lights.
        - Subtle ambient lighting.
        - Glowing portals.
        - Particles around magical objects.
        - Darker corners and environmental shadows.
    Animations
        - Idle, walking and attack animations for all enemies.
        - Enemy hit and death animations.
        - Chest-opening animations.
        - Portal activation animations.
    Audio
        - Different sounds for each weapon and enemy.
        - Footsteps.
        - Ambient dungeon sounds.
        - Room-clear feedback.
        - Floor transition effects.
- Improve the UI and player experience

## FORGE improvement roadmap
1. Phase 1: Combat polish
   - Hit-stop, knockback and screen shake.
   - Enemy attack telegraphs.
   - Better attack and dodge animations.
   - Sound effects and combat feedback.
   Start here
2. Phase 2: Dungeon variety
   - Room templates and modifiers.
   - Branching paths and loops.
   - Better room placement.
   - More interesting enemy compositions.
3. Phase 3: Progression
   - Credits and inventory.
   - Chests, keys and locked doors.
   - Equipment and upgrades.
   - Meaningful rewards for optional rooms.
4. Phase 4: Visual and audio polish
   - Consistent lighting and color palettes.
   - Environmental animations.
   - Better menus and HUD.
   - Music and ambient audio.
5. Phase 5: RL improvements
   - Additional telemetry metrics.
   - Player skill and playstyle profiling.
   - Smoother difficulty transitions.
   - More rigorous policy evaluation.
6. Phase 6: Research-ready release
   - Consent and recording workflow.
   - Playtesting with actual participants.
   - PPO vs baseline comparisons.
   - Final performance and usability testing.

# Useful github repos
- https://github.com/bgrenat/godot-game-dev-studio.git
- https://github.com/Coding-Solo/godot-mcp.git
- https://github.com/setcodes/gamedev-skills.git
- https://github.com/grndctrl/godot-skills.git