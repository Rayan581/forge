# FORGE — Adaptive Difficulty via PPO (Proof of Concept)

This document explains everything added on top of the original FORGE prototype: what problem it solves, how the pipeline works end to end, every file that changed and why, the bugs found and fixed along the way, and how to present this as a proof of concept in your FYP defense.

---

## 1. The Problem This Solves

The original prototype had a **fixed dungeon generator**: room count was a hardcoded formula (`clampi(5 + level_num, 5, 9)`), and enemy stats came from whatever the Defense Panel's manual sliders or presets (Novice/Intermediate/Expert) were set to. Nothing in the game reacted to how the player was actually performing.

The goal: replace that static generation with a system where **the dungeon adapts to the player automatically** — clear levels quickly and cleanly, and the next dungeon gets harder (more rooms, tougher enemies); struggle or die a lot, and it eases off. And instead of hand-coding that reactive logic with if/else rules, learn it with **PPO (Proximal Policy Optimization)**, a reinforcement learning algorithm.

---

## 2. Why This Needed a Hybrid Architecture

Godot cannot train or run PyTorch models natively. So the system is split into two halves that never talk to each other at runtime:

| Phase | Where | What happens |
|---|---|---|
| **Training** | Python, offline, once (or whenever you retrain) | A PPO agent learns, over hundreds of thousands of simulated attempts, what difficulty parameters to output given a player's recent performance. |
| **Inference** | GDScript, inside Godot, every time a level ends | The *already-trained* network's weights are loaded from a JSON file and run through a plain matrix-multiply forward pass — no ML runtime, no Python process, no network calls needed in the shipped game. |

This is why there are two very different kinds of files in this project: a Python training script that never ships with the game, and a handful of `.gd` files that do.

---

## 3. The Full Pipeline, Step by Step

**Offline (done on your dev machine, before/between builds):**

1. `ai_training/train_ppo_difficulty.py` defines a simulated dungeon-difficulty environment and trains a PPO agent (Stable-Baselines3) against it for 300,000 timesteps.
2. The trained network's weights are exported to plain JSON (`policy_weights.json`) — just matrices and bias vectors, nothing PyTorch-specific.
3. That JSON file is copied into the Godot project at `res://ai/policy_weights.json`.

**At runtime (every time someone plays):**

1. `Main.gd` loads `policy_weights.json` once at startup via `PPOPolicy.gd`. If the file isn't there yet, it silently falls back to a hand-written heuristic so the game still runs and can be demoed before you've trained anything.
2. The player fights through a dungeon and reaches the exit room (the one with the portal in its center — marked `RoomType.EXIT`, chosen as whichever room is furthest from the start).
3. The moment they step through, `Main._on_dungeon_escaped()` fires and measures **that level's performance**: completion time, deaths, damage taken (all measured as deltas from a snapshot taken when the level started).
4. `DifficultyManager.build_observation()` packages that performance plus the current difficulty settings into an 8-number vector, normalized to roughly 0–1.
5. `PPOPolicy.predict()` runs that vector through the trained network's forward pass and returns a 7-number action vector (each in −1 to 1).
6. `DifficultyManager.apply_ppo_action()` maps those back onto real values: `enemy_health`, `enemy_damage`, `enemy_speed`, `enemy_aggro`, `hazard_density`, `resource_scarcity`, `room_count_target`.
7. `DungeonGenerator.generate_dungeon()` builds the next dungeon using those exact numbers.
8. The Defense Panel's sliders/score/labels are refreshed (`sync_ui_with_manager()`) so you can *see* what the policy just decided, live.

This loop repeats every level, for the whole session.

---

## 4. Files Changed, and Why

| File | What was added |
|---|---|
| `scripts/PPOPolicy.gd` *(new)* | Loads the trained weights JSON and runs the forward pass in pure GDScript. Contains the rule-based fallback used when no trained weights exist. |
| `scripts/DifficultyManager.gd` | Added `room_count_target`, `enemy_count_scale`, `PARAM_RANGES`, `build_observation()`, `apply_ppo_action()` — the translation layer between the game's real numbers and the policy's normalized ones. |
| `scripts/DungeonGenerator.gd` | Enemy counts per room now scale by `enemy_count_scale` via a new `_scale_enemies()` helper. Room count now comes from `p_diff.room_count_target` instead of a fixed formula. |
| `scripts/Main.gd` | Tracks per-level start time/deaths/damage; calls the PPO pipeline in `_on_dungeon_escaped()`; wires the Auto-Kill toggle. |
| `scripts/Enemy.gd` | Added `kill()` — instant death routed through the normal `take_damage()` path so telemetry/signals stay accurate. |
| `scripts/Room.gd` | Added `kill_all_enemies()`, used by the Auto-Kill toggle. |
| `scripts/MiniMap.gd` | Added `reveal_exit` — when on, the exit room (the one with the door/portal) is shown on the minimap even before the player has visited it, with a white ring to mark it as "revealed, not yet been there." |
| `scripts/DefenseOverlay.gd` + `scenes/DefenseOverlay.tscn` | New **"☠ Auto-Kill Enemies (Testing)"** checkbox; new label showing the PPO-controlled `room_count`/`enemy_count_scale` (previously invisible in the panel); fixed the panel going stale after PPO updates (see bug list below). |
| `ai_training/train_ppo_difficulty.py` *(new)* | The actual PPO training script — see Section 5. |
| `ai_training/inspect_policy.py` *(new)* | Diagnostic tool — sweeps each observation dimension and shows how much it moves each output, to reveal what the trained network is actually reacting to. |

