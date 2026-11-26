# FORGE — Adaptive Difficulty via PPO: Full Technical Reference

Every formula, every transformation, every number — in the order they actually execute. Cross-referenced to the exact file and function they live in.

---

## 1. System Overview

Two halves that never talk to each other at runtime:

```
OFFLINE (Python, once)                    RUNTIME (Godot, every level)
─────────────────────                     ────────────────────────────
Simulated player env                      Player plays, reaches exit
      │                                          │
PPO training (300k steps)                 Main._on_dungeon_escaped()
      │                                          │
Export weights → policy_weights.json ───► PPOPolicy.gd loads + runs it
                                                  │
                                           DifficultyManager applies output
                                                  │
                                           DungeonGenerator builds next level
```

---

## 2. Runtime Pipeline — Every Step, Exact Formula

### Step 1 — Measuring performance (`Main.gd`)

When a dungeon is built, three values are snapshotted:
```gdscript
level_start_time_msec = Time.get_ticks_msec()
level_start_deaths = telemetry_logger.total_deaths
level_start_damage_taken = telemetry_logger.damage_taken
```

When the player touches the exit portal, `_on_dungeon_escaped()` computes the deltas:
```gdscript
completion_time_sec = (Time.get_ticks_msec() - level_start_time_msec) / 1000.0
deaths_this_level = telemetry_logger.total_deaths - level_start_deaths
damage_taken_this_level = telemetry_logger.damage_taken - level_start_damage_taken
```

### Step 2 — Building the observation vector (`DifficultyManager.build_observation()`)

Eight numbers, each normalized to roughly `[0, 1]`:

| # | Name | Formula | Notes |
|---|---|---|---|
| 0 | `norm_time` | `clamp(completion_time_sec / 90.0, 0, 1)` | 90 = `target_time(45) × 2`, so exactly-on-target = 0.5 |
| 1 | `norm_deaths` | `clamp(deaths_this_level / 3.0, 0, 1)` | 3+ deaths saturates to 1.0 |
| 2 | `norm_dmg_ratio` | `clamp(damage_taken_this_level / max(1, player_max_health), 0, 1)` | fraction of max HP lost this level |
| 3 | `norm_hp` | `clamp((enemy_health - 20) / (120 - 20), 0, 1)` | current enemy health, normalized |
| 4 | `norm_dmg` | `clamp((enemy_damage - 5) / (50 - 5), 0, 1)` | current enemy damage, normalized |
| 5 | `norm_haz` | `clamp((hazard_density - 0.05) / (0.80 - 0.05), 0, 1)` | current hazard density, normalized |
| 6 | `norm_rooms` | `clamp((room_count_target - 5) / (9 - 5), 0, 1)` | current room count, normalized |
| 7 | `norm_level` | `clamp(level_num / 10.0, 0, 1)` | dungeon depth, normalized |

The general normalization formula used everywhere (`_normalize`):
```
normalized = clamp((value - range_min) / (range_max - range_min), 0.0, 1.0)
```

### Step 3 — Policy forward pass (`PPOPolicy.predict()`)

**If a trained `policy_weights.json` is loaded**, this is a standard MLP forward pass — the exact same architecture SB3 trained:

```
x₀ = observation                          (8-vector)
x₁ = tanh(W₁·x₀ + b₁)                     (hidden layer 1, 64 units)
x₂ = tanh(W₂·x₁ + b₂)                     (hidden layer 2, 64 units)
raw_action = W₃·x₂ + b₃                   (output layer, 7 units, linear)
action = tanh(raw_action)                 (final squash to [-1, 1])
```
In GDScript, each layer is literally:
```gdscript
for o in range(w.size()):          # for each output neuron
    var s = b[o]                   # start with bias
    for k in range(row.size()):    # dot product with input
        s += w[o][k] * x[k]
    y[o] = s
# then tanh() on every y[o] except the very last layer, which gets tanh()
# applied separately afterward as the final squash
```

