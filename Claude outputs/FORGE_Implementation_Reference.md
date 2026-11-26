# FORGE: implementation reference (what the code actually does)

Scanned 24 Nov 2026. Read only; no code was changed.

**Source scanned:** GitHub `Rayan581/forge`, `main` at commit `e272d46` ("Updated TODO", 21 Nov 2026). The project's local `FYP` folder has the same code; the only differences are Windows line endings and the untracked `ml_spike/judge/data/` folder (the synthetic corpus). Every number below comes from reading the code. I did not run the game or the tests (there is no Godot binary in this environment), so test results are not re-verified here.

File references are relative to the repo root. `gp/` = `godot_prototype/`.

---

## 0. One-paragraph summary

FORGE is a Godot 4.7 top-down dungeon game. Each floor is a grid of rooms built by a **random-walk-with-branching generator (a spanning tree, not BSP)**. Floors 1–5 are fixed **cold-start calibration floors**. When Floor 5 is cleared, a weighted **CR0** profile builds the first observation, and a **PPO policy (8 inputs → 64 → 64 → 8 outputs, tanh hidden layers, output clipped to [-1, 1])** runs in pure GDScript to pick Floor 6. From then on the policy runs once per finished floor. Its 8 outputs are enemy health, damage, speed, aggro, hazard density, resource scarcity, room count and **archetype complexity**, which a softmax turns into a mix over **5 enemy archetypes**. The policy was trained in Python (Stable-Baselines3) against a **simulated player ("sim-v3")**. Every finished floor is logged to **SQLite** (`user://forge_telemetry.db`), with a JSON fallback. A **LightGBM Judge with TreeSHAP** exists **offline in Python only**. The game itself still uses the hand-weighted linear score. A **static +8 %/floor baseline** is built in. **There is no BSP baseline yet.**

---

## 1. Enemies (`gp/scripts/Enemy.gd`, `Room.gd`, `ProjectileFireball.gd`, `SlamShockwave.gd`)

There are five archetypes. The enum order is a contract shared with Python, so it must not be reordered: `MELEE_CRAWLER=0, RANGED_PYROMANCER=1, HEAVY_BRUTE=2, AGILE_SKIRMISHER=3, SWARMER=4`.

### 1.1 Stats

Each enemy's stats = the PPO/base value × its archetype multiplier (`ARCHETYPE_MULTIPLIERS`, `configure_parameters()`). The table shows values at the **Intermediate preset** (base HP 60, damage 20, speed 130, aggro 250).

| Archetype | HP × | Dmg × | Speed × | Aggro × | At Intermediate (HP / dmg / speed / aggro) | Collider r | Art |
|---|---|---|---|---|---|---|---|
| Melee Crawler | 1.0 | 1.0 | 1.0 | 1.0 | 60 / 20 / 130 / 250 | 16 | skeleton (user pack) |
| Ranged Pyromancer | 0.75 | 0.9 | 0.92 | aggro = **max(aggro, 420)** | 45 / 18 / 120 / 420 | 16 | priest (user pack) |
| Heavy Brute | 2.0 | 1.4 | 0.55 | 0.8 | 120 / 28 / 72 / 200 | 22 | CC0 (0x72) |
| Agile Skirmisher | 0.8 | 0.8 | 1.3 | 1.2 | 48 / 16 / 169 / 300 | 16 | CC0 |
| Swarmer | 0.35 | 0.45 | 1.15 | 1.0 | 21 / 9 / 150 / 250, **3 bodies per slot** | 10 | CC0 |

Shared rules:
- If the player is outside aggro range, an enemy wanders at 40–45 % of its speed.
- A hit knocks the enemy back with a 420 px/s impulse that decays at 1400 px/s². The Brute takes only 30 % of it.
- A hit flashes the enemy for 0.14 s.
- On death, the enemy signals at once (so room-clear logic runs), then plays a 0.45 s inert death animation with no collision and no damage.

### 1.2 Behaviour per archetype

- **Melee Crawler** (`_process_crawler_ai`): chases inside aggro range. It strikes within 38 px, with one hit every 0.8 s. Under 34 px it backs off at 75 px/s (anti-stick) while still striking. Each strike knocks itself back 180 px/s.
- **Ranged Pyromancer** (`_process_pyromancer_ai`):
  - **Needs line of sight**: a wall raycast every 0.1 s.
  - Keeps a standoff band of 140–280 px. Closer than 140 px it kites away at 1.15× speed. Farther than 280 px it approaches. Inside the band it strafes at 32 px/s.
  - Casts with a **0.5 s yellow telegraph**. The fireball flies at **240 px/s for 4 s** and deals its full damage on contact. Cast cooldown is 1.6 s.
  - Losing line of sight during a cast aborts it. A hit in the first half of the charge interrupts it (0.35 s cooldown).
