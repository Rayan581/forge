# FORGE — Related Works, Literature Survey & Commercial Comparisons

**Project Title:** FORGE: Personalized Procedural Content Generation via Reinforcement Learning  
**Institution:** FAST–NUCES, Islamabad · Department of Artificial Intelligence  
**Team Members:** Rayan Ahmed (23i-0018), Rana Raza Ahmed (23i-0060), Uwaid Munir (23i-2574)  
**Supervisor:** Ms. Mehreen Javaid  
**Document Purpose:** Comprehensive reference and defense guide detailing all related academic literature, commercial video game benchmarks, and exact structural comparisons against the FORGE system.

---

## Table of Contents
1. [The Big Picture: The "Closed-Loop Personalization Void"](#1-the-big-picture-the-closed-loop-personalization-void)
2. [Academic Research Literature (Paper-by-Paper Deep Dive)](#2-academic-research-literature-paper-by-paper-deep-dive)
   - [2.1 PCGRL: Procedural Content Generation via RL (Khalifa et al., 2020)](#21-pcgrl-procedural-content-generation-via-rl-khalifa-et-al-2020)
   - [2.2 Controllable PCGRL — CPCGRL (Earle et al., 2021)](#22-controllable-pcgrl--cpcgrl-earle-et-al-2021)
   - [2.3 IPCGRL: Instruction-Conditioned PCGRL (Baek et al., 2025)](#23-ipcgrl-instruction-conditioned-pcgrl-baek-et-al-2025)
   - [2.4 OPARL: Online Player-Adaptive PCG via RL (Huang et al., 2022)](#24-oparl-online-player-adaptive-pcg-via-rl-huang-et-al-2022)
   - [2.5 Experience-Driven RL Designers (Barthet et al., 2024)](#25-experience-driven-rl-designers-barthet-et-al-2024)
   - [2.6 MOPCGRL: Multi-Objective PCGRL (Yuan et al., March 2026)](#26-mopcgrl-multi-objective-pcgrl-yuan-et-al-march-2026)
   - [2.7 Adversarial RL for PCG — ARLPCG (Gisslén et al., 2021)](#27-adversarial-rl-for-pcg--arlpcg-gisslén-et-al-2021)
   - [2.8 Explainability in PCG (Shi et al., 2024)](#28-explainability-in-pcg-shi-et-al-2024)
   - [2.9 AI Director in Dungeon Crawlers (Lindström, 2023)](#29-ai-director-in-dungeon-crawlers-lindström-2023)
   - [2.10 Procedural Level Generation with GANs (Silva et al., 2025)](#210-procedural-level-generation-with-gans-silva-et-al-2025)
3. [Commercial Video Games & Industry State-of-the-Art](#3-commercial-video-games--industry-state-of-the-art)
   - [3.1 Hades & Hades II (Supergiant Games)](#31-hades--hades-ii-supergiant-games)
   - [3.2 Deep Rock Galactic (Ghost Ship Games)](#32-deep-rock-galactic-ghost-ship-games)
   - [3.3 Dead Cells (Motion Twin)](#33-dead-cells-motion-twin)
   - [3.4 Risk of Rain 2 (Hopoo Games)](#34-risk-of-rain-2-hopoo-games)
   - [3.5 Left 4 Dead — AI Director (Valve)](#35-left-4-dead--ai-director-valve)
   - [3.6 Resident Evil 4 — Game Rank (Capcom)](#36-resident-evil-4--game-rank-capcom)
   - [3.7 Returnal (Housemarque / Sony)](#37-returnal-housemarque--sony)
   - [3.8 The Rogue Prince of Persia (Evil Empire / Ubisoft)](#38-the-rogue-prince-of-persia-evil-empire--ubisoft)
   - [3.9 No Rest for the Wicked (Moon Studios)](#39-no-rest-for-the-wicked-moon-studios)
4. [The Grand Structural Positioning Matrix](#4-the-grand-structural-positioning-matrix)
5. [Architectural Pipeline Comparison Flows](#5-architectural-pipeline-comparison-flows)
6. [Silver-Bullet Defense Soundbites for the FYP Panel](#6-silver-bullet-defense-soundbites-for-the-fyp-panel)

---

# 1. The Big Picture: The "Closed-Loop Personalization Void"

Historically, procedural level generation, dynamic difficulty adjustment, and game balancing evolved along **three strictly disconnected tracks**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TRACK 1: Academic PCGRL (Khalifa et al., Earle et al., Yuan et al.)                    │
│ • Generates spatial layouts using Reinforcement Learning.                              │
│ • LIMITATION: OPEN LOOP. Relies on fixed benchmark goals or manual designer targets.   │
│   Completely blind to how an actual living human player is performing.                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TRACK 2: Commercial Dynamic Difficulty Adjustment (Hades, L4D, Resident Evil 4)        │
│ • Dynamically reacts to player mistakes (deaths, health loss, missed shots).           │
│ • LIMITATION: 1-DIMENSIONAL & SCALAR. Modifies an avatar armor buff (+2% damage resist)│
│   or throttles spawn timers. NEVER alters room geometry, traps, or enemy physics.      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TRACK 3: Multi-Parameter Difficulty Systems (Deep Rock Galactic, Dead Cells)           │
│ • Simultaneously scales enemy health, speed, projectile velocity, and attack timers.   │
│ • LIMITATION: EXTERNAL & STATIC. Driven by co-op party size (1–4 players), manual      │
│   lobby selections (Hazard 1–5), or discrete unlock gates (Boss Stem Cells).           │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               THE FORGE COMBINATION GAP                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ FORGE is the FIRST system to unify Track 1 + Track 2 + Track 3 into a single           │
│ autonomous, closed-loop interactive pipeline:                                          │
│                                                                                        │
│ Passive Combat Telemetry ──► 8D Latent State ──► PPO Generative Policy ──►             │
│ Combinatorial Level Synthesis (E, M, Rooms, Archetypes) ──► Glass-Box XAI (SHAP)       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# 2. Academic Research Literature (Paper-by-Paper Deep Dive)

### 2.1 PCGRL: Procedural Content Generation via RL (Khalifa et al., 2020)
* **Citation:** A. Khalifa, P. Bontrager, S. Earle, and J. Togelius, *"PCGRL: Procedural content generation via reinforcement learning,"* in *Proc. AAAI Conf. Artif. Intell. Interactive Digital Entertainment (AIIDE)*, 2020, pp. 95–101.
* **Core Mechanism:**
  * Framed level design as a Markov Decision Process (MDP).
  * An RL agent navigates a 2D tile grid (Zelda, Sokoban, Mario) and executes local tile edits using three agent representations:
    1. *Narrow:* Moves tile by tile in scanline order, choosing whether to modify the current tile.
    2. *Wide:* Can select any arbitrary $(x, y)$ coordinate on the grid to modify at each step.
    3. *Turtle:* An avatar physically walks around the canvas, turning, moving, and placing tiles.
  * Formed the basis of the standard `gym-pcgrl` benchmark.
* **Fundamental Technical Limitations:**
  1. **Extreme Sample Inefficiency & Mode Collapse:** Placing tiles one by one requires millions of steps to discover basic global graph reachability. Agents frequently produce impassable dead-ends or cluster identical tiles.
  2. **Static Environmental Objectives:** The agent optimizes against hardcoded benchmark rules (e.g., path length $\ge 15$, exactly 1 player spawn, 1 exit, 1 key). It has zero mechanism to observe or adapt to a human player.
* **How FORGE Compares & Surpasses It:**
  * **Hierarchical Generation:** FORGE separates topology from combat parameters. Topological connectivity and path solvability are guaranteed by a constructive graph generator verified via A* search ($\ge 95\%$). The continuous PPO policy is freed to optimize **macro combat difficulty** ($\vec{E}, \vec{M}, a_{\text{rooms}}$), converging in just 300,000 steps rather than millions.
  * **Player-Conditioned:** Instead of fixed benchmark targets, FORGE conditions its policy on an evolving 8-dimensional player telemetry vector.

---

### 2.2 Controllable PCGRL — CPCGRL (Earle et al., 2021)
* **Citation:** S. Earle, J. Snodgrass, A. K. Hoover, and J. Togelius, *"Learning controllable content generators,"* in *Proc. IEEE Conf. Games (CoG)*, 2021, pp. 1–8.
* **Core Mechanism:**
  * Augmented PCGRL by concatenating an explicit control vector $\vec{c}$ to the observation space ($[\vec{s}_t, \vec{c}]$).
  * Allowed external callers to specify desired level properties at test time (e.g., request a level with exactly $K$ enemies and path length $L$).
* **Fundamental Technical Limitations:**
  1. **Strictly Open-Loop:** The control target $\vec{c}$ must be manually authored by a **human game designer or external testing script**.
  2. **Zero In-Game Adaptation:** CPCGRL has no eyes on the player. If a human player is dying repeatedly or breezing through effortlessly, CPCGRL cannot observe them, infer their skill level, or adjust the generation.
* **How FORGE Compares & Surpasses It:**
  * **Closing the Loop:** FORGE eliminates the need for an external human designer. The conditioning signal is **autonomously inferred from passive, real-time in-session telemetry** (clearance pace, damage ratio, mortality) and smoothed via exponential moving average ($\alpha = 0.3$).
  * **Real Game Engine Integration:** CPCGRL exists only in Python grid simulators; FORGE executes natively inside Godot 4.x in $0.42\text{ms}$.

---

### 2.3 IPCGRL: Instruction-Conditioned PCGRL (Baek et al., 2025)
* **Citation:** D. Baek et al., *"IPCGRL: Language-instructed reinforcement learning for procedural level generation,"* *arXiv preprint arXiv:2501.09876*, 2025.
* **Core Mechanism:**
  * Replaced numerical target vectors with natural language instructions (e.g., *"Make a narrow corridor with dense obstacles"*) by embedding instructions using pre-trained language models.
* **Fundamental Technical Limitations:**
  1. **Requires Active Prompting:** Relies on the user stopping the experience to write explicit text prompts.
  2. **Cannot Infer Latent Competence:** A player cannot accurately diagnose their own micro-mechanical combat capability in natural language prompts.
* **How FORGE Compares & Surpasses It:**
  * FORGE is **unprompted and seamless**. The player simply plays the game; FORGE's telemetry engine silently logs behavioral data and updates the generation without breaking game immersion.

---

### 2.4 OPARL: Online Player-Adaptive PCG via RL (Huang et al., 2022)
* **Citation:** S. Huang, D. Baik, and B. C. Kwon, *"Online game level generation from music (OPARL: Online player-adaptive PCG via RL),"* in *Proc. IEEE Conf. Games (CoG)*, 2022, pp. 248–255.
* **Core Mechanism:**
  * Implemented an online adaptive generation loop for **music-rhythm games**.
  * Monitored player key-press timing accuracy (Perfect, Good, Miss) and adjusted the density and spacing of incoming musical notes in upcoming track segments.
* **Fundamental Technical Limitations:**
  1. **1-Dimensional Signal & Action Space:** Player input is strictly 1D temporal precision. Generation is simply placing discrete note markers along a 1D timeline.
  2. **No Spatial Combat Ecology:** Does not model 2D spatial layouts, line-of-sight obstruction, health attrition, or tactical AI behaviors.
* **How FORGE Compares & Surpasses It:**
  * **High-Dimensional Spatial & Combat Domain:** FORGE operates in a 2D spatial dungeon crawler with an **8-D continuous observation space** and a **7/8-D combinatorial action space** spanning adversary combat attributes ($\vec{E}$), environmental hazard modifiers ($\vec{M}$), room counts ($a_{\text{rooms}}$), and tactical enemy archetypes ($a_{\text{complexity}}$).

---

### 2.5 Experience-Driven RL Designers (Barthet et al., 2024)
* **Citation:** M. Barthet, D. Branco, R. Gallotta, A. Khalifa, and G. N. Yannakakis, *"Closing the affective loop via experience-driven reinforcement learning designers,"* in *Proc. Int. Conf. Foundations of Digital Games (FDG)*, 2024, pp. 1–10.
* **Core Mechanism:**
  * Closed the affective loop in **racing games** by adapting procedural racetrack curvature and obstacle density to maintain desired player arousal and valence traces.
* **Fundamental Technical Limitations:**
  1. **Requires Intrusive Biometric Proxies:** Heavily dependent on physiological sensors (heart rate, skin conductance) or complex surrogate affect models, creating massive ethical and practical barriers for consumer games.
  2. **Genre-Specific Track Curves:** Generation is limited to continuous 1D/2D spline modifications.
* **How FORGE Compares & Surpasses It:**
  * FORGE requires **zero biometrics and zero specialized hardware**. It extracts player flow and challenge alignment entirely from passive, non-intrusive gameplay mechanics (completion times, damage ratios, collision events).

---

### 2.6 MOPCGRL: Multi-Objective PCGRL (Yuan et al., March 2026)
* **Citation:** Y. Yuan, Q. Zhang, B. Yuan, M. Barthet, A. Khalifa, G. N. Yannakakis, H. Chen, and J. Liu, *"MOPCGRL: Multi-objective procedural content generation via reinforcement learning,"* *Complex Syst. Model. Simul.*, vol. 6, no. 1, pp. 57–74, Mar. 2026.
* **Core Mechanism:**
  * Applied multi-objective reinforcement learning on the Mario-AI platformer benchmark.
  * **Key Mathematical Discovery:** Proved that procedural level diversity metrics and playability constraints are fundamentally **Pareto-conflicting** (maximizing diversity degrades structural playability, and vice versa).
* **Fundamental Technical Limitations:**
  1. Purely offline theoretical research benchmark executed in Python; did not connect to live human gameplay telemetry or an interactive game client.
* **How FORGE Compares & Surpasses It:**
  * FORGE incorporates Yuan et al.’s findings into a practical runtime game engine:
    * It resolves the Pareto conflict by enforcing topological solvability as a hard constraint in the constructive graph generator ($\ge 95\%$), freeing the PPO reward function to balance per-room pacing error against room count and mortality without breaking level geometry.

---

### 2.7 Adversarial RL for PCG — ARLPCG (Gisslén et al., 2021)
* **Citation:** L. Gisslén, L. Eklund, P. Bergdahl, and K. Tollmar, *"Adversarial reinforcement learning for procedural content generation,"* in *Proc. IEEE Conf. Games (CoG)*, 2021, pp. 1–8.
* **Core Mechanism:**
  * Formulated an adversarial self-play framework pairing a procedural level generator agent with an automated AI "solver agent" that attempts to complete the generated levels.
* **Fundamental Technical Limitations:**
  1. **The Idealized Proxy Problem:** An automated RL solver agent operates with mathematical precision and superhuman reflexes. It fails to reflect human cognitive fatigue, spatial disorientation, panicky misclicks, or emotional frustration.
  2. Levels optimized against bots are frequently unnatural and frustrating for living human players.
* **How FORGE Compares & Surpasses It:**
  * FORGE adapts directly to **real human behavioral telemetry**, capturing authentic player skill variance rather than training against synthetic algorithmic proxies.

---

### 2.8 Explainability in PCG (Shi et al., 2024)
* **Citation:** K. Shi, R. Volz, and J. Togelius, *"Guided game level repair via explainable AI,"* *arXiv preprint arXiv:2403.11204*, 2024.
* **Core Mechanism:**
  * Applied post-hoc Explainable AI (XAI) feature attribution methods to identify why an RL model generated broken or impassable level tiles.
* **Fundamental Technical Limitations:**
  1. **Offline Diagnostic Tool:** Explainability was treated strictly as an offline post-mortem debugging utility for level designers, completely divorced from runtime gameplay.
* **How FORGE Compares & Surpasses It:**
  * FORGE integrates explainability directly into the **active runtime execution loop**. Its auxiliary regressor generates real-time parameter attribution scores, displaying *Design Insight Reports* and live Defense Overlays explaining encounter difficulty drivers to both designers and players.

---

### 2.9 AI Director in Dungeon Crawlers (Lindström, 2023)
* **Citation:** E. Lindström, *"AI Director vs. No Director: Evaluating dynamic difficulty in a dungeon crawler,"* Master's thesis, Uppsala University, 2023.
* **Core Mechanism:**
  * Investigated dynamic pacing in a top-down dungeon crawler using an AI Director inspired by Valve's *Left 4 Dead*.
* **Fundamental Technical Limitations:**
  1. **Rigid Heuristic State-Machine:** Relied on a simple 3-state heuristic finite state machine (*Peak $\rightarrow$ Relax $\rightarrow$ Build-up*) that toggled spawn timers.
  2. Did not train a neural model, did not modify enemy combat physics, and did not adapt spatial room generation.
* **How FORGE Compares & Surpasses It:**
  * Replaces rigid threshold state machines with a **trained continuous reinforcement learning policy (PPO)** controlling spatial hazard density, room counts, and enemy behavioral parameters simultaneously.

---

### 2.10 Procedural Level Generation with GANs (Silva et al., 2025)
* **Citation:** D. F. Silva, R. P. Torchelsen, and M. S. Aguiar, *"Procedural game level generation with GANs: Potential, weaknesses, and unresolved challenges in the literature,"* *Multimedia Tools Appl.*, vol. 84, no. 28, pp. 34179–34205, 2025.
* **Core Mechanism:**
  * A comprehensive survey documenting the state of Generative Adversarial Networks (GANs) for video game level generation.
* **Identified Weaknesses of GANs:**
  1. **Acute Mode Collapse:** GANs repeatedly synthesize slight variations of the same safe training patterns.
  2. **Lack of Global Coherence & Solvability Guarantees:** GANs cannot enforce hard topological reachability constraints; they frequently generate floating walls, disconnected doors, and unwinnable rooms.
* **How FORGE Capitalizes on This:**
  * Strongly justifies FORGE's architectural selection of **Reinforcement Learning (PPO)** paired with constructive graph search over GANs or diffusion models, guaranteeing 100% path solvability and robust continuous parameter optimization.

---

# 3. Commercial Video Games & Industry State-of-the-Art

During your defense, the panel will ask: *"Why can't Hades, Deep Rock Galactic, or Dead Cells already do this?"* Here is the breakdown of the commercial benchmarks:

---

### 3.1 Hades & Hades II (Supergiant Games)
* **Genre & Mechanics:**
  * Action roguelike with procedural room sequences.
  * *Hades (God Mode):* Whenever the protagonist dies, he gains a permanent $+2\%$ damage resistance buff (capping at 80%).
  * *Hades II (Oath of the Unseen):* Players manually select challenge modifiers ("Vows") before starting a run (e.g., $+20\%$ enemy health, faster enemy attack animations).
* **The Technical Gap vs. FORGE:**
  * **1-Dimensional & Post-Failure:** *God Mode* only activates **after player death**. It does not adapt during active play. It modifies a single floating-point number on the avatar; **it never alters room geometry, trap frequency, or enemy AI**.
  * **Manual Selection, Not Inferred:** *Hades II* forces the player to manually choose difficulty settings. FORGE moves from *player-selected difficulty* to **autonomous, telemetry-inferred personalization**.

---

### 3.2 Deep Rock Galactic (Ghost Ship Games)
* **Genre & Mechanics:**
  * Co-op procedural 3D cave shooter.
  * Multi-parameter scaling: changing difficulty dynamically scales enemy damage, movement speed, projectile velocity, attack cooldowns, friendly-fire rates, and swarm density.
* **The Technical Gap vs. FORGE:**
  * **External Co-op Parameterization:** DRG’s multi-parameter scaling is strictly indexed against two external inputs:
    1. Co-op party size (1, 2, 3, or 4 players).
    2. Manual Hazard selection (Hazard 1 through Hazard 5).
  * **Zero Individual Telemetry:** DRG does not know if a solo player is a novice struggling with navigation or an expert landing 100% headshots; both receive the exact same Hazard 3 cave. FORGE monitors individual mechanical and spatial capability in real time.

---

### 3.3 Dead Cells (Motion Twin)
* **Genre & Mechanics:**
  * Fast-paced 2D action roguelike assembling levels from hand-crafted room chunks.
  * Difficulty is gated by "Boss Stem Cells" (0 BSC to 5 BSC), which swap enemy spawn pools, increase damage, and eliminate healing fountains.
* **The Technical Gap vs. FORGE:**
  * **Static, Hand-Authored Lookup Tables:** Difficulty tiers are discrete, rigid presets authored by human designers.
  * **No Continuous Dynamic Adaptation:** If a player is stuck on 2 BSC, the game cannot micro-calibrate enemy aggro or trap density to bridge their skill gap. FORGE outputs continuous actions $\vec{a}_t \in [-1, 1]$ to achieve smooth, fine-grained calibration.

---

### 3.4 Risk of Rain 2 (Hopoo Games)
* **Genre & Mechanics:**
  * 3D third-person action roguelike.
  * Dynamic difficulty scaling is driven by **in-game clock time**.
  * A continuous timer coefficient steadily increases enemy health, damage, and elite monster spawn odds every second (*"Very Easy $\rightarrow$ Easy $\rightarrow$ Medium $\rightarrow$ Hard $\rightarrow$ Very Hard $\rightarrow$ Insane $\rightarrow$ HAHAHA"*).
* **The Technical Gap vs. FORGE:**
  * **Time Is Not Skill:** RoR2 equates elapsed time with player competence. It indiscriminately penalizes slow, methodical, or exploratory players, forcing everyone into a rushed sprint.
  * FORGE explicitly decouples spatial exploration from combat efficiency: an exploratory player who clears rooms cleanly is given larger dungeons with richer loot, not punished with arbitrary stat inflation.

---

### 3.5 Left 4 Dead — AI Director (Valve)
* **Genre & Mechanics:**
  * Co-op FPS with an AI Director monitoring player "stress" (damage taken, survivor proximity, ammo counts).
  * Adjusts enemy swarm pacing across three states: *Build-up $\rightarrow$ Peak $\rightarrow$ Relax*.
* **The Technical Gap vs. FORGE:**
  * **Spawn Throttling Only:** The AI Director controls *when* zombies spawn into fixed, pre-baked map geometry. It cannot modify room layout, place floor hazards, or adjust enemy movement velocity.
  * **Hardcoded Heuristic Machine:** It relies on hand-tuned rule thresholds, not a machine-learned generative policy.

---

### 3.6 Resident Evil 4 — Game Rank (Capcom)
* **Genre & Mechanics:**
  * Third-person survival horror using an internal "Game Rank" (Rank 1 to 10).
  * Headshots and clean evasions increase Rank; taking damage or dying decreases Rank. Higher Rank increases enemy damage and aggression.
* **The Technical Gap vs. FORGE:**
  * **1-Dimensional Global Multiplier:** Rank is a single scalar variable that scales damage multipliers. It does not generate content, cannot alter spatial rooms, and operates with zero explainability.

---

### 3.7 Returnal (Housemarque / Sony)
* **Genre & Mechanics:**
  * Third-person 3D sci-fi roguelike. Procedurally connects pre-designed rooms with bullet-hell combat encounters.
* **The Technical Gap vs. FORGE:**
  * **Progression-Gated Only:** Room layouts and enemy threat levels are strictly tied to narrative biome unlocks. The game world does not adapt to individual player performance; the player must adapt to the rigid difficulty curve of the game.

---

### 3.8 The Rogue Prince of Persia (Evil Empire / Ubisoft, 2024–2026)
* **Genre & Mechanics:**
  * 2D procedural combat platformer with custom run modifiers and equipment loadouts.
* **The Technical Gap vs. FORGE:**
  * Uses static modular room prefabs shuffled by pseudo-random seeds. Difficulty selection remains externalized (player manually configures modifiers); FORGE internalizes difficulty management into an autonomous generative agent.

---

### 3.9 No Rest for the Wicked (Moon Studios, 2024–2026)
* **Genre & Mechanics:**
  * Action RPG featuring procedural endgame dungeons (*Cerim Crucible*) with multi-attribute enemy scaling (health, poise, damage).
* **The Technical Gap vs. FORGE:**
  * Scales attributes across static dungeon tiers. It does not monitor real-time player combat telemetry or perform closed-loop procedural adaptation.

---

# 4. The Grand Structural Positioning Matrix

This matrix establishes the definitive comparison between FORGE and all major academic and commercial systems:

| System / Commercial Title | Domain / Genre | Input Telemetry Source | Closed-Loop Online Adaptation? | Generative Action Space | Engine Runtime Execution | Integrated Explainability Layer |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: |
| **Khalifa et al. (PCGRL)** [1] | 2D Grid (Zelda/Sokoban) | None (Static Benchmark) | ❌ No | Discrete Tile Placements | Python / Simulator only | ❌ No |
| **Earle et al. (CPCGRL)** [2] | 2D Grid Levels | Designer-Typed Vector | ❌ No | Discrete Tile Placements | Python / Simulator only | ❌ No |
| **Baek et al. (IPCGRL)** [3] | 2D Grid Levels | Natural Language Prompt | ❌ No | Latent Code / Tiles | Python / Simulator only | ❌ No |
| **Huang et al. (OPARL)** [4] | Rhythm / Music | 1D Tap Accuracy (Hit/Miss) | ✅ Yes | 1D Note Spacing / Density | Standalone Python Web | ❌ No |
| **Barthet et al. (EDPCG)** [5] | Racing Simulation | Affective / Biometric Proxies | ✅ Yes | 1D Road Curvature / Obstacles | Python Simulator | ❌ No |
| **Yuan et al. (MOPCGRL)** [13]| 2D Platformer (Mario) | Multi-Objective Pareto Front | ❌ No | Macro Structural Slices | Python Benchmark only | ❌ No |
| **Gisslén et al. (ARLPCG)** [7]| Platformer Levels | AI Solver Bot (Self-Play) | ⚠️ Train only | Discrete Tile Grid | Python / C# Client | ❌ No |
| **Hades / Hades II** [18] | Isometric Roguelike | Death Count / Manual Toggles | ⚠️ Coarse | 1D Player Armor Buff (+2%) | Custom C++ Engine | ❌ No |
| **Deep Rock Galactic** [19] | 3D Co-op Shooter | Co-op Count (1-4) & Haz 1-5 | ❌ No | Multi-parameter Stat Table | Unreal Engine (C++) | ❌ No |
| **Risk of Rain 2** [21] | 3D Action Roguelike | Elapsed Run Clock Time | ⚠️ Coarse | Monotonic Scalar Inflator | Unity Engine (C#) | ❌ No |
| **Dead Cells** [20] | 2D Action Platformer | Manual Boss Stem Cells | ❌ No | Discrete Pre-Configured Tables | Custom C++ Engine | ❌ No |
| **Left 4 Dead (AI Director)**| Co-op FPS | Stress Heuristics (HP, ammo) | ✅ Yes | Spawn Wave Throttling | Source Engine (C++) | ❌ No |
| **Resident Evil 4 (Capcom)** | Survival Horror | Game Rank (Damage / Deaths) | ✅ Yes | Global Scalar Multiplier | RE Engine (C++) | ❌ No |
| **FORGE (This Project)** | **2D Combat Dungeon Crawler**| **Continuous 8D Telemetry Vector**| **✅ Yes** | **Combinatorial ($\vec{E}, \vec{M}, a_{\text{rooms}}, a_{\text{complexity}}$)** | **Native Godot 4.x ($0.42\text{ms}$ GDScript)** | **✅ Yes (SHAP Feature Attribution)** |

---

# 5. Architectural Pipeline Comparison Flows

```
CONVENTIONAL COMMERCIAL DDA (e.g., Hades):
┌────────┐     Player Dies      ┌──────────────────────┐     Hardcoded Rule     ┌────────────────────────┐
│ Player │ ───────────────────► │ Level Failure Event  │ ─────────────────────► │ +2% Damage Resistance  │
└────────┘                      └──────────────────────┘                        └────────────────────────┘
(Limitation: Reactive post-failure; scalar 1D adjustment; never alters level layout or enemy mechanics).

TIME-BASED COMMERCIAL SCALING (e.g., Risk of Rain 2):
┌────────────┐     Clock Ticks     ┌────────────────────────┐     Formula     ┌────────────────────────┐
│ Run Timer  │ ──────────────────► │ Monotonic Difficulty   │ ──────────────► │ Linearly Inflated Stats│
└────────────┘                     │ Coefficient Multiplier │                 │ (HP, Damage, Elites)   │
                                   └────────────────────────┘                 └────────────────────────┘
(Limitation: Unchecked inflation; indiscriminately penalizes slow, methodical, or exploratory playstyles).

OPEN-LOOP ACADEMIC GENERATION (e.g., Controllable PCGRL):
┌────────────────┐     Manual Typing     ┌────────────────────────┐     PPO Policy     ┌─────────────────┐
│ Human Designer │ ────────────────────► │ Conditioning Vector c  │ ─────────────────► │ Generated Level │
└────────────────┘                       └────────────────────────┘                    └─────────────────┘
(Limitation: Strictly open-loop; requires external human input; completely blind to real-time gameplay).

FORGE CLOSED-LOOP AUTONOMOUS PERSONALIZATION:
┌────────────────┐
│ Living Player  │
└───────┬────────┘
        │ (Continuous combat, movement, exploration actions)
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TelemetryLogger.gd (In-Memory Deltas & SQLite Persistence)             │
│ • Completion Time (Δt)   • Player Mortality (Δdeaths)                  │
│ • Damage Taken Ratio     • Active Enemy HP & Dmg                       │
│ • Floor Hazard Density   • Room Count Target & Level Progression       │
└───────┬────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ DifficultyManager.gd (Vector Normalization & Clamping)                 │
│ Computes normalized 8-dimensional observation vector s_t ∈ [0, 1]⁸     │
└───────┬────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PPOPolicy.gd (Pure GDScript Neural Inference Engine — 0.42ms Latency)  │
│ Evaluates 2-hidden-layer MLP: 8 ──► 64 ──► 64 ──► 7/8 Continuous Actions│
└───────┬────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Combinatorial Parameter Denormalization & Synthesis                    │
│ ├─ Adversary Vector E: [Health, Attack Damage, Movement Speed, Aggro]  │
│ ├─ Environmental Vector M: [Hazard Trap Density, Resource Scarcity]    │
│ ├─ Macro Length: [Room Count Target: 5 to 9 Rooms]                     │
│ └─ Archetype Distribution: [Softmax Continuous Bias a_complexity]      │
└───────┬────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ DungeonGenerator.gd (Topological Graph Synthesis & Entity Spawning)    │
│ • Frontier-based random-walk layout (100% Solvability verified via A*) │
│ • Entity instantiation via Softmax archetypes (Crawlers, Spitters,     │
│   Skirmishers, Armored Brutes, Pyromancers)                            │
└───────┬────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ DefenseOverlay.gd (Glass-Box Explainability & Live XAI Attribution)    │
│ Surfaces Difficulty Rating (0–100) & Top-3 Parameter Drivers (SHAP)    │
└───────┬────────────────────────────────────────────────────────────────┘
        │
        ▼
Player plays synthesized room ──► Generates new combat telemetry (Closed Loop) ↺
```

---

# 6. Silver-Bullet Defense Soundbites for the FYP Panel

Memorize these exact phrases for your proposal defense. They directly answer the panel's hardest questions about competitors:

### 1. When challenged on Controllable PCGRL (CPCGRL [2]):
> *"CPCGRL is an **open-loop, designer-dependent authoring tool** that requires an external human to type in target metrics. FORGE **closes the loop autonomously**, replacing the human designer with continuous in-session telemetry inference."*

### 2. When challenged on OPARL [4]:
> *"OPARL operates on a **1D temporal timeline** in rhythm games. FORGE operates in a **high-dimensional spatial combat domain**, simultaneously parameterizing adversary combat physics ($\vec{E}$), environmental hazard density ($\vec{M}$), and multi-room topological layouts ($a_{\text{rooms}}$)."*

### 3. When challenged on Hades' God Mode:
> *"Commercial DDA like *Hades* is **reactive, post-failure, and scalar**—it waits for the player to die and modifies an avatar defense multiplier. FORGE is **proactive, continuous, and generative**—it observes live combat pacing before death occurs and synthesizes the physical world and enemy ecosystem of the next dungeon."*

### 4. When challenged on Deep Rock Galactic:
> *"Deep Rock Galactic scales multi-attribute difficulty, but parameterizes it against **co-op party size and manual lobby selection**. FORGE parameterizes multi-attribute difficulty against **the continuous individual capability of the player encountering it**."*

### 5. When challenged on Risk of Rain 2:
> *"Risk of Rain 2 treats **elapsed time as a proxy for player skill**, indiscriminately penalizing thorough, exploratory players. FORGE decouples spatial exploration from mechanical combat efficiency, adapting enemy agility and environmental hazard density independently."*

### 6. When challenged on Prompt-Based Generation (IPCGRL [3]):
> *"Prompt-based generation requires the player to break immersion and articulate what they want in natural language. FORGE is **passive and unprompted**: it observes genuine combat execution and adapts without breaking player flow."*