**If no trained weights exist** (fallback heuristic, also in `PPOPolicy.gd`):
```
performance_signal = clamp( (0.5 − norm_time)×1.4 − norm_deaths×1.5 − norm_dmg_ratio×0.8,  −1, 1 )
step = 0.12

action[0] (enemy_health)      = clamp( norm_hp×2−1  + performance_signal×step,  −1, 1 )
action[1] (enemy_damage)      = clamp( norm_dmg×2−1 + performance_signal×step,  −1, 1 )
action[2] (enemy_speed)       = clamp( performance_signal × 0.5,                −1, 1 )
action[3] (enemy_aggro)       = clamp( performance_signal × 0.5,                −1, 1 )
action[4] (hazard_density)    = clamp( norm_haz×2−1 + performance_signal×step,  −1, 1 )
action[5] (resource_scarcity) = clamp( performance_signal × 0.3,                −1, 1 )
action[6] (room_count)        = clamp( norm_rooms×2−1 + performance_signal×step, −1, 1 )
```
Reading `performance_signal`: positive = fast clear + no deaths (push difficulty up); negative = slow/deadly level (ease off). The `×2−1` term converts a current normalized value (0 to 1) back into the −1 to 1 action space before adding the nudge, so each parameter shifts from wherever it currently sits rather than jumping to an absolute value.

### Step 4 — Applying the action (`DifficultyManager.apply_ppo_action()`)

Each of the 7 action values (−1 to 1) is denormalized back to a real number:
```
denormalized = range_min + ((clamp(action, −1, 1) + 1) / 2) × (range_max − range_min)
```
Applied per-parameter:

| Action index | Parameter | Range applied |
|---|---|---|
| 0 | `enemy_health` | 20 – 120 |
| 1 | `enemy_damage` | 5 – 50 |
| 2 | `enemy_speed` | 60 – 220 |
| 3 | `enemy_aggro` | 100 – 450 |
| 4 | `hazard_density` | 0.05 – 0.80 |
| 5 | `resource_scarcity` | 0.10 – 0.90 |
| 6 | `room_count_target` | 5 – 9 (then rounded to nearest int) |

### Step 5 — Building the next dungeon (`DungeonGenerator.generate_dungeon()`)

**Layout** — random-walk with branching, grid-based:
- Start room placed at `(0,0)`.
- Loop while `rooms.size() < room_count_target`: pick a random existing room from the frontier queue, try a random direction (N/S/E/W); if that grid cell is empty, place a new room there and connect a door both ways. If no direction works, drop that room from the frontier.
- **Exit room** = whichever room has the greatest Manhattan distance from start: `dist = |x − start_x| + |y − start_y|`.

**Special room ratios** (driven by current `hazard_density` / `resource_scarcity`):
```
num_hazard_rooms   = clamp( int(hazard_density × available_room_count), 1, available_room_count )
num_treasure_rooms = clamp( int((1 − resource_scarcity) × 2.5), 1, 3 )
```
Remaining rooms (not start/exit/hazard/treasure) become `COMBAT` rooms.