- **Heavy Brute** (`_process_brute_ai`, `_do_slam`):
  - Starts a **0.7 s slam wind-up** when the player is within 110 px. The telegraph is a growing red ground circle.
  - During the wind-up it steps in to about 70 px, so a player who stands still gets hit and one who moves away does not.
  - The slam hits within a **90 px radius**. Cooldown is 2.2 s. After the slam it stays planted for 0.35 s and spawns a `SlamShockwave` visual.
- **Agile Skirmisher** (`_process_skirmisher_ai`):
  - **Orbits** the player at 120–160 px and flips direction every 1.5–3 s.
  - When ready, it tightens the orbit. Then it telegraphs for **0.2 s** with a cyan aim line and **lunges** for 0.25 s at 2.5× speed. The lunge hits once within 40 px.
  - It then **retreats** for 0.6 s. Cooldown is 1.4 s.
- **Swarmer** (`_process_swarmer_ai`): one spawn slot = a **pack of 3**. They approach on flank offsets of −40°, 0° and +40°, and the offset fades out as they close in. Each bites within 30 px every 0.7 s, then knocks itself back 140 px/s.

### 1.3 How enemies are spawned (`Room.spawn_entities`)
- Each enemy **slot** in a room samples an archetype from `DifficultyManager.archetype_mix`. A Swarmer slot becomes 3 bodies, and each body counts toward `enemies_alive`.
- **Apex champion:** in the **exit room**, slot 0 becomes a Heavy Brute with **×1.7 HP, ×1.25 damage and ×1.28 scale** whenever `enemy_health >= 85`.
  - The code comment says "Floor 5", but the condition **also fires on any adaptive floor where the PPO sets HP ≥ 85**. The simulator does not model this champion.
- Enemy stats are set from the floor-wide values. There is no per-room scaling.

---

## 2. Player and world mechanics

**Player** (`gp/scripts/Player.gd`):

| Mechanic | Value |
|---|---|
| Max HP | 100 |
| Move speed | 220 px/s |
| Sword | 35 damage, 0.35 s cooldown. The hit lands 0.1 s into the swing as a circle query (r = 58 px) centred 36 px toward the **mouse**. It hits every enemy inside, up to 16. |
| Dodge (Space) | 0.20 s at 2.45× speed, 1.0 s cooldown, i-frames for the dash + 0.06 s. Knockback is ignored while dashing. |
| Taking a hit | 0.6 s invulnerability, 340 px/s knockback |
| Death | Respawn after 1.2 s in the start room with full HP. Cleared rooms stay cleared, and the floor timer keeps running. Deaths are unlimited. |

**World:**
- **Hazards** (`Hazard.gd`) are spike Area2Ds. They do **not block movement**. Each deals **12 damage every 0.75 s** while the player stands on it. Damage is fixed: `hazard_density` only changes how many spikes spawn.
- **Pickups** (`Pickup.gd`) are health flasks that heal **35 HP**. They are only picked up when the player is below max HP.
- **Exit:** the portal in the exit room opens once **that room's** enemies are dead. Other rooms do **not** need clearing.
- **Camera:** a trauma shake on hits, kills, hazards and death.
- **UI:** damage floaters and a minimap (`MiniMap.gd`).
  - `TODO.md` says the map overlay should be hidden because it helps too much. It is still shown.

---

## 3. DifficultyManager (`gp/scripts/DifficultyManager.gd`)

### 3.1 Parameters and ranges (`PARAM_RANGES`, identical in Python `train_ppo_difficulty.py`)
| Param | Range | Note |
|---|---|---|
| enemy_health | 20–120 | |
| enemy_damage | 5–50 | |
| enemy_speed | 60–220 | |
| enemy_aggro | 100–450 | |
| hazard_density | 0.05–0.80 | |
| resource_scarcity | 0.10–0.90 | |
| room_count | **5–9** (rounded) | Calibration floors use 3–5 |
| archetype_complexity c | 0–1, from a7 ∈ [-1, 1] | c = (a7 + 1)/2 |
| enemy_count_scale | 0.7–1.3 on calibration floors only | The comment calls it "PPO-controlled, 0.6–1.6", but **`apply_ppo_action` forces it to 1.0**. The PPO does not control it. |
| ranged_enemy_ratio | derived | = mix[pyromancer]. The policy does not set it directly. |