**Nothing pre-existing was removed or rewritten** — every diff against your original upload is additive except one line (`room_count` now reads from `difficulty_manager.room_count_target` instead of a hardcoded formula), which is the one change that had to happen for PPO to have any effect at all.

---

## 5. How Training Actually Works (Be Precise About This in Your Defense)

`train_ppo_difficulty.py` does **not** run your actual Godot game. It trains against a small **simulated player model** — a hand-written formula that guesses completion time, deaths, and damage taken given a set of difficulty parameters and a "skill" number that drifts upward slowly over a simulated run. This is a standard bootstrapping technique (sim-to-real transfer): PPO needs hundreds of thousands of attempts to learn anything, far more than any real human could playtest.

**Be upfront about this if asked** — it's a completely normal first step for an FYP, not something to hide. The honest framing: *"This proves the pipeline and the algorithm work end-to-end; the next step is fine-tuning it on real playtester telemetry."*

### The Observation → Action Contract

- **Observation (8 numbers, each ~0–1):** last-level completion time, deaths, damage-taken ratio, current enemy health, current enemy damage, current hazard density, current room count, current level number.
- **Action (7 numbers, each −1 to 1, later mapped to real ranges by Godot):** enemy_health, enemy_damage, enemy_speed, enemy_aggro, hazard_density, resource_scarcity, room_count.

This contract is identical on both the Python and GDScript sides — that's what lets a trained network be dropped into the game with zero code changes on the Godot side.

### Reward Function (and a Bug We Found and Fixed)

The first version of the reward compared raw completion time against a fixed target. Since `completion_time = room_count × time_per_room`, this let the agent satisfy the time target purely by inflating `room_count`, with no regard for actual combat difficulty — a classic **reward hacking** failure. We confirmed this empirically with `inspect_policy.py`, which showed completion time dominating the room-count output almost entirely.

**Fix:** the reward now judges pace **per room**, not as a raw total, so resizing room count no longer moves that term. Room count is instead judged separately, against how well it tracks the current combat challenge (more danger → more rooms is "appropriate"; padding rooms with no corresponding challenge increase is penalized). Death penalties were already working correctly and were left unchanged.

---

## 6. Testing Tools Added

**Auto-Kill toggle** (Defense Panel → "☠ Auto-Kill Enemies (Testing)"): instantly kills every enemy in the current dungeon and every dungeon generated afterward while it's on, so you can walk straight to the exit and watch difficulty escalate across levels without needing to fight. The exit room is also revealed on the minimap while this is active, so you can find it immediately.

**`inspect_policy.py`**: run against any `policy_weights.json` to see, numerically, which observation dimension drives each output the most — useful for catching reward-hacking issues like the one above before they show up as weird in-game behavior.

---

## 7. Known Bugs Found and Fixed Along the Way

1. **Stale Defense Panel after PPO updates.** The sliders/score/driver breakdown only refreshed on manual slider drags or preset clicks; they went stale after PPO silently changed parameters at level-end. Fixed by calling `sync_ui_with_manager()` right after `apply_ppo_action()`.
2. **Room count reward hacking** (Section 5) — fixed via per-room pacing in the reward function.
3. **Fallback heuristic escalated too aggressively** — an early version of the rule-based fallback (used only when no trained weights exist) could saturate room count to its max after 2–3 fast clears. Tuned the step size down so it takes a genuine run of good levels to climb, and actually comes back down on a bad level instead of sticking at the ceiling.

---

## 8. What Does and Doesn't Persist Across Restarts

- **Does not persist:** dungeon progress. Every launch starts at level 1 with default (Intermediate) difficulty — `Main._ready()` creates a fresh `DifficultyManager` each time, and there's no save file.
- **Does persist:** the trained policy itself — `policy_weights.json` is a static file on disk, loaded fresh each launch. It doesn't keep learning during play (it's frozen inference), so each new session is the same trained "brain" reacting to a new player's performance from scratch — which is the correct behavior for treating each playthrough independently.

---

## 9. How to Present This POC

The strongest framing for a defense: this demonstrates a **working, end-to-end adaptive-difficulty pipeline** —

1. A real RL algorithm (PPO) trained against a simulated environment with an explicit, inspectable reward function.
2. A genuine deployment path into a game engine that can't run ML natively (export → pure-GDScript inference), which is itself a meaningful engineering contribution, not just "call an API."
3. Diagnostic tooling (`inspect_policy.py`) that caught and let you fix a real reward-hacking failure mode — a legitimate finding, not just a demo that happened to work.
4. A clear, stated path to the next stage: replacing the simulated player with real playtester telemetry (`session_telemetry.json` is already being logged) to close the sim-to-real gap.

That last point matters — proposing exactly what real data collection and retraining would look like next is usually stronger for a proposal defense than pretending the simulated version is the finished product.
