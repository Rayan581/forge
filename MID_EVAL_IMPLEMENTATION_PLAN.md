# FORGE — FYP-1 Mid-Evaluation Lean Implementation Plan

**Project:** F26-012-FORGE — Personalized Procedural Content Generation via Reinforcement Learning  
**Target Milestone:** Stage 2 / Gates 2 & 3 (Mid-1 Evaluation — Week 10)  
**Authors & Leads:** Rayan Ahmed (23i-0018), Rana Raza Ahmed (23i-0060), Uwaid Munir (23i-2574)  
**Faculty Supervisor:** Ms. Mehreen Javaid  
**Repository:** `Rayan581/forge` (private GitHub) — **28 commits** across Weeks 1–10  
**Status as of:** October 15, 2026

---

## Executive Status Dashboard

| Work Package | Status | Key Commit(s) |
| :--- | :---: | :--- |
| WP1 — Enemy Variety & Dodge Roll | ✅ **Done** | `35654da`, `cb56ca3` |
| WP2 — Visual Aesthetics & Sprites | ✅ **Done** | `b7dd94f`, `367b803`–`8637b03` |
| WP3 — 5-Floor Cold-Start Protocol | ✅ **Done** | `b7dd94f`, `8637b03` |
| WP4 — FAST CI/CD Pipeline | ✅ **Done** | `c0d9813`, `4e46fbc`, `7b2a8d8` |
| WP5 — Formal SRS/SDS Documentation | ✅ **Done** | `1044ee8`, `b7dd94f` |

**All 7 Mid-1 scope commitments delivered. Repository: 28 commits, 16 GDScript modules.**

---