### 3.2 Observation: 8-D (`build_observation`; identical layout in Python `_get_obs`)
```
[0] norm_time    = clamp(floor_completion_time / 90 s, 0, 1)   # TOTAL floor time, not per room
[1] norm_deaths  = clamp(deaths / 3, 0, 1)
[2] norm_dmg     = clamp(damage_taken / player_max_hp, 0, 1)
[3] norm_enemy_hp, [4] norm_enemy_dmg, [5] norm_hazard, [6] norm_rooms   # current settings, 0-1
[7] norm_level   = clamp(floor_num / 10, 0, 1)                 # saturates at floor 10
```
- The observation is 8-D in **every** version. Only the action went from 7-D to 8-D.
- The policy **does not see** speed, aggro, scarcity or a7, even though it controls them.
- The reward judges pace **per room**, but obs[0] is **total** floor time. The policy has to infer pace from obs[0] together with obs[6].

### 3.3 Action: 8-D (`apply_ppo_action`)
- The order is `[health, damage, speed, aggro, hazard, scarcity, room_count, archetype_complexity]`. Each value is in [-1, 1] and denormalised linearly into the ranges above.
- **A legacy 7-output policy is still accepted.** In that case a7 = 2·(difficulty_score/100) − 1.
- The shipped `gp/ai/policy_weights.json` is 8-output (meta `sim-v3`).

### 3.4 Archetype mix from a7 (`compute_archetype_mix`, same in Python `archetype_mix`)
```
c = (clamp(a7) + 1) / 2,  LEVELS = [crawler 0.00, pyro 0.50, brute 0.90, skirm 0.70, swarm 0.25]
p_i = 0.85 * softmax(-|LEVEL_i - c| / 0.25) + 0.15 / 5
```
So every archetype always keeps at least a 3 % share. Calibration floors set an explicit mix instead (`set_archetype_mix`), and c is then the mix-weighted mean level.

### 3.5 Presets, calibration and static baseline
- **Presets** (Defense Panel only):

  | Preset | HP / dmg / speed / aggro / hazard / scarcity |
  |---|---|
  | Novice | 35 / 10 / 85 / 160 / 0.15 / 0.15 |
  | Intermediate | 60 / 20 / 130 / 250 / 0.35 / 0.40 |
  | Expert | 95 / 35 / 185 / 380 / 0.65 / 0.75 |

  Presets set a7 from the difficulty score.
- **Static baseline** (`static_baseline_mode`):
  - Intermediate preset, with **HP and damage × (1 + 0.08·(floor−1))**.
  - a7 fixed at −0.1 (c = 0.45), 6 rooms, count scale 1.0.
  - **No calibration floors and no PPO.**
- **Difficulty score** (`calculate_difficulty_score`): a fixed linear 0–100 score with weights damage 0.28, HP 0.22, speed 0.18, aggro 0.14, hazard 0.10, scarcity 0.08.
  - Archetype complexity is **deliberately excluded**.
  - The "drivers %" shown in the Defense Panel are each term's share of this score. They are **not SHAP**.

---

## 4. Cold start (Floors 1–5) and the hand-off to PPO

**Calibration floors** (`CALIBRATION_LEVELS`). Mix order: crawler / pyro / brute / skirm / swarm.

| Floor | Rooms | HP | Dmg | Speed | Aggro | Hazard | Scarcity | Count × | Mix C/P/B/S/W |
|---|---|---|---|---|---|---|---|---|---|
| 1 Novice Initiation | 3 | 35 | 10 | 85 | 160 | 0.05 | 0.15 | 0.7 | .70/0/0/0/.30 |
| 2 Swarm Reflex | 4 | 45 | 14 | 110 | 200 | 0.15 | 0.25 | 0.9 | .50/0/0/0/.50 |
| 3 Ranged Evasion & Traps | 4 | 55 | 18 | 135 | 240 | 0.38 | 0.35 | 1.0 | 0/.75/0/.25/0 |
| 4 Tactical Crucible | 5 | 70 | 24 | 155 | 290 | 0.50 | 0.55 | 1.15 | .25/.25/0/.30/.20 |
| 5 Apex Gauntlet | 5 | 90 | 30 | 175 | 350 | 0.65 | 0.70 | 1.3 | .15/.25/.30/.20/.10 (+ apex Brute, since HP ≥ 85) |

**CR0** (`TelemetryLogger.compute_cr0_baseline`):
- Floors are weighted **1.0 / 1.5 / 2.0 / 2.5 / 3.0**.
- Human-readable score: **CR0 = 40·survival + 35·damage defence + 25·pace**, clamped to 10–95.
  - Survival = 1 − 0.5·deaths.
  - Damage defence = 1 − damage/120.
  - Pace = 1 − (s/room − 5)/12.
  - Tiers: < 40 Novice, < 70 Intermediate, otherwise Expert.
- **CR0 is not a policy input.** The Floor-6 observation uses weighted averages of `obs_time = s/room·6/90`, `obs_deaths = deaths/3` and `obs_dmg = damage/max_hp`.