**Per-room-type enemy/hazard/pickup counts** (before PPO's `enemy_count_scale` is applied):

| Room type | Enemies (base, random) | Hazards | Pickups |
|---|---|---|---|
| HAZARD | `randi_range(1, 3)` | `clamp(int(hazard_density × 10), 3, 10)` | 0 |
| TREASURE | `randi_range(1, 2)` | 0 | `randi_range(2, 4)` |
| COMBAT | `randi_range(2, 5)` | `clamp(int(hazard_density × 4), 0, 4)` | 1 if `random() > resource_scarcity` else 0 |
| EXIT | `clamp(int(3 + hazard_density × 3), 3, 6)` | `clamp(int(hazard_density × 6), 1, 6)` | — |

**Enemy count scaling** (`_scale_enemies()`), applied on top of every base count above:
```
final_enemy_count = max(1, round(base_count × enemy_count_scale))
```
`enemy_count_scale` itself is not currently a PPO output — it stays at its default `1.0` unless you extend the action vector to control it (see Section 5, "Extending the system").

### Step 6 — Refreshing the Defense Panel (`DefenseOverlay.sync_ui_with_manager()`)

Called immediately after `apply_ppo_action()` so the UI never shows stale numbers. Internally recomputes the same 0–100 difficulty score shown to a human (see Section 3) purely for display — this score has no effect on the PPO pipeline itself.

---

## 3. The Difficulty Score / Explainability Report (`calculate_difficulty_score()`)

This is a **separate, hand-built linear model** used only for the Defense Panel's human-readable score — it does not feed into PPO in either direction.

Normalize each of the 6 base parameters to 0–1 (same normalization formula as Section 2):
```
norm_hp       = clamp((enemy_health − 20) / 100, 0, 1)
norm_dmg      = clamp((enemy_damage − 5) / 45, 0, 1)
norm_spd      = clamp((enemy_speed − 60) / 160, 0, 1)
norm_aggro    = clamp((enemy_aggro − 100) / 350, 0, 1)
norm_haz      = clamp((hazard_density − 0.05) / 0.75, 0, 1)
norm_scarcity = clamp((resource_scarcity − 0.10) / 0.80, 0, 1)
```

Weighted sum (weights sum to 1.0):
```
raw_score = norm_dmg×0.28 + norm_hp×0.22 + norm_spd×0.18 + norm_aggro×0.14 + norm_haz×0.10 + norm_scarcity×0.08
score_0_to_100 = round(raw_score × 100)
```

Tier labels:
```
score < 35            → "Accessible / Easy"
35 ≤ score < 60        → "Balanced / Moderate"
60 ≤ score < 80        → "Intense / Challenging"
score ≥ 80             → "Brutal / Hardcore"
```

Feature attribution (percentage each factor contributed to the score — SHAP-style, but it's really each term's share of the weighted sum):
```
contribution_i% = round( (norm_i × weight_i / total_contribution) × 100 )
```
where `total_contribution` is the same `raw_score` sum above (or `1.0` if it's ~zero, to avoid divide-by-zero). Sorted descending and the top 4 shown in the panel.

---

## 4. Offline Training — Every Formula in the Simulated Environment

### 4.1 Observation and action space

Identical shape/order to the Godot side (Section 2), enforced by `gymnasium.spaces.Box`:
- Observation: `Box(low=0, high=1, shape=(8,))`
- Action: `Box(low=-1, high=1, shape=(7,))`

### 4.2 Simulated player model (`_simulate_level()`)

A "challenge" score is computed from the current (denormalized) parameters:
```
hp_n  = normalize(enemy_health, 20, 120)
dmg_n = normalize(enemy_damage, 5, 50)
spd_n = (enemy_speed − 60) / 160
haz_n = normalize(hazard_density, 0.05, 0.80)

challenge = 0.35×dmg_n + 0.25×hp_n + 0.20×spd_n + 0.20×haz_n
```
Compared against the simulated player's current skill (a number that starts at a random value in `[0.3, 0.6]` and drifts up by `uniform(0, 0.01)` every level, regardless of difficulty — modeling a player who slowly gets better at the game itself):
```
gap = challenge − player_skill        # positive = too hard, negative = too easy
```

**Completion time:**
```
base_time_per_room = target_time(45) / 6
time_mult = 1 + gap × 1.8
completion_time = max(5, room_count × base_time_per_room × time_mult × uniform(0.85, 1.15))
```

**Deaths** (binomial draw, more likely when `gap > 0`):
```
death_prob = clamp(0.5 + gap × 1.2, 0, 0.95)
deaths = Binomial(3, death_prob) if gap > 0 else Binomial(1, max(0, death_prob))
```

**Damage taken ratio:**
```
dmg_ratio = clamp(0.3 + gap × 0.9 + Normal(0, 0.05), 0, 1)
```

### 4.3 Reward function (current, fixed version — see Section 5 for why it changed)

```
target_time_per_room = 45 / 6
time_per_room = completion_time / room_count
time_error = |time_per_room − target_time_per_room| / target_time_per_room

reward = 1 − time_error
reward −= deaths × 0.5
if deaths == 0 and time_per_room < target_time_per_room × 0.5:
    reward −= 0.3        # too easy — should have escalated
if deaths >= 2:
    reward −= 0.4        # too hard — should have eased off

challenge_for_rooms = 0.5×dmg_n + 0.5×hp_n
appropriate_room_count = 5 + challenge_for_rooms × 4
room_mismatch = |room_count − appropriate_room_count| / 4
reward −= room_mismatch × 0.5
```

Episode = 30 simulated levels (`MAX_LEVELS`), then resets with a freshly randomized player skill.

### 4.4 PPO hyperparameters (`train()`)

```
algorithm:      PPO, MlpPolicy
network:        2 hidden layers, 64 units each, tanh activations
n_steps:        2048    (rollout length before each policy update)
batch_size:     256
learning_rate:  3e-4
total_timesteps: 300,000
```

### 4.5 Export format (`export_policy_to_json()`)

Pulls the actor network's weights directly out of SB3's internal modules:
```
model.policy.mlp_extractor.policy_net   → hidden layers' weights/biases
model.policy.action_net                 → final output layer's weights/biases
```
Written as:
```json
{
  "layers": [
    {"w": [[...]], "b": [...]},   // hidden layer 1: shape [64, 8]
    {"w": [[...]], "b": [...]},   // hidden layer 2: shape [64, 64]
    {"w": [[...]], "b": [...]}    // output layer:   shape [7, 64]
  ],
  "activation": "tanh"
}
```
`w[i]` is shape `[out_dim][in_dim]` — i.e. `w[o][k]` is the weight from input `k` to output neuron `o`, exactly matching the loop structure in `PPOPolicy.gd`'s forward pass (Step 3 above).

---

## 5. The Reward-Hacking Bug — Full Before/After

**Diagnosis tool:** `inspect_policy.py` sweeps each observation dimension from 0→1 (holding the rest at 0.5) and measures how much each output moves — confirmed `norm_time` dominated the `room_count` output almost completely, while `norm_deaths` correctly pushed it down but far more weakly.

**Root cause:** the original reward used `time_error = |completion_time − 45| / 45`, and `completion_time = room_count × time_per_room`. Since `room_count` is a direct multiplier on the exact quantity being judged, PPO could satisfy the reward purely by resizing `room_count` — a shortcut requiring zero relationship to actual combat difficulty (enemy stats).

**Fix, in two parts:**
1. Switched to `time_per_room = completion_time / room_count` as the pacing metric — resizing `room_count` no longer moves this term at all, removing the shortcut.
2. Added an explicit `room_mismatch` penalty comparing `room_count` against an `appropriate_room_count` derived from current `enemy_health`/`enemy_damage` — so room count now has to justify itself against real combat difficulty rather than floating free.

You must **retrain** (`python train_ppo_difficulty.py`) and re-export for this fix to take effect — editing the reward function only changes future training runs, not any `policy_weights.json` you already trained under the old reward.

---

## 6. Testing Tools — Exact Behavior

**Auto-Kill toggle** (`Enemy.kill()` → `Room.kill_all_enemies()` → `Main._kill_all_enemies_in_all_rooms()`):
```gdscript
func kill() -> void:
    take_damage(current_health)   # routes through the normal death path
```
Called on every `Enemy` child of every active room. Fires the same `enemy_defeated` signal a real kill would, so telemetry counts stay accurate. Re-applied automatically every time a new dungeon is built while the toggle stays on.

**Minimap exit reveal** (`MiniMap.set_reveal_exit()`): when true, a room's `EXIT`-type color is shown even if `is_visited == false`, plus a white ring drawn via `draw_arc()` at 32% of the cell's radius, distinguishing "revealed but not yet visited" from "already been there."

**`inspect_policy.py` sensitivity formula:** for each observation dimension `d`, holds all others at `0.5`, evaluates the network at `d=0` and `d=1`, and reports `output(d=1) − output(d=0)` for every action — the magnitude of that difference is the reported "swing."

---

## 7. Persistence — Exact Behavior

| State | Persists across restart? | Why |
|---|---|---|
| Dungeon level number | No | `Main.current_dungeon_level` reset to `1` on every `_ready()` |
| `DifficultyManager` fields | No | New `DifficultyManager` instance created fresh in `Main._ready()`, defaulting to the `INTERMEDIATE` preset |
| Trained policy (`policy_weights.json`) | Yes | Static file on disk, reloaded fresh each launch — but it's frozen inference, not online learning, so it reacts to the new session's performance from scratch each time |
| `session_telemetry.json` | Yes | Written by `TelemetryLogger` to `user://`, but nothing currently reads it back in — it's there for later fine-tuning use, not currently consumed at runtime |

---

## 8. Extending the System (if you want to go further)

- **`enemy_count_scale` as an 8th PPO output:** currently fixed at `1.0`; extend the action vector to 8 dimensions and add it to `PARAM_RANGES`/`build_observation`/`apply_ppo_action` symmetrically on both the Python and GDScript sides.
- **Real telemetry fine-tuning:** replace `_simulate_level()`'s formulas with a regression fit against logged `session_telemetry.json` data from actual playtesters, closing the sim-to-real gap described in Section 4.2.
- **Per-room-type difficulty:** right now all rooms in a dungeon share the same global `enemy_health`/`enemy_damage`; a more granular system could let PPO output separate values per room type (HAZARD vs COMBAT vs EXIT).