## 1. Scope Boundary: Strict Mid-1 Commitments vs. Deferred Items

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   IN-SCOPE FOR MID-1 (WEEKS 7–10)                      │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Dungeon Sprites & Aesthetics: Replace raw circles with 2D sprites,  │
│    add camera shake + floating damage text. [✔]                        │
│ 2. Enemy Attack Variety: Ranged Pyromancer + Melee Crawler. [✔]        │
│ 3. Cold-Start Protocol: 5 calibration levels before PPO loop. [✔]      │
│ 4. Static Baseline Mode: Playable without AI. [✔]                      │
│ 5. Telemetry Logger: Flat JSON logger. [✔]                             │
│ 6. FAST CI/CD Pipeline: Headless Godot solvability test. [✔]           │
│ 7. Documentation: Formal SRS (Gate 2) & SDS (Gate 3). [✔]             │
└────────────────────────────────────────────────────────────────────────┘
```

### Explicitly Deferred Items (NOT in Mid-1 Scope)
* **SQLite Database Migration:** Gate 3 (Final-1). Flat JSON active.
* **4–5 Enemy Archetypes:** Gate 3 Exit. Mid-1 delivers 2 archetypes. ✔
* **Rule-Based BSP Generator Baseline:** Final-1 (Week 14).
* **In-Run Equipment Shop Economy:** Final-1 (Week 14).
* **Empirical ML Judge Regressor & TreeSHAP:** Mid-2 (Week 26).
* **10-Participant Human UAT Study:** Final-2 (Week 32 / Gate 5).

---

## 2. Work Package 1: Enemy Attack Variety & Non-AI Baseline ✅

**Key commits:** `35654da` (Oct 14) — Ranged Pyromancer + dodge roll | `cb56ca3` (Oct 14) — spawn/trigger bug fix

### 2.1 Enemy Types

| Enemy Type | Script | Movement & AI | Attack |
| :--- | :--- | :--- | :--- |
| **Melee Crawler** *(polished)* | `Enemy.gd` (MELEE state) | Chases player, aggro radius 240 px | Contact slash: 20 dmg, 0.8s cooldown |
| **Ranged Pyromancer** *(new Mid-1)* | `Enemy.gd` (RANGED state) + `ProjectileFireball.gd` | Standoff 180–220 px, retreats on approach | Fireball: 18 dmg, 240 px/s, 0.5s yellow charge-up tell |

### 2.2 Player Dodge Roll ✅
`Player.gd` — Spacebar: 0.2s dash with iframes, 1.0s cooldown.

### 2.3 Static Baseline Toggle ✅
`DefenseOverlay.gd` — toggle between:
* **Adaptive Closed-Loop (PPO):** live PPO policy adapts difficulty each floor.
* **Static Baseline (Non-Adaptive):** +8% HP/damage per floor — classic roguelike baseline for comparative evaluation.

---

## 3. Work Package 2: Visual Aesthetics & Dungeon Sprites ✅

**Key commits:** `b7dd94f` (Oct 10), `367b803`, `250806e`, `9308f7c`, `8637b03` (Oct 11)

Implemented in `Room.gd`, `Main.gd`, `DamageFloater.gd`, `Player.gd`, `Enemy.gd`:

1. **Sprite Integration ✅** — Authentic 2D pixel-art sprites:
   * `player.png` (armored knight, movement bob, sword flash FX)
   * `enemy_crawler.png` (demonic crawler, carapace animation)
   * `enemy_pyromancer.png` & `projectile_fireball.png`
   * `hazard_spikes.png`, `pickup_potion.png`, `portal_exit.png`
   * Tilemap: `tile_floor_stone.png`, `tile_floor_hazard.png`, `tile_floor_treasure.png`, `tile_floor_exit.png`, `tile_wall_top.png`

2. **Combat Juice ✅**
   * `Main.gd` — trauma screen shake: 0.15s decaying trauma on hit/kill
   * `DamageFloater.gd` — upward tween + scale pop: 🟡 enemy dmg / 🔴 player dmg / 🟢 potion heal

3. **Typography ✅** — `godot_prototype/assets/fonts/`:
   * **Cinzel** — headers, room badges, difficulty score
   * **Inter** — HUD telemetry readouts, damage floaters

---

## 4. Work Package 3: 5-Floor Cold-Start Protocol ✅

**Key commits:** `b7dd94f` (Oct 10), `8637b03` (Oct 11 — "5 level first chnge")

### 4.1 5 Calibration Floors

```text
Floor 1 (Intro)       Floor 2 (Swarm)      Floor 3 (Evasion)    Floor 4 (Crucible)    Floor 5 (Apex)
3R | HP35 | Dmg10  →  4R | HP45 | Dmg14  →  4R | HP55 | Dmg18  →  5R | HP70 | Dmg24  →  5R | HP90 | Dmg30
Spd:85 | Haz:5%        Spd:110 | Haz:15%     Spd:135 | Haz:38%     Spd:155 | Haz:50%     Spd:175 | Haz:65%
```

`DungeonGenerator.gd` + `DifficultyManager.gd` procedurally generate each floor against escalating parameter vectors.

### 4.2 CR₀ Weighted Aggregation
`TelemetryLogger.gd` (`compute_cr0_baseline()`):

$$\vec{w} = [1.0, 1.5, 2.0, 2.5, 3.0],\quad \sum w_i = 10.0$$

$$CR_0 = \frac{\sum w_i S_i}{\sum w_i} \times 40 + \frac{\sum w_i D_i}{\sum w_i} \times 35 + \frac{\sum w_i P_i}{\sum w_i} \times 25 \in [10, 95]$$

### 4.3 Policy Weights — Embedded ✅
`godot_prototype/ai/policy_weights.json` (~111KB) — pure GDScript forward pass in `PPOPolicy.gd`, <0.05ms inference, no external runtime dependency. Two additional weight snapshots: `policy_weights_2.json`, `policy_weights_working.json`.

---

## 5. Work Package 4: FAST CI/CD Pipeline ✅

**Key commits:** `c0d9813` (Oct 14), `b595fd5`, `cf423e0`, `b65f3d1`, `7b2a8d8`, `4e46fbc` (Oct 14–15)

### 5.1 Pipeline Architecture

```
git push → GitHub Actions (ubuntu-latest)
├── ci.yml        → Godot 4.3 Headless solvability + ruff Python lint
│   └── 500 dungeons A* flood-fill → 100% pass = ✔ merge allowed
└── release.yml   → Windows export preset → .exe distributable on tag
```

### 5.2 ci.yml Details
* **Godot binary:** 4.3 stable, SHA-256 verified (fixed `4e46fbc`)
* **Python lint:** ruff 0.4.10 (fixed `b595fd5`, `cf423e0`)
* **Test script:** `tests/ci_solvability_runner.gd` — 500 random-seed dungeons, A* solvability check

---

## 6. Work Package 5: Formal Engineering Documentation ✅

**Key commits:** `1044ee8` (Oct 10), `b7dd94f` (Oct 10)

Compiled as full LaTeX report (`F26_FYP1_Mid_Report_LaTeX_Complete/`, 23 source files):
* **SRS (Gate 2):** FR-01–FR-07, NFR-01–NFR-06
* **SDS (Gate 3):** GDScript inference pipeline, JSON telemetry schema, Godot scene tree architecture
* **Traceability Matrix:** FR-01–FR-07 → GDScript modules → CI solvability test
* **Appendices:** Real commit log (28 commits), test cases, action register, 5 architectural diagrams

---

## 7. Repository Evidence Summary

**28 total commits | 16 GDScript modules | 2 GitHub Actions workflows | 3 PPO policy weight files**

| SHA | Date | Author | Description |
| :--- | :--- | :--- | :--- |
| `4e46fbc` | Oct 15 | Rayan Ahmed | ci: fix Godot 4.3 SHA-256 checksums and export path |
| `7b2a8d8` | Oct 15 | Rayan Ahmed | ci/cd: Apply Claude audit fixes |
| `cb56ca3` | Oct 14 | Rayan Ahmed | fix(ranged): fix projectile spawn, casting trigger, aggro range |
| `35654da` | Oct 14 | Rayan Ahmed | feat(combat): add Ranged Pyromancer, fireball, Player dodge roll |
| `b595fd5` | Oct 14 | Rayan Ahmed | ci: format tests to ruff 0.4.10 rules |
| `cf423e0` | Oct 14 | Rayan Ahmed | ci: fix ruff config, format imports, polish release workflow |
| `b65f3d1` | Oct 14 | Rayan Ahmed | chore: add Windows export preset for CI release build |
| `c0d9813` | Oct 14 | Rayan Ahmed | ci: add complete GitHub Actions CI/CD pipeline for FORGE |
| `367b803` | Oct 11 | Rana Raza Ahmed | taking all5 into account |
| `250806e` | Oct 11 | Rana Raza Ahmed | banda hata wa and fading fix |
| `9308f7c` | Oct 11 | Rana Raza Ahmed | tried improving graphics |
| `8637b03` | Oct 11 | Rana Raza Ahmed | 5 level first chnge |
| `1044ee8` | Oct 10 | Rayan Ahmed | docs: add lean Mid-Evaluation implementation plan and team WBS |
| `b7dd94f` | Oct 10 | Rayan Ahmed | feat: visual assets, combat polish, documentation, and cleanup |
| `2f2c412` | Sep 10 | Rayan Ahmed | Updated proposal document |
| `3f34ad1` | Aug 30 | Rayan Ahmed | Add Godot 4.x procedural multi-room dungeon prototype |

---

## 8. Team Accountability (Actual Delivery)

| Member | Primary Ownership | Actual Deliverables |
| :--- | :--- | :--- |
| **Rayan Ahmed** (23i-0018) | ML & PCG Lead, CI/CD, Docs | `PPOPolicy.gd`, `policy_weights.json` (3 snapshots), `ci.yml`/`release.yml`, SHA-256 fix, SRS/SDS LaTeX compilation, CR₀ math formulation |
| **Rana Raza Ahmed** (23i-0060) | Game Engine & Gameplay Lead | 5-level progression (`8637b03`), graphics polish (`9308f7c`, `367b803`, `250806e`), player/enemy sprite overhaul |
| **Uwaid Munir** (23i-2574) | Telemetry & Evaluation Lead | Co-authored `TelemetryLogger.gd`, JSON schema, `DefenseOverlay.gd` baseline toggle, test cases, SRS/SDS co-author |

---

## 9. Deferred Items Tracker (Gates 3–5)

| Item | Gate | Notes |
| :--- | :--- | :--- |
| Archetypes 3–5 (Brute, Skirmisher, Swarmer) | Gate 3 / Final-1 (Week 14) | 2 of 5 done |
| SQLite Telemetry Migration | Gate 3 / Final-1 (Week 14) | Flat JSON active |
| In-Run Equipment Shop / Forge Embers | Gate 3 / Final-1 (Week 14) | — |
| ML Judge Regressor + TreeSHAP | Gate 4 / Mid-2 (Week 26) | Linear proxy active |
| 10-Participant UAT Study (GEQ + PENS) | Gate 5 / Final-2 (Week 32) | — |