**Sequence in `Main._on_dungeon_escaped`:**
1. Record the floor.
2. Ask for the 1–5 rating (only if the player consented).
3. If the floor was a calibration floor, store its record.
4. After Floor 5: compute CR0, show the "PPO activated" banner, and **predict Floor 6 from the CR0 observation**.
5. From Floor 6 on (`next_level >= 7`): **one PPO step per finished floor**.

**Mismatch with training:**
- The simulator's cold start (`DungeonDifficultyEnv._calibrate`) uses an **unweighted** mean of the **raw total** times of the 3–5-room calibration floors, and a **rounded** mean of deaths.
- The game uses **weighted** averages and **rescales time to a 6-room floor**.
- So the Floor-6 observation in the game is distributed slightly differently from what the policy saw in training. This is minor, but it is a real difference.

---

## 5. DungeonGenerator (`gp/scripts/DungeonGenerator.gd`)

The algorithm is a **random walk with branching on a grid**. It is **not BSP, cellular automata or WFC**.

1. **Layout** (`_random_layout`):
   - Start at (0,0).
   - Each step picks a parent room: 50 % the newest room (which grows long chains), otherwise a random room from the queue.
   - It attaches a new room on a free side, with a matching door pair.
   - Doors are only opened between parent and child, so the room graph is a **spanning tree** and is connected by construction.
   - It makes up to 24 attempts. It keeps the layout whose deepest BFS room has `max_depth*2 + 1 if not in line with the start` as its score, and accepts early once depth ≥ ceil(rooms/2).
   - If every attempt fails, it falls back to a straight chain.
2. **Exit room**: a room at the **maximum BFS door depth**. Ties go to one not in line with the start, then to the one farthest on the grid.
   - `README_TECHNICAL_DETAIL.md` and report Ch5 still say "Manhattan-farthest". That is outdated.
3. **Room roles and contents** (driven by the parameters):
   - **Hazard rooms**: count = clamp(int(hazard·n), 1, n), where n = the rooms other than start and exit. Each has clamp(int(hazard·10), 3, 10) spikes and 1–3 enemy slots.
   - **Treasure rooms**: count = clamp(int((1−scarcity)·2.5), 1, 3). Each has 2–4 flasks and 1–2 enemy slots.
   - **Combat rooms**: 2–5 enemy slots, clamp(int(hazard·4), 0, 4) spikes, and 1 flask with probability (1 − scarcity).
   - **Exit room**: clamp(int(3 + 3·hazard), 3, 6) slots and clamp(int(6·hazard), 1, 6) spikes.
   - Enemy slot counts are multiplied by `enemy_count_scale`, with a minimum of 1.
   - Rooms are not tinted by role any more.
4. **Sizes** (`_assign_sizes`):
   - Widths come from {608 … 1120} and heights from {416 … 672}, in 64 px steps.
   - The exit room is biased larger, combat rooms slightly wider, and treasure/start rooms smaller.
   - Floors with 8 or more rooms drop the largest size step.
5. **World layout** (`_layout_world`):
   - A column/row table: each column is as wide as its widest room and each row as tall as its tallest, plus 160 px spacing.
   - Doors therefore line up on straight corridors. Each door's corridor length is stored.
   - The 96 px doors snap to the 32 px tile grid.

**Two-stage claim:**
- Stage 1 is the layout. Stage 2 fills the rooms, and the PPO parameters drive it.
- Hazard and pickup positions are random within a margin of 70–80 px from the walls. There is **no check that the paths inside a room are walkable**. Spikes never block movement, though, so this only costs HP.

---

## 6. PPO policy at run time (`gp/scripts/PPOPolicy.gd`)

**Network:**
- Loads `res://ai/policy_weights.json`: layers `w[out][in]` and `b`.
- Architecture: **8 → 64 → 64 → 8**, tanh on the hidden layers, final layer = the Gaussian mean **clipped** to [-1, 1]. This matches SB3's `predict(deterministic=True)`.
- A shape check rejects files whose input width is not 8.

**Fallback:** if the file is missing or bad, `_fallback_heuristic` takes over.
- Performance signal = (0.5 − time)·1.4 − deaths·1.5 − dmg·0.8.
- It moves HP, damage, hazard and rooms by at most ±0.12 per floor, and sets speed, aggro and scarcity from the signal.
- **a7 = −0.1 + 0.9·signal**, so the fallback heuristic is **8-D**.

**Weight files in `gp/ai/`:**

| File | Outputs | Note |
|---|---|---|
| `policy_weights.json` | 8 | **Shipped.** sim-v3, 113 KB |
| `policy_weights_v2.json` | 8 | sim-v2 |
| `policy_weights_2.json`, `_working.json`, `_v1_7dim.json` | 7 | Legacy |

