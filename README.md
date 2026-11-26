# FORGE — Personalized Procedural Content Generation via Reinforcement Learning

> **Player-telemetry-driven, closed-loop adaptive difficulty for 2D combat dungeon crawlers**
> FAST-NUCES Islamabad · School of Computing · Department of Artificial Intelligence · FYP 2026-27 · Group F26-012

[![CI](https://github.com/Rayan581/forge/actions/workflows/ci.yml/badge.svg)](https://github.com/Rayan581/forge/actions/workflows/ci.yml)
[![Release](https://github.com/Rayan581/forge/actions/workflows/release.yml/badge.svg)](https://github.com/Rayan581/forge/actions/workflows/release.yml)
[![Godot 4.x](https://img.shields.io/badge/Godot-4.x-blue?logo=godot-engine)](https://godotengine.org/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-yellow?logo=python)](https://python.org/)
[![License: Academic](https://img.shields.io/badge/License-Academic%20FYP-lightgrey)](#license--academic-integrity)

---

## Table of Contents

1. [What is FORGE?](#what-is-forge)
2. [Research Motivation](#research-motivation)
3. [Architecture Overview](#architecture-overview)
4. [Repository Structure](#repository-structure)
5. [Quick Start — Playing the Game](#quick-start--playing-the-game)
6. [Controls Reference](#controls-reference)
7. [Gameplay Guide](#gameplay-guide)
8. [Installation and Setup](#installation-and-setup)
9. [AI Pipeline — How Adaptive Difficulty Works](#ai-pipeline--how-adaptive-difficulty-works)
10. [CI/CD Pipeline](#cicd-pipeline)
11. [Testing and Validation](#testing-and-validation)
12. [Development Guide](#development-guide)
13. [Project Team and Supervision](#project-team-and-supervision)
14. [License and Academic Integrity](#license-and-academic-integrity)

---

## What is FORGE?

**FORGE** is a research-grade, closed-loop adaptive-difficulty game engine built in **Godot 4.x** (CI pins 4.3-stable). It combines real-time player telemetry, a **PPO (Proximal Policy Optimization) reinforcement-learning** policy deployed as pure GDScript, and procedural dungeon generation to produce a dungeon-crawler whose difficulty evolves with the player — without a human ever adjusting a slider.

Traditional Dynamic Difficulty Adjustment (DDA) relies on blunt stat-scaling (boosting enemy HP when the player is winning, reducing it when they are losing). FORGE replaces this with a **Controllable PCG-via-RL** loop:

- The game continuously measures **what the player is actually doing** (combat pace, death count, damage taken).
- A trained PPO network translates that data into **structured difficulty parameters** — enemy health, damage, speed, aggro range, hazard density, resource scarcity, and room count.
- The **procedural dungeon generator** builds the next floor using those exact numbers.
- The **Defense Panel overlay** makes every AI decision visible and auditable in real time.

The result: difficulty that responds to demonstrated mechanical skill rather than arbitrary thresholds.

---

## Research Motivation

Mainstream DDA systems (e.g., Resident Evil 4's "Emergency Difficulty Change," Left 4 Dead's Director AI) share a common limitation: they adjust isolated parameters reactively and opaquely. Players often sense the manipulation and feel their performance is being discounted.

FORGE investigates whether **learned difficulty conditioning** — an RL agent trained to produce multi-parameter configurations that keep a player in their flow-state — produces better subjective outcomes than rule-based approaches. Key research questions:

1. Can a PPO policy, trained on a **simulated player model**, generalize to real player sessions without additional fine-tuning?
2. Does **multi-parameter joint optimization** (7 parameters simultaneously) outperform single-axis adjustment?
3. Can the policy's decisions be made interpretable to both the player and an evaluating panel?

Full literature review and research context: [`docs/proposal/FORGE_Proposal.md`](docs/proposal/FORGE_Proposal.md)
Academic papers surveyed: [`papers/`](papers/) and [`docs/research/DDA_Research_Papers.md`](docs/research/DDA_Research_Papers.md)

---

## Architecture Overview

```
+------------------------------------------------------------------+
|                    OFFLINE (Python, one-time)                    |
|                                                                  |
|  DungeonDifficultyEnv (Gymnasium)                                |
|  +-- Simulated player model (_simulate_level)                    |
|       +-- PPO training, 300,000 timesteps (Stable-Baselines3)   |
|             +-- export_policy_to_json() --> policy_weights.json  |
+-------------------------------+----------------------------------+
                                | JSON weights file
                                v
+------------------------------------------------------------------+
|                    RUNTIME (Godot 4.x, every level)              |
|                                                                  |
|  Player plays dungeon floor                                      |
|        | combat_efficiency, deaths, damage_taken, pace           |
|        v                                                         |
|  TelemetryLogger.gd  --> DifficultyManager.build_observation()  |
|                                | 8-vector, normalized [0,1]     |
|                                v                                 |
|                        PPOPolicy.predict()                       |
|                        MLP forward pass, pure GDScript           |
|                        tanh(64)(64)(7)  -- ~0.21 ms        |
|                                | 7-vector, [-1,1]               |
|                                v                                 |
|                  DifficultyManager.apply_ppo_action()           |
|                  Denormalize to real parameter values           |
|                                |                                 |
|                                v                                 |
|                  DungeonGenerator.generate_dungeon()            |
|                  Next floor built with new parameters           |
|                                |                                 |
|                                v                                 |
|                  DefenseOverlay.sync_ui_with_manager()          |
|                  All decisions visible in real time             |
+------------------------------------------------------------------+
```

![FORGE Closed-Loop Architecture](assets/arch_closedloop.png)

---

## Repository Structure

```
FORGE/
+-- godot_prototype/               <- Primary deliverable: playable game
|   +-- scenes/                    Godot scene files (.tscn)
|   |   +-- Main.tscn              Root scene (entry point)
|   |   +-- MainMenu.tscn          Title screen
|   |   +-- Room.tscn              Dungeon room template
|   |   +-- Player.tscn            Player character
|   |   +-- Enemy.tscn             Base enemy
|   |   +-- Hazard.tscn            Floor hazard
|   |   +-- Pickup.tscn            Health pickup
|   |   +-- DefenseOverlay.tscn    AI transparency panel
|   |   +-- LevelSplash.tscn       Level transition card
|   |   +-- DamageFloater.tscn     Damage number popup
|   |   +-- ProjectileFireball.tscn  Ranged enemy projectile
|   +-- scripts/                   GDScript game logic
|   |   +-- Main.gd                Game loop, level transitions, PPO orchestration
|   |   +-- Player.gd              Movement, melee, dodge roll, health
|   |   +-- Enemy.gd               AI archetypes (Melee Crawler, Ranged Pyromancer)
|   |   +-- Room.gd                Room spawning, door management, completion logic
|   |   +-- DungeonGenerator.gd    Procedural layout (random-walk grid)
|   |   +-- DifficultyManager.gd   Parameter management, PPO I/O translation
|   |   +-- PPOPolicy.gd           Neural network forward pass + fallback heuristic
|   |   +-- TelemetryLogger.gd     Per-session data capture -> session_telemetry.json
|   |   +-- DefenseOverlay.gd      Evaluator panel: sliders, score, attribution chart
|   |   +-- MiniMap.gd             Floor minimap with exit reveal
|   |   +-- LevelSplash.gd         Level card animation
|   |   +-- DamageFloater.gd       Floating damage number animation
|   |   +-- Hazard.gd              Hazard tick damage
|   |   +-- Pickup.gd              Pickup collection
|   |   +-- ProjectileFireball.gd  Fireball trajectory and impact
|   +-- ai/                        Runtime AI weights + sensitivity script (jh.py)
|   |   +-- policy_weights.json    Exported PPO network (~111 KB)
|   +-- tests/                     Headless Godot test scripts
|   |   +-- ci_solvability_runner.gd  500-seed dungeon solvability harness (CI)
|   |   +-- benchmark_inference.gd    PPO inference latency benchmark
|   |   +-- test_static_baseline.gd   Static baseline unit test
|   +-- assets/                    Pixel art sprites and fonts
|   +-- export_presets.cfg         Godot Windows export configuration
|   +-- project.godot              Godot project manifest
|
+-- ml_spike/                      Python RL training pipeline
|   +-- train_ppo_difficulty.py    PPO training + JSON weight export
|   +-- ppo_difficulty_model.zip   Saved SB3 model checkpoint
|   +-- requirements.txt           Python dependencies
|   +-- tests/                     pytest suites (env, policy, smoke, parity, performance)
|   +-- analysis/                  Training curves, policy evaluation, figure scripts
|
+-- .github/workflows/             CI/CD automation
|   +-- ci.yml                     Lint, pytest, policy checks, Godot import/solvability/PCK
|   +-- release.yml                Windows PE32+ build packaging
|
+-- docs/                          Comprehensive documentation & university deliverables
|   +-- guidelines/                FAST-NUCES policies, grading rubrics, orientation notes
|   +-- research/                  DDA literature surveys, related works, paper dossiers
|   +-- proposal/                  Full FYP proposal (Markdown + DOCX), defense slides, CCP justification
|   +-- mid_evaluation/            Mid-1 presentation deck, implementation roadmap, session logs
|   +-- reports/mid_report/        Mid-1 formal report submissions
|       +-- latex/                 LaTeX report source (main.tex, chapters/, ThesisFigs/)
|       +-- diagrams/              Draw.io vector sources and diagram exports
|       +-- *.pdf                  Signed final submission PDF and compiled reports
|
+-- assets/                        Art assets, diagrams & showcase deliverables
|   +-- diagrams/                  Architecture & Gantt SVG/PNG diagrams
|   +-- poster/                    Exhibition poster PSD, fonts, and preview renders
|   +-- 2D Pixel Dungeon Asset Pack/ Tilemaps and character animations
|   +-- Enemy_Animations_Set/      Enemy sprite animations
|
+-- papers/                        Curated academic paper library (PDFs)
+-- tools/                         Build scripts, tectonic LaTeX compiler, Godot launcher
+-- AI Logs/                       AI usage disclosure log (FAST requirement)
+-- archive/                       Historical spikes and early outlines
+-- scratch/                       Temporary scratch scripts and intermediate notes
+-- CHANGES.md                     Formal scope change control register
+-- TODO.md                        Active development roadmap & action items
```

---

## Quick Start — Playing the Game

### Option A: Download Pre-built Release (Recommended)

1. Go to the [**Releases**](https://github.com/Rayan581/forge/releases) tab.
2. Download `FORGE-Windows-v*.zip` from the latest release.
3. Extract and run `FORGE.exe` — no Godot installation required.

### Option B: Run from Source in Godot Editor

**Requirements:** [Godot Engine 4.x](https://godotengine.org/download) (standard, not Mono/C#). CI runs 4.3-stable; development used 4.7.x.

```bash
# 1. Clone the repository
git clone https://github.com/Rayan581/forge.git
cd forge

# 2. Open Godot, click Import
# 3. Browse to: godot_prototype/project.godot
# 4. Click "Import & Edit"
# 5. Press F5 (or the Play button) to run
```

The game opens at the **Main Menu**. Click **Start** to begin your first floor.

---

## Controls Reference

### Movement and Combat

| Key / Button | Action |
| :--- | :--- |
| `W` or Up Arrow | Move Up |
| `S` or Down Arrow | Move Down |
| `A` or Left Arrow | Move Left |
| `D` or Right Arrow | Move Right |
| `Left Click` or `J` | Melee attack (sword swing) |
| `Space` or `Shift` | **Dodge Roll** — brief invincibility frames, rolls in movement direction |

### Interface

| Key | Action |
| :--- | :--- |
| `Tab` or `` ` `` (backtick) | Toggle **Defense Panel** (AI transparency overlay) |

### Defense Panel Controls (evaluator / developer mode)

| Control | Action |
| :--- | :--- |
| Sliders (Enemy HP, Damage, Speed, etc.) | Manually override current difficulty parameters |
| **Auto-Kill Enemies** checkbox | Instantly kills all enemies in every room (test mode) |
| **Reveal Exit** toggle | Reveals exit room on minimap even before visiting |
| **Preset buttons** (Novice / Intermediate / Expert) | Snap all parameters to preset values |
| **Static Baseline (+8% / floor)** toggle | Disables the PPO policy and scales difficulty by a fixed +8% per floor (non-adaptive comparison condition) |

---

## Gameplay Guide

### Objective

Descend through procedurally generated dungeon floors. Each floor ends when you find and step through the **exit portal** (glowing doorway, marked on the minimap once unlocked). There is no final boss — FORGE is a research prototype demonstrating infinite-depth adaptive difficulty.

### Floor Structure

Each floor is a **connected graph of rooms** generated fresh by a random-walk grid algorithm. Room count (5 to 9) is controlled by the PPO policy based on your recent performance.

| Room Type | Minimap Color | Contents |
| :--- | :--- | :--- |
| **Start** | Green | Where you spawn each floor. No enemies. |
| **Combat** | Grey | 2-5 enemies and occasional hazards and pickups. |
| **Hazard** | Orange | Dense floor hazards, 1-3 enemies, no pickups. |
| **Treasure** | Yellow | 1-2 enemies plus 2-4 health pickups. |
| **Exit** | White (ring when revealed) | Portal to next floor. Enemies guard it. |

### Enemies

| Archetype | Behavior | Threat Level |
| :--- | :--- | :--- |
| **Melee Crawler** | Chases the player and slashes at close range. Stats are set by the PPO policy. | Primary threat in most rooms. |
| **Ranged Pyromancer** | Keeps its distance and fires fireballs; kites away when approached. | High damage from safety; prioritize over brutes. |

Enemy stats (HP, damage, speed, aggro range) are live values set by the PPO policy at the start of each floor. You can read the current values in the **Defense Panel**.

### Health and Death

- Your health bar is displayed at the top-left of the screen.
- Damage numbers float above your character when hit.
- If your HP reaches 0, the floor resets at the **same difficulty level**. Deaths are counted as telemetry and fed back into the policy — repeated death will cause the next floor to ease off.
- There is no game-over screen; FORGE is designed for continuous play sessions for telemetry collection.

### Pickups

Green orbs dropped in Treasure rooms restore a fixed amount of HP on contact. Resource scarcity (controlled by the PPO policy) affects how many spawn per floor.

### The Defense Panel (Press Tab or backtick)

The Defense Panel is an **AI transparency interface** that shows you exactly what the policy decided and why:

- **Difficulty Score (0-100):** Composite weighted score across all 6 parameters.
- **Tier label:** Accessible / Easy, Balanced / Moderate, Intense / Challenging, Brutal / Hardcore.
- **Feature Attribution bars:** Which factor is contributing most to the current difficulty (modelled after SHAP values, computed as each parameter's weighted share of the total score).
- **Live sliders:** Read and optionally override each difficulty parameter in real time.
- **PPO mode indicator:** Shows whether the trained network or the fallback heuristic is active.
- **Static Baseline toggle:** Switches to the non-adaptive baseline for comparison.

---

## Installation and Setup

### Playing Only

See [Quick Start](#quick-start--playing-the-game). No Python required.

### Running the ML Training Pipeline

**Requirements:** Python 3.10+, pip

```bash
cd ml_spike
pip install -r requirements.txt
python train_ppo_difficulty.py
```

This trains a fresh PPO policy (approximately 5-10 minutes on a modern CPU) and writes `policy_weights.json`. Copy the output file to `godot_prototype/ai/policy_weights.json` to deploy it.

To inspect what a trained policy is responding to, run the sensitivity sweep:

```bash
python godot_prototype/ai/jh.py
```

It holds every other observation at 0.5, sweeps one dimension at a time from 0 to 1 and prints the output sensitivity, which helps catch reward-hacking behaviour before it appears in-game.

To reproduce the Mid Report's training curves and policy evaluation (PPO vs. static baseline vs. random, 500 seeds), see [`ml_spike/analysis/README.md`](ml_spike/analysis/README.md).

### Python Development Environment

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# Install all Python dependencies
pip install -r ml_spike/requirements.txt
pip install ruff

# Run linter
ruff check ml_spike/
```

---

## AI Pipeline — How Adaptive Difficulty Works

### Overview

The pipeline is split into two phases that share **no runtime dependency**:

| Phase | Environment | Frequency |
| :--- | :--- | :--- |
| **Training** | Python, Gymnasium, Stable-Baselines3 | Once, or on retrain |
| **Inference** | GDScript, Godot 4.x | Every level end |

### Observation Vector (8 dimensions, normalized to [0, 1])

| Index | Name | Formula |
| :---: | :--- | :--- |
| 0 | Completion time | `clamp(time_sec / 90.0, 0, 1)` |
| 1 | Deaths this level | `clamp(deaths / 3.0, 0, 1)` |
| 2 | Damage-taken ratio | `clamp(damage / max_hp, 0, 1)` |
| 3 | Current enemy HP | `clamp((hp - 20) / 100, 0, 1)` |
| 4 | Current enemy damage | `clamp((dmg - 5) / 45, 0, 1)` |
| 5 | Current hazard density | `clamp((haz - 0.05) / 0.75, 0, 1)` |
| 6 | Current room count | `clamp((rooms - 5) / 4, 0, 1)` |
| 7 | Floor depth | `clamp(level / 10.0, 0, 1)` |

### Neural Network Architecture (PPOPolicy.gd)

```
Input (8) -> tanh -> Linear(64) -> tanh -> Linear(64) -> tanh -> Linear(7) -> tanh -> Output (7)
```

Implemented as a hand-unrolled matrix multiply in GDScript — no ML runtime, no external process, no network calls. Measured inference time: **~0.21 ms mean (0.36 ms max)** per call (`tests/benchmark_inference.gd`).

### Action Vector (7 dimensions, range [-1, 1])

| Index | Parameter | Real Range |
| :---: | :--- | :--- |
| 0 | `enemy_health` | 20 to 120 HP |
| 1 | `enemy_damage` | 5 to 50 |
| 2 | `enemy_speed` | 60 to 220 px/s |
| 3 | `enemy_aggro` | 100 to 450 px |
| 4 | `hazard_density` | 0.05 to 0.80 |
| 5 | `resource_scarcity` | 0.10 to 0.90 |
| 6 | `room_count` | 5 to 9 (integer) |

Denormalization formula: `value = min + ((action + 1) / 2) * (max - min)`

### Cold-Start Protocol (Floors 1-5)

Before the PPO policy has sufficient session data, Floors 1-5 use a **weighted calibration ramp**:

```
CR0 = sum(floor_score_i * w_i)    where w = [1.0, 1.5, 2.0, 2.5, 3.0]
```

This computes an initial Calibration Rating `CR0` that seeds the first PPO inference; the PPO policy takes over from Floor 6.

### Reward-Hacking: A Real Engineering Finding

During development, the sensitivity sweep (`godot_prototype/ai/jh.py`) revealed that an early policy was satisfying the time-based reward purely by inflating `room_count` (more rooms = longer completion time = on-target), with no relationship to actual combat difficulty. This is a textbook **reward hacking** failure.

**Fix:** replaced raw completion-time error with **per-room pacing** (`time / room_count`), so resizing room count no longer moves the metric. A separate `room_mismatch` penalty ties room count to combat difficulty (enemy HP and damage), forcing the policy to justify room count choices against actual threat level.

The diagnostic, detection method and fix are documented in `godot_prototype/README_FULL_PIPELINE.md`.

### Fallback Heuristic

If `policy_weights.json` is absent or fails to load, `PPOPolicy.gd` activates a deterministic rule-based fallback — the game remains fully playable and demonstrates escalating and de-escalating difficulty, just without the learned policy.

---

## CI/CD Pipeline

All pushes and pull requests to `main` trigger the **CI workflow** (`.github/workflows/ci.yml`):

| Job / Stage | Tool | What it checks |
| :--- | :--- | :--- |
| **Python Lint** | `ruff` | Lint and format check of `ml_spike/` |
| **Python Tests** | `pytest` | Environment validation, policy validation, PPO smoke test, inference parity, performance (coverage + JUnit artifacts) |
| **Policy JSON Validation** | Python | Schema/value checks, size gate (< 120 KB), Python-vs-JSON inference parity |
| **Godot Import / Load Check** | headless Godot | All `.gd`, `.tscn` and `.tres` resources load |
| **Solvability** | `ci_solvability_runner.gd` | 500 randomized dungeons are reachable from start to exit (BFS) |
| **Parse / Scenes / Policy / PCK** | headless Godot | Startup parse check, required scenes exist, policy JSON present in the game tree, PCK export smoke test |

The **Release workflow** (`.github/workflows/release.yml`) triggers on version tags (`v*`) and packages a signed Windows PE32+ executable and `.pck` bundle.

### Running CI Locally

```bash
# Python lint
ruff check ml_spike/

# Godot headless solvability (CI uses Godot 4.3-stable)
godot --headless --path godot_prototype --script tests/ci_solvability_runner.gd

# Python tests
pytest ml_spike/tests
```

---

## Testing and Validation

### Automated Tests

| Suite | Location | What it verifies |
| :--- | :--- | :--- |
| Environment validation | `ml_spike/tests/test_env_validation.py` | Gymnasium env spaces, rewards and observation bounds |
| Policy validation | `ml_spike/tests/test_policy_validation.py` | `policy_weights.json` schema, shapes and finite values |
| PPO smoke test | `ml_spike/tests/test_ppo_smoke.py` | Short training run completes and exports |
| Inference parity | `ml_spike/tests/test_inference_parity.py` | Python forward pass matches the exported JSON weights |
| Performance | `ml_spike/tests/test_performance.py` | Inference latency budget |
| Solvability harness | `godot_prototype/tests/ci_solvability_runner.gd` | 500 / 500 generated dungeons are solvable (CI enforced) |
| Inference benchmark | `godot_prototype/tests/benchmark_inference.gd` | `PPOPolicy.gd` latency (~0.21 ms mean, 0.36 ms max) |
| Static baseline | `godot_prototype/tests/test_static_baseline.gd` | Non-adaptive baseline scales parameters by +8% per floor |

The manual test cases are listed in the appendix of the Mid Report.

### Manual Validation

Use the **Auto-Kill toggle** in the Defense Panel to instantly clear all enemies and sprint directly to the exit. This lets you observe difficulty escalation across 10+ floors in under 2 minutes without fighting.

Watch the **Difficulty Score** and **feature attribution bars** in the Defense Panel update at each level transition — the policy should visibly push parameters upward on clean clears and pull back after deaths.

### Non-Functional Requirements

| NFR | Target | Verification Method |
| :--- | :--- | :--- |
| **NFR-01** Frame rate | 60+ FPS on integrated GPU | Manual testing and Godot profiler |
| **NFR-02** PPO inference | Under 1 ms per call | `benchmark_inference.gd` (measured ~0.21 ms mean, 0.36 ms max) |
| **NFR-03** Startup time | Under 5 s on cold launch | Stopwatch across 5 trials |
| **NFR-04** Policy weights size | 150 KB or less | `policy_weights.json` is ~111 KB (CI gate: < 120 KB) |
| **NFR-05** Solvability | 100% across 500 seeds | CI pipeline enforced per push |

---

## Development Guide

### Project Conventions

- **GDScript style:** 4-space indent, `snake_case` variables, `PascalCase` class names.
- **Python style:** enforced by `ruff 0.4.10` (configuration in `ruff.toml`).
- **AI usage:** all AI-assisted work must be logged in `AI Logs/AI logs.xlsx` with the format: `[ID] | Date | Tool | Prompt summary | Files affected | Human review`.
- **Commit messages:** use conventional commits — `feat:`, `fix:`, `ci:`, `docs:`, `chore:`.

### Adding a New Enemy Archetype

1. Create a new scene inheriting `Enemy.tscn`.
2. Override `_ready()` in `Enemy.gd` to set archetype-specific base stats.
3. Register the archetype in `Room.gd`'s `_spawn_enemies()` weighted pool.
4. Add a test case verifying damage and the death signal.

### Retraining the Policy

```bash
cd ml_spike
python train_ppo_difficulty.py
# Outputs: policy_weights.json + ppo_difficulty_model.zip

# Deploy to Godot
copy policy_weights.json ..\godot_prototype\ai\policy_weights.json
```

After retraining, run `python godot_prototype/ai/jh.py` to verify no reward hacking has occurred before committing the new weights.

### File Ownership (team reference)

| Component | Primary Author |
| :--- | :--- |
| `Player.gd`, `Enemy.gd`, `Room.gd`, `Main.gd`, `DungeonGenerator.gd`, combat, scenes and sprites | Rayan Ahmed (23i-0018): Engine / Gameplay |
| `train_ppo_difficulty.py`, `PPOPolicy.gd`, `DifficultyManager.gd` (incl. CR0), ML pipeline | Rana Raza Ahmed (23i-0060): ML / PCG |
| `TelemetryLogger.gd`, `DefenseOverlay.gd`, CI/CD workflows, evaluation and `ml_spike/analysis` | Uwaid Munir (23i-2574): Telemetry / CI / Evaluation |

--- | :--- |
| `PPOPolicy.gd`, `DifficultyManager.gd` | Rayan Ahmed (23i-0018) |
| `train_ppo_difficulty.py`, ML pipeline | Rana Raza Ahmed (23i-0060) |
| `TelemetryLogger.gd`, `DefenseOverlay.gd` | Uwaid Munir (23i-2574) |
| `DungeonGenerator.gd`, `Room.gd`, `Main.gd` | Rayan Ahmed (23i-0018) |
| `Player.gd`, `Enemy.gd`, combat system | Rayan Ahmed (23i-0018) |
| CI/CD workflows (`.github/workflows/`) | Rayan Ahmed (23i-0018) |

---

## Project Team and Supervision

| Role | Name | ID / Contact |
| :--- | :--- | :--- |
| **Engine / Gameplay** | Rayan Ahmed | 23i-0018 |
| **ML / PCG** | Rana Raza Ahmed | 23i-0060 |
| **Telemetry / CI / Evaluation** | Uwaid Munir | 23i-2574 |
| **Supervisor** | Ms. Mehreen Javaid | Department of AI, FAST-NUCES |
| **HOD** | Mr. Ahmad Din | School of Computing |
| **Director** | Dr. Waseem Shehzad | FAST-NUCES Islamabad |
| **Institution** | FAST-NUCES, Islamabad | School of Computing |

**FYP Batch:** Fall 2026 (batch 2023-2027), Group F26-012
**Evaluation Stage:** FYP-1 Mid (Mid-1) submission

---

## License and Academic Integrity

This repository is maintained as part of the Senior Final Year Project at the **National University of Computer and Emerging Sciences (FAST-NUCES)**, Islamabad. All work is subject to FAST's academic integrity policy.

- **Academic sources** are cited in [`docs/proposal/FORGE_Proposal.md`](docs/proposal/FORGE_Proposal.md) and archived in [`papers/`](papers/).
- **AI-assisted development** is disclosed in [`AI Logs/AI logs.xlsx`](AI%20Logs/AI%20logs.xlsx) per FAST FYP guidelines.
- **Third-party assets:** pixel art sprites generated with [`generate_prototype_sprites.py`](generate_prototype_sprites.py); Google Fonts (Inter) used under the Open Font License.

This project is **not** open-source licensed for external use. All rights reserved by the authors and FAST-NUCES pending formal submission.