`jh.py` (sensitivity sweep) is stale:
- It applies a final **tanh**, while the game clips.
- It names only 7 outputs.

**Latency:**
- `tests/benchmark_inference.gd` fails if the **median exceeds 1.0 ms** (it calls this NFR-06).
- It is **not in the CI list**, so no CI run produces a latency number.

The documents disagree on the number:

| Source | Claimed latency |
|---|---|
| `README.md` | "~0.21 ms mean, 0.36 ms max", labelled NFR-02 |
| `CHANGES.md` CR-01 | "< 0.5 ms" |
| `MID_EVAL_IMPLEMENTATION_PLAN.md` | "< 0.05 ms" |
| Python `test_performance.py` | `test_python_inference_under_05ms` (a Python forward pass, not GDScript) |

Pick one measured number, run on one machine, and cite it everywhere.

**Policy size:**
- CR-01 says the JSON is "< 50 KB". It is actually **113 KB**.
- CI allows up to 120 KB.

---

## 7. Training (`ml_spike/train_ppo_difficulty.py`, `ml_spike/analysis/`)

**Environment** (`DungeonDifficultyEnv`, Gymnasium; custom, no gym-pcgrl):
- One episode = **30 adaptive floors**, starting from the Floor-5 settings, after a simulated 5-floor cold start.
- Observation and action spaces are the same 8-D/8-D as in the game.

**Simulated player:**
- Skill starts at U(0.05, 0.95).
- **Reflex** = skill + b and **tactics** = skill − b, with b ~ U(−0.12, 0.12).
- Gradual drift of N(0.004, 0.007) per floor.
- A 5 % chance per floor of an abrupt ±0.15–0.30 shift. Half of those revert 3–6 floors later.

**Physics** (`_room_layout` → `_physics` → `_simulate`):
- `_room_layout` mirrors the generator's room roles and counts.
- Reflex and tactics loads → a hit probability through a sigmoid.
- Per-room time = traverse + (kill + evade + stagger)·caution + hazard time.
- Damage = an exposure model minus usable healing.
- deaths = floor(net damage).
- Lognormal noise on time and damage.

**Reward** (`reward_fn`):
```
1 − min(2, |t_room − 7.5|/7.5)        # pace per room (target 45 s / 6 rooms)
− 0.5·deaths;  − 0.3 if 0 deaths and pace < 0.5·target;  − 0.4 if deaths ≥ 2
− 0.45·|dmg_ratio − 0.35|             # flow
− 0.30·|rooms − (5 + 4·skill)|/4      # room count vs HIDDEN skill
− 0.20·|c − skill|                    # archetype complexity vs HIDDEN skill
− 0.40·|sev − (0.10 + 0.25·reflex)|/0.30          # hit-severity prior (hidden reflex)
− 0.80·|ln(cover / (1.4 + 2.2·(1 − tactics)))|    # healing-cover prior (hidden tactics)
− 0.15·mean(a²)                       # balance prior
− 0.25·mean|a_t − a_{t−1}|            # smoothness
(training only) − 1.5·Σ max(0, |a| − 1)²   # TrainWrapper, action box widened to [-4, 4]
```
- Several reward terms use the **hidden** skill, reflex and tactics, which the policy never observes.
- So part of the personalisation is imposed by design. `results_sim_v3.md` says so.

**Hyper-parameters** (`make_model`):
- MlpPolicy [64, 64] with tanh.
- n_steps 512 × 8 envs, batch 512, 10 epochs.
- Learning rate 3e-4, decaying linearly to 3e-5.
- γ = 0.9, λ = 0.9, ent_coef 0, CPU.

**What was shipped:**
- 3 seeds × **1,000,000 steps** (`train_with_logging.py`). The CLI default in `train_ppo_difficulty.py` is 600k.
- `export_best.py` picks the best seed on a separate validation set (seeds 50000+).

**Simulated results** (`results_sim_v3.md`):
- On 6 skill profiles, the shipped policy beats random-init, the heuristic and static +8 % on both reward and pacing.
- Pacing error is about 0.12–0.13, with 0 deaths per floor.
- Mean |Δaction| is 0.048–0.065.
- After an abrupt −0.30 skill drop, it recovers in **2 floors**.
- Spearman(skill, chosen difficulty) = 1.0. This is partly built in by the reward (see above).

**Known sim ↔ game gaps found in this scan:**
- Healing: a pickup is 0.18 of max HP in the simulator, but **35 HP** in the game.
- The apex champion is not simulated.
- Hazard damage is modelled per tile, while the game deals 12 per 0.75 s tick while standing on a spike.
- The cold-start observation differs (see §4).
- The Python "heuristic" baseline in `evaluate_policies.py` is a **7-D port with legacy a7**. The game's fallback is 8-D, so the simulated "heuristic" row is not quite the in-game heuristic.

---

## 8. Telemetry (`gp/scripts/TelemetryLogger.gd`, `gp/telemetry/*`, `ml_spike/telemetry_data/`)

**Backends:**
- `SqliteBackend` (godot-sqlite addon) writes to `user://forge_telemetry.db`.
- If the addon is missing, `JsonBackend` writes to `user://session_telemetry.json`.
- Both share the `TelemetryBackend` interface.
- A legacy JSON history is imported into SQLite once.
- SQL lives in `schema.sql` (with migrations) and `queries.sql` (named statements).

**Schema** (v2):
- `schema_version` and `meta`.
- `sessions`: `id`, `install_id` (a persistent random ID), `mode ∈ {adaptive, static, unknown}`, `policy_version`, `game_version`, `consent`, and totals.
- `floors`: one row per floor, unique on (session, floor). It holds:
  - `phase ∈ {calibration, adaptive, static}`
  - the outcomes
  - all 8 settings + 5 mix shares + count scale
  - `difficulty_score`
  - `obs_0..7` and `action_0..7`
  - `frame_avg_ms`, `frame_p95_ms`, `frame_max_ms`
  - `perceived_difficulty`
  - `manual_override`
- `kills_by_archetype`.
- The `v_corpus` view is what the Judge reads.
- **There is no `bsp` value** in `mode` or `phase` yet. The BSP baseline needs a schema v3.

**What is logged:**
- Every floor is logged **whether or not the player consented**. Consent only sets `sessions.consent`, and the exports can filter on it (`--consented-only`).
- Floors where the Defense Panel changed settings get `manual_override = 1` and are left out of the Judge corpus.
- The comment in the code says "zero PII". In practice the data is pseudonymous (`install_id`), and testers send the `.db` file to the team (`PLAYTEST.md`).

**Python side:** `telemetry_db.py`
- `TelemetryDatabase.sync_from_game_db()` merges a game DB.
- `get_judge_training_data()` returns the data the Judge trains on.
- `JUDGE_FEATURES` has 14 entries.
- `analysis/export_telemetry.py` exports the corpus to CSV.

---

## 9. Playtest study features

- **Consent** (`ui/ConsentScreen.gd`, `GameSettings.gd` → `user://forge_settings.cfg`):
  - Shown once at startup, until it is answered.
  - Can be changed later in Main Menu → "Data & Privacy".
  - The 18 Nov supervisor note asked for consent **after the Play button**. The code shows it **at launch**, before the menu.
- **Floor rating** (`ui/FloorRating.gd`):
  - Asks "How hard did that floor feel?" on a 1–5 scale. The game pauses, keys 1–5 answer, Esc skips.
  - Only shown when the player consented and `rate_floors` is on.
- **Pause menu** (`ui/PauseMenu.gd`).
- **Build flavour** (`BuildInfo.gd`):
  - The "Windows Desktop" export preset has the custom feature `playtest`, as does running with `-- --playtest`.
  - Playtest builds hide the Defense Panel and the difficulty badge.
  - The version string is `0.9.0-playtest` or `0.9.0-dev`.

---

## 10. Defense Overlay (`gp/scripts/DefenseOverlay.gd`; dev builds only)

**Sliders:** HP, damage, speed, aggro, hazard % and scarcity %.
- There is **no slider for room count or archetype complexity**.
- Changing a slider flags the floor `manual_override`.
- `sync_ui_with_manager()` uses `set_value_no_signal` (the fix for the "only HP adapts" bug, guarded by `test_overlay_sync`).

**Buttons:**
- Novice, Intermediate and Expert presets. These flag override and rebuild the floor.
- **Regenerate floor**: same-floor rebuild, and telemetry keeps counting.
- **Auto-kill** toggle.
- **Static +8 % baseline** toggle.

**Display:**
- Difficulty score/100 with its tier label, and the top 4 "drivers" (linear-score shares).
- Next-dungeon room count and count scale.
- Floor/room label with mode tag `[CALIBRATION n/5]`, `[ADAPTIVE PPO]` or `[STATIC +8%/floor]`, plus the live mix C/P/B/S/W %.
- Live telemetry summary and the minimap.

**There is no SHAP panel in the game.**

---

## 11. Judge model and SHAP (`ml_spike/judge/`; offline only)

**Target** (`common.py`):
- If a rating exists: `(rating−1)/4`.
- Otherwise (all synthetic rows), **measured** = 0.40·min(dmg/max_hp, 1) + 0.35·min(deaths, 3)/3 + 0.25·min((time/rooms)/15 s, 1).

**Features (18):**
- The 14 `JUDGE_FEATURES`.
- 4 from the previous floor: `prev_time_per_room`, `prev_deaths`, `prev_damage_frac`, `prev_difficulty_score`.
- On the first floor these four are NaN.

**Data:** `make_synthetic_corpus.py` generates **30,199 synthetic floors** (3,000 simulated players, seed 0) with sim-v3. It uses the `v_corpus` column names plus `source = synthetic`.

**Training:** `train_judge.py`
- LightGBM 4.7.0, split by player: 5-fold grouped CV plus a held-out set of 600 players.
- Saves `judge_model.txt` and `judge_model.json`.

**Results on synthetic test data:**

| Model | MAE |
|---|---|
| LightGBM Judge | **0.052** (R² 0.82) |
| Linear regression, same features | 0.069 |
| Rescaled linear proxy | 0.104 |
| Raw proxy | 0.206 |
| Mean predictor | 0.146 |

**Results on real data** (29 floors, 1 player, 3 sessions): the Judge **loses** to the proxy.

| Against | Judge MAE | Proxy MAE |
|---|---|---|
| Measured difficulty | 0.121 | 0.109 |
| The player's ratings | 0.311 | 0.162 |

**SHAP:** `explain.py` uses `shap.TreeExplainer` (shap 0.54.1).
- Global beeswarm and bar charts.
- A per-floor "Design Insight Report" CLI: `python -m ml_spike.judge.explain --db … --session …`.

**Not built:**
- No GDScript port.
- No in-game explanation.
- The PPO still trains on the simulator reward, not on the Judge.

---

## 12. Baselines that exist today

| Baseline | Where | Status |
|---|---|---|
| Static +8 %/floor | `DifficultyManager.apply_static_baseline` (game); `step_static` (sim) | Built and tested (`test_static_baseline`). Weak: novices die about 0.7 times per floor. |
| Fallback heuristic | `PPOPolicy._fallback_heuristic` (game, 8-D); `evaluate_policies.heuristic_action` (sim, 7-D) | Built. The two versions differ (§7). |
| Random-init PPO | `evaluate_policies.py` (10 untrained nets) | Simulation only |
| Linear difficulty proxy vs the Judge | `judge/train_judge.py` | Offline |
| **BSP generator** | none | **Not implemented.** No BSP code exists, and there is no layout-diversity script. |

---

## 13. CI and tests (`.github/workflows/ci.yml`, `release.yml`)

**CI jobs:**

| Job | What it does |
|---|---|
| `python-lint` | ruff 0.4.10: check + format on `ml_spike/` |
| `python-tests` | pytest on `ml_spike/tests/` with coverage, CPU torch |
| `policy-validation` | Checks the policy JSON schema, the < 120 KB size limit, and Python inference parity |
| `godot-headless` | See below |
| `ci-gate` | Requires all four jobs above to pass |

The `godot-headless` job, step by step:
1. Godot **4.7.2-stable**, checked by SHA.
2. Downloads godot-sqlite v4.9.
3. Imports the project and load-checks every `.gd`, `.tscn` and `.tres`.
4. **Solvability harness** (`ci_solvability_runner.gd`): 500 seeds × room counts 3–9 = 3,500 layouts. Checks:
   - BFS reachability
   - the requested room count
   - no overlapping rooms or corridors
   - exit at maximum depth and ≥ 2
   - room sizes within bounds
   - at least 6 distinct sizes per 100 rooms
5. **11 GDScript tests**: `test_damage_telemetry`, `test_cold_start`, `test_static_baseline`, `test_telemetry_fallback`, `test_archetype_mix`, `test_enemy_archetypes`, `test_swarm_room`, `test_animations`, `test_overlay_sync`, `test_telemetry_logger`, `test_playtest_flow`.
6. `test_telemetry_sqlite` against the real extension. It fails if the extension skips.
7. A parse check, a check that the required scenes exist, and a PCK export smoke test of the "Windows Desktop" (playtest) preset.

**Files in `gp/tests/` that CI does not run:**
- `benchmark_inference.gd` (so CI produces no latency number)
- `render_ingame.gd` (needs a display)
- `telemetry_scenario.gd` (a shared helper)

**Python tests:**
- 137 `def test_` functions across 11 files. Parametrisation raises the collected count (the earlier review counted 145).
- Files: env validation, inference parity, Judge, performance, policy validation, PPO smoke, SB3 parity, sim-v2, sim-v3, SQLite telemetry, telemetry schema.

**`release.yml`** still pins **Godot 4.3-stable**, while CI uses 4.7.2. The project file says 4.7, and `benchmark_inference.gd`'s header says "Godot 4.3". This is the version inconsistency from the report review (C1), and it is in the workflows too.

---

## 14. Docs vs code: disagreements to fix

| # | Topic | What the docs say | What the code does |
|---|---|---|---|
| 1 | Action space | Report: 7-D throughout | **8-D** (+ archetype_complexity). 7-D files are still accepted. |
| 2 | Observation | Sometimes described as a "player profile" or "EMA vector" (TODO, proposal Gate 3) | A plain **8-D last-floor observation**: total time/90, deaths/3, damage/HP, HP, damage, hazard, rooms, floor/10. No EMA, and no speed, aggro, scarcity or a7 inputs. |
| 3 | Enemy list | Report: 2 archetypes (crawler, pyromancer) | **5 archetypes** (§1). The Swarmer spawns 3 bodies per slot. An apex Brute appears whenever HP ≥ 85, not only on Floor 5. |
| 4 | Topology method | Report Ch5 and README_TECHNICAL_DETAIL: exit = **Manhattan-farthest**, fixed room size. Report Ch10: BSP planned for Final-1. | Random-walk spanning tree, exit = **maximum BFS depth**, per-room sizes and corridors. **No BSP.** |
| 5 | Reward-hacking story | `CHANGES.md` CR-03: the policy "collapsed room counts to N = 4", rooms now "[4, 12]". `README.md`: it **inflated** room_count. Report: "pinned at an extreme". | These three accounts contradict each other. The PPO room range is **5–9**, so N = 4 is impossible under the current ranges. The current reward judges pace per room and ties rooms to hidden skill (5 + 4·skill). Pick one true account; the git history of `train_ppo_difficulty.py` is the evidence. |
| 6 | Inference latency | 0.21 ms (README), < 0.5 ms (CHANGES), < 0.05 ms (mid plan) | One benchmark script with a 1 ms limit, not run in CI (§6) |
| 7 | Policy size | CR-01: < 50 KB | 113 KB (CI limit 120 KB) |
| 8 | NFR numbering | README: latency = **NFR-02** | `benchmark_inference.gd` calls it **NFR-06** |
| 9 | Telemetry | Report: flat JSON | SQLite with schema v2, JSON only as a fallback |
| 10 | Privacy | "No personal identifiers"; "zero PII" comment | A persistent `install_id`, and every session is logged regardless of consent (flagged, filterable) |
| 11 | enemy_count_scale | Comment: "PPO-controlled 0.6–1.6" | Only set on calibration floors. PPO floors force 1.0. |
| 12 | Judge | Report: planned, 25-player corpus, live TreeSHAP in Godot | Built offline on **synthetic** data. It beats the proxy on synthetic data, **loses on 29 real floors**, and has no in-game version. |
| 13 | Training budget | Report: 300k steps; script default 600k | The shipped policy is 3 seeds × 1M steps (sim-v3) |
| 14 | Sensitivity script `jh.py` | README: "run jh.py to verify no reward hacking" | Stale: it applies a final tanh (the game clips) and lists 7 outputs |
| 15 | Consent timing | Supervisor 18 Nov: show consent after Play | Shown at first launch, before the menu |
| 16 | Godot version | 4.3 (declaration, release.yml, benchmark header) vs 4.7.2 (CI, report) | Project feature tag is "4.7"; CI is 4.7.2 |
| 17 | Sim vs game | Docs say they "must match exactly" | They match on ranges, obs/action and the mix. They differ on heal size, apex champion, hazard damage model and cold-start averaging (§4, §7). |
| 18 | Minimap | TODO: hide the map overlay | Still shown |

---

## 15. Where to look (quick index)

| Question | File:function |
|---|---|
| Enemy AI / stats | `gp/scripts/Enemy.gd` (`ARCHETYPE_MULTIPLIERS`, `_process_*_ai`) |
| Spawning, apex champion, swarm packs | `gp/scripts/Room.gd:spawn_entities` |
| Floor flow, cold start → PPO | `gp/scripts/Main.gd:build_new_dungeon`, `_on_dungeon_escaped` |
| Parameters, obs/action, mix, presets, static | `gp/scripts/DifficultyManager.gd` |
| CR0 and floor rows | `gp/scripts/TelemetryLogger.gd:compute_cr0_baseline`, `record_floor` |
| Layout generator | `gp/scripts/DungeonGenerator.gd:generate_dungeon` |
| Run-time policy + heuristic | `gp/scripts/PPOPolicy.gd` |
| Simulator, reward, training | `ml_spike/train_ppo_difficulty.py` |
| Evaluation vs baselines | `ml_spike/analysis/evaluate_policies.py`, `results_sim_v3.md` |
| Judge + SHAP | `ml_spike/judge/common.py`, `train_judge.py`, `explain.py`, `results_judge.md` |
| DB schema | `gp/telemetry/schema.sql`, `queries.sql` |
| CI | `.github/workflows/ci.yml` |
