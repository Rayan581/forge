# FORGE: Personalized Procedural Content Generation via Reinforcement Learning

## Player-Conditioned Adaptive Dungeon Generation

**Subtitle:** Player-telemetry-inferred, structured difficulty conditioning for combat dungeon crawlers — positioned against closely related closed-loop PCGRL systems

---

| Project Metadata | Specification |
| :--- | :--- |
| **Institution** | FAST–NUCES, Islamabad · Department of Artificial Intelligence |
| **Project Title** | FORGE: Personalized Procedural Content Generation via Reinforcement Learning |
| **Stream** | Stream A — Research-Derived (FAST FYP Guide §1.1) |
| **Team Members** | Member A, Member B, Member C |
| **Supervisor** | Project Supervisor |
| **Project Horizon** | 2 Semesters (FYP-1: Final-1 / FYP-2: Final-2) |
| **Date** | August 2026 |

---

## Table of Contents

- [1. Project Overview & Motivation](#1-project-overview--motivation)
  - [1.1 Abstract](#11-abstract)
  - [1.2 Motivation & Industry Context](#12-motivation--industry-context)
  - [1.3 Problem Statement](#13-problem-statement)
  - [1.4 Contribution Statement & Novelty Boundary](#14-contribution-statement--novelty-boundary)
  - [1.5 Target Audience & Stakeholders](#15-target-audience--stakeholders)
  - [1.6 Thematic & UN SDG Alignment](#16-thematic--un-sdg-alignment)
- [2. Literature Review / Survey & Market Analysis](#2-literature-review--survey--market-analysis)
  - [2.1 Survey Research & PCGRL Landscape](#21-survey-research--pcgrl-landscape)
  - [2.2 Synthesis of Recent Research Extensions](#22-synthesis-of-recent-research-extensions)
  - [2.3 Related-Work Structural Positioning Matrix](#23-related-work-structural-positioning-matrix)
  - [2.4 Concrete Research Gap Addressed by FORGE](#24-concrete-research-gap-addressed-by-forge)
  - [2.5 Market Analysis & Commercial State-of-the-Art](#25-market-analysis--commercial-state-of-the-art)
- [3. High-Level Goals (Tabular Format)](#3-high-level-goals-tabular-format)
  - [3.1 Strategic Goal Matrix](#31-strategic-goal-matrix)
  - [3.2 Research & Engineering Objectives](#32-research--engineering-objectives)
- [4. Project Scope (Fixed — Complex Computing Problem)](#4-project-scope-fixed--complex-computing-problem)
  - [4.1 Complex Computing Problem (CCP) Justification](#41-complex-computing-problem-ccp-justification)
  - [4.2 Core Scope Commitments (In-Scope Deliverables)](#42-core-scope-commitments-in-scope-deliverables)
  - [4.3 Documented Optional Extensions](#43-documented-optional-extensions)
  - [4.4 Scope Baselines & Change Control Process](#44-scope-baselines--change-control-process)
- [5. Proposed Solution & System Architecture](#5-proposed-solution--system-architecture)
  - [5.1 Game Format & Operational Mechanics](#51-game-format--operational-mechanics)
  - [5.2 Combinatorial Difficulty Model (Difficulty ≠ Enemy Count)](#52-combinatorial-difficulty-model-difficulty--enemy-count)
  - [5.3 End-to-End Closed-Loop System Architecture](#53-end-to-end-closed-loop-system-architecture)
  - [5.4 Cold-Start Profiling & The Placement Phase](#54-cold-start-profiling--the-placement-phase)
  - [5.5 Reinforcement Learning Methodology](#55-reinforcement-learning-methodology)
  - [5.6 Deployment Architecture & Non-Functional Design](#56-deployment-architecture--non-functional-design)
  - [5.7 Proposal-Stage Proof of Concept (POC) & Technical Spike](#57-proposal-stage-proof-of-concept-poc--technical-spike)
- [6. Timeline, Evaluation & Iterations](#6-timeline-evaluation--iterations)
  - [6.1 Five-Gate Evaluation Trajectory](#61-five-gate-evaluation-trajectory)
  - [6.2 Milestone Schedule & Two-Semester Gantt Plan](#62-milestone-schedule--two-semester-gantt-plan)
  - [6.3 Verification, Testing & Evaluation Framework](#63-verification-testing--evaluation-framework)
  - [6.4 User Acceptance Testing (UAT) Protocol](#64-user-acceptance-testing-uat-protocol)
  - [6.5 Provisional Acceptance Criteria](#65-provisional-acceptance-criteria)
  - [6.6 Risk Management & Mitigation Matrix](#66-risk-management--mitigation-matrix)
- [7. Work Breakdown Structure (WBS)](#7-work-breakdown-structure-wbs)
  - [7.1 Team Member Allocation Matrix](#71-team-member-allocation-matrix)
  - [7.2 Individual Accountability & Removal Test](#72-individual-accountability--removal-test)
- [8. Tools, Technology & External Components](#8-tools-technology--external-components)
  - [8.1 Technology Stack](#81-technology-stack)
  - [8.2 External Component Classification](#82-external-component-classification)
  - [8.3 AI-Assisted Development Framework & Usage Logging](#83-ai-assisted-development-framework--usage-logging)
  - [8.4 FAST FYP Guide Alignment Checklist](#84-fast-fyp-guide-alignment-checklist)
- [9. References & Citations (IEEE Style)](#9-references--citations-ieee-style)

---

## 1. Project Overview & Motivation

### 1.1 Abstract
Procedural Content Generation (PCG) has evolved from rule-based grammars and search-based heuristics to learned, reinforcement learning-driven generation (PCGRL) [1]. While controllable PCGRL methods condition level generation on structured targets [2], [3] and adaptive systems close the loop using real-time telemetry [4], [5], no existing framework connects continuous, unprompted player behavioral profiling directly to a multi-attribute combat difficulty generator paired with an explainability layer. 

FORGE addresses this gap in the context of top-down 2D dungeon crawlers built in the Godot engine. By continuously updating a player-preference embedding from raw session telemetry (rather than requiring hand-authored target vectors), FORGE conditions a Proximal Policy Optimization (PPO) [11] policy that operates on a structured, combinatorial action space comprising enemy parameters (health, damage, speed, aggro radius) and environmental modifiers (hazard density, resource scarcity). The system integrates a learned auxiliary difficulty predictor that serves both as an adaptive reward-fit term and as a glass-box explainability engine, generating a Design Insight Report via feature attribution. Evaluated against constructive rule-based baselines (BSP) and unconditioned PPO generators, FORGE establishes a reproducible, research-grounded approach to personalized game generation.

### 1.2 Motivation & Industry Context
Modern video games increasingly depend on procedural generation to sustain replayability, lower production costs, and dynamically pace challenges. However, the vast majority of deployed and literature-standard PCGRL implementations (including benchmark environments built upon `gym-pcgrl` [10]) generate content tailored to an *average* player profile. 

In actual play, human players exhibit wide distributions of mechanical skill, spatial exploration habits, risk tolerance, and combat pacing. Content balanced for a statistical mean inevitably under-challenges experienced players (inducing boredom) and over-penalizes novice players (inducing anxiety and churn) [12]. Recent studies in multi-objective PCGRL [13] reveal that game generation metrics naturally conflict, while empirical analyses of player perceptions [15] demonstrate that the perceived authenticity and personalization of procedural generation profoundly influences user immersion. Concurrently, generative neural models such as GANs suffer from acute mode collapse and lack formal playability guarantees [16]. These challenges establish the critical necessity for an online, reinforcement-learning-based generator capable of balancing conflicting multi-dimensional constraints while adapting specifically to the player encountering them.

### 1.3 Problem Statement
The objective of FORGE is to design, implement, and rigorously evaluate an online reinforcement-learning-based procedural content generator for a room-based 2D combat dungeon crawler that:
1. Continuously infers a multi-dimensional player behavioral profile from passive in-session telemetry without requiring explicit player questionnaires or designer-assigned target vectors;
2. Conditions a generative PPO policy upon this evolving profile to dynamically synthesize dungeons calibrated to individual player capability;
3. Formulates difficulty as a structured parameter space spanning continuous enemy behavioral parameters and environmental constraints rather than a simplistic scalar difficulty multiplier; and
4. Implements an explainability engine that extracts and presents the specific environmental and adversary attributes responsible for driving the predicted difficulty of any generated instance.

### 1.4 Contribution Statement & Novelty Boundary

#### The One-Sentence Contribution Formula (FAST FYP Guide §4)
> **Existing PCGRL approaches** generate levels conditioned on designer-specified targets (CPCGRL [2]) or close the loop in non-combat domains (OPARL [4], EDRL [5]), **but remain incapable of autonomously inferring multi-attribute combat challenge profiles directly from raw player telemetry.** We will contribute **FORGE: an end-to-end closed-loop pipeline that infers player profiles from live telemetry, conditions a PPO policy over a combinatorial enemy/environment parameter space in a Godot dungeon crawler, and surfaces difficulty attribution through a learned regressor**, and evaluate it against **rule-based BSP and unconditioned PPO baselines across solvability, difficulty-fit error, layout diversity, and player-reported engagement metrics** [13]–[15].

#### What Is and Isn't New — Stated Plainly
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ WHAT IS NOT CLAIMED AS NEW (ESTABLISHED PRIOR ART)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Level generation framed as an MDP solved via RL (PCGRL [1]).              │
│ • Conditioning an RL generator on multi-dimensional vectors (CPCGRL [2]).    │
│ • Closing the telemetry-to-generation loop in rhythm/racing games [4], [5]. │
│ • Multi-objective Pareto formulations for game content metrics [13].        │
│ • Post-hoc explainable AI techniques applied to game levels [8].            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ WHAT IS CLAIMED AS NEW (FORGE'S DISTINCT CONTRIBUTION)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Autonomous inference of conditioning signals from raw combat telemetry.   │
│ • Structured, combinatorial difficulty spanning enemy stats + hazards.      │
│ • Integration of a dual-purpose difficulty predictor & explainability layer.│
│ • Closed-loop personalization validated within a deployable Godot client.   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.5 Target Audience & Stakeholders
FORGE explicitly identifies two user groups:
- **Primary Stakeholders (End-User Players):** Players of 2D action-adventure and roguelike dungeon crawlers across diverse skill tiers (Novice, Intermediate, Hardcore/Expert). The system autonomously personalizes encounter difficulty to preserve psychological flow [12].
- **Secondary Stakeholders (Game & Level Designers):** Technical game designers who inspect the generated *Design Insight Reports* to audit why specific encounters are ranked at given difficulty levels, transforming black-box RL outputs into actionable design intelligence.

### 1.6 Thematic & UN SDG Alignment
- **UN SDG 3 (Good Health and Well-Being):** Mitigates player anxiety, frustration, and gaming-induced stress by avoiding persistent difficulty mismatches and dynamic difficulty spikes.
- **UN SDG 9 (Industry, Innovation, and Infrastructure):** Contributes an open, modular, and explainable algorithmic pipeline for intelligent software generation, advancing adaptive AI architectures in interactive simulations.

*(Note: Per FAST FYP Guide §1.3, this thematic alignment establishes broader context and is not claimed as a substitute for technical CCP depth).*

---

## 2. Literature Review / Survey & Market Analysis

### 2.1 Survey Research & PCGRL Landscape
Procedural Content Generation historically utilized constructive algorithms (e.g., Binary Space Partitioning, cellular automata) and search-based optimization (SBPCG) [6]. While computationally predictable, constructive methods cannot adapt to player behavior, and search-based methods are frequently too computationally prohibitive for real-time inference.

- **PCGRL Foundations:** Khalifa et al. (2020) [1] transformed level design into a Markov Decision Process (MDP), utilizing deep reinforcement learning agents that traverse a tile grid and execute local edits. The reference benchmark `gym-pcgrl` [10] established the Zelda-style 2D grid paradigm upon which FORGE's environment layer is grounded.
- **Controllability in PCGRL:** Earle et al. (2021) [2] introduced Controllable PCGRL (CPCGRL), conditioning policy networks on explicit metric targets (e.g., target path length, enemy count). Baek et al. (2025) [3] proposed IPCGRL, utilizing natural language prompts to guide generation. Crucially, both CPCGRL and IPCGRL rely on *external callers* (a human designer or fixed test script) to prescribe the target conditioning vector.
- **Closed-Loop Adaptive PCG:** Huang et al. (2022) [4] developed OPARL (Online Player-Adaptive PCG via RL), which reads player input in a music-rhythm game and adapts subsequent level segments. Barthet et al. (2024) [5] demonstrated experience-driven RL generation in racing games by targeting desired physiological/affective traces. While pioneering, neither system addresses combat-oriented action games, nor do they operate across multi-attribute combinatorial spaces.
- **Adversarial & Self-Play Generators:** Gisslén et al. (2021) [7] formulated ARLPCG, pairing a generator network with a self-play solver agent. While ARLPCG eliminates the need for human training data, solver agents act as idealized proxies that fail to mirror human cognitive variance, spatial exploration styles, or fatigue.
- **Explainability in PCG:** Recent investigations into Explainable AI for PCG (e.g., Guided Game Level Repair [8]) demonstrate the utility of feature attribution for level validation, but treat explainability as an offline post-processing diagnostic rather than an integrated component of an active generation pipeline.

### 2.2 Synthesis of Recent Research Extensions
To ensure rigorous positioning against cutting-edge literature, FORGE incorporates insights from four primary reference works:

1. **MOPCGRL (Yuan et al., March 2026) [13]:** Proposes multi-objective reinforcement learning to navigate conflicting diversity metrics with playability constraints on the Mario-AI benchmark. MOPCGRL proves mathematically that procedural diversity metrics (e.g., density vs. structural variation) are non-trivially Pareto-conflicting. FORGE leverages this finding to formalize its multi-objective reward formulation (§5.5.2), resolving trade-offs between solvability, diversity, and difficulty-fit.
2. **Measuring Diversity of Game Scenarios (IEEE, 2025) [14]:** Establishes formalized distance metrics across functional, structural, and behavioral gameplay facets. FORGE utilizes these formulations to construct its mathematical diversity reward penalty and validate layout variance across repeated play sessions.
3. **Playing the Imitation Game: Player Experience Under Perceived Generation (ACM, 2025) [15]:** Demonstrates that player satisfaction is governed by psychological perception and perceived intentionality rather than raw mathematical complexity alone. This study reinforces FORGE's decision to deploy user-facing explainability and execute comprehensive User Acceptance Testing (§6.4) alongside automated metrics.
4. **Procedural Game Level Generation with GANs: Weaknesses & Challenges (Springer, 2025) [16]:** A state-of-the-art survey documenting why deep generative adversarial networks struggle in level generation: mode collapse, lack of global structural coherence, and inability to enforce hard topological solvability constraints. This analysis strongly justifies FORGE's architectural selection of RL (PPO) over GANs for mission-critical game topologies.

### 2.3 Related-Work Structural Positioning Matrix

| System | Structured Multi-Attribute Target Space | Conditioning Inferred from Live Telemetry | Closed-Loop Online Adaptation | Domain / Genre | Integrated Explainability Layer |
| :--- | :---: | :---: | :---: | :--- | :---: |
| **Controllable PCGRL / IPCGRL** [2], [3] | **Yes** | **No** (Designer/Prompt Set) | **No** | 2D/3D Platformer, Sokoban | **No** |
| **OPARL** [4] | **Partial** (Scalar/Low-Dim) | **Yes** | **Yes** | Rhythm / Music Segments | **No** |
| **Experience-Driven RL** [5] | **Partial** (Affect Trace) | **Yes** (Affective Proxy) | **Yes** | Racing Simulations | **No** |
| **MOPCGRL** [13] | **Yes** (Pareto Front) | **No** (Objective Space) | **No** | Mario-AI Benchmark | **No** |
| **Adversarial PCG (ARLPCG)** [7] | **No** (Single Difficulty Axis) | **No** (Solver Agent Proxy) | **Yes** (During Training) | Platformer Environments | **No** |
| **Commercial DDA (L4D, RE4)** | **Partial** (Spawn Throttling) | **Yes** (Hardcoded Rules) | **Yes** | FPS / Survival Horror | **No** |
| **FORGE (This Project)** | **Yes** (Enemy + Environment) | **Yes** (Rolling Session Vectors) | **Yes** | **Combat Dungeon Crawler** | **Yes** (SHAP / Feature Attribution) |

### 2.4 Concrete Research Gap Addressed by FORGE
No published system in the PCGRL literature simultaneously synthesizes:
1. A continuous, automated telemetry-to-profile inference pipeline that bypasses manual target specification;
2. A combinatorial combat difficulty formulation incorporating independent enemy attributes and environmental hazards;
3. An active deployment in a real-time 2D combat dungeon crawler; and
4. An integrated difficulty predictor that provides design-level explainability.

### 2.5 Market Analysis & Commercial State-of-the-Art
- **Valve's Left 4 Dead (AI Director):** Utilizes hardcoded rule trees monitoring player "emotional intensity" (damage taken, survivor clustering) to dynamically throttle enemy spawn surges. It does not alter level layout, geometry, or adversary mechanics, nor does it learn over time.
- **Capcom's Resident Evil 4 (Adaptive Difficulty Rank):** Implements an internal scalar game rank (1 to 10) adjusted per death or successful headshot, scaling enemy damage and reaction speed via linear lookup tables.
- **Supergiant Games' Hades (God Mode):** Provides a static, manually activated handicap system that increases damage resistance by a fixed +2% per subsequent death.

**Commercial Limitation:** All existing commercial Dynamic Difficulty Adjustment (DDA) engines rely on simplistic scalar adjustments or rule-based heuristics that tune superficial spawn rates. None utilize reinforcement learning to synthesize bespoke spatial environments and enemy parameter vectors adapted to individual player telemetry.

---

## 3. High-Level Goals (Tabular Format)

### 3.1 Strategic Goal Matrix

| Goal Category | Description & Academic / Practical Basis | Concrete Key Deliverable |
| :--- | :--- | :--- |
| **Research** | Grounded in academic literature (PCGRL [1], CPCGRL [2], MOPCGRL [13]); models multi-attribute difficulty trade-offs under Seoul Accord complex computing standards. | Exhaustive Literature Review deliverable (Final-1); validated theoretical formulation of combat difficulty spaces. |
| **Development** | Bridges research into real-time interactive game systems; establishes a robust client-server architecture between Godot 4.x and a Python PPO inference server. | Fully operational Godot dungeon crawler integrated with local FastAPI RL service and SQLite telemetry pipeline. |
| **Novelty** | Pioneers telemetry-inferred multi-attribute difficulty conditioning combined with dual-purpose difficulty prediction and explainability. | Trained player-conditioned PPO agent; feature attribution engine generating automated *Design Insight Reports*. |
| **Product Delivery** | Translates research prototypes into an installable, standalone product capable of execution outside development workstations. | Packaged Windows executable with documented installation scripts, reproducible seeds, and sub-2s generation latency. |

### 3.2 Research & Engineering Objectives
1. **Solvability Assurance:** Achieve ≥ 95% automated solvability rate across generated dungeon instances using A* pathfinding and reachability graphs.
2. **Predictive Alignment:** Train an auxiliary difficulty regressor achieving a Mean Absolute Error (MAE) within ±15% of empirical player challenge ratings.
3. **Responsive Personalization:** Demonstrate statistically significant behavioral adaptation in generated levels within 3 to 5 post-placement play sessions.
4. **Explainability Transparency:** Extract and render normalized feature-importance rankings for every generated layout to explain model reasoning to designers.

---

## 4. Project Scope (Fixed — Complex Computing Problem)

### 4.1 Complex Computing Problem (CCP) Justification
FORGE is rigorously formulated to satisfy the criteria of a **Complex Computing Problem (CCP)** under the **Seoul Accord** guidelines mandated by the FAST School of Computing.

```
                  ┌──────────────────────────────────────────────┐
                  │    SEOUL ACCORD COMPLEX COMPUTING PROBLEM    │
                  └──────────────────────┬───────────────────────┘
                                         │
     ┌──────────────────┬────────────────┼─────────────────┬──────────────────┐
     ▼                  ▼                ▼                 ▼                  ▼
1. Depth of       2. Conflicting   3. No Obvious     4. Unfamiliar      5. Beyond
   Knowledge         Requirements     Solution          Issues             Standard
   (RL+PCG+GameDesign)(Solvability vs (No closed-form   (Emergent enemy    (Bypasses fixed
    Multi-Attribute)  Personalization) formula exists)   x hazard physics)  CRUD / heuristics)
```

#### Detailed Seoul Accord Characteristic Mapping (7 Claimed):

1. **Depth of Knowledge:** Requires multi-disciplinary mastery across deep reinforcement learning (PPO optimization, policy conditioning), applied machine learning (auxiliary regression, permutation importance), discrete algorithmic graph search (A* pathfinding, reachability graphs), and real-time interactive systems engineering.
2. **Conflicting Requirements:** The system must navigate sharply competing objectives: maximizing challenge for expert players while preserving accessibility for novices; ensuring 100% topological path solvability while injecting disruptive hazards; and driving high procedural diversity [13] while maintaining strict difficulty targets.
3. **No Obvious Solution:** No closed-form analytical equation exists to calculate how a specific combination of enemy parameters (e.g., high speed + low damage) interacts with terrain modifiers (e.g., tight corridors + high trap density). Both the difficulty mapping and the generative policy must be learned through empirical exploration.
4. **Unfamiliar Issues:** Explores non-linear emergent dynamics: the difficulty of an encounter is not the sum of its parts. A room with high enemy damage but ample line-of-sight cover plays fundamentally differently from an open room with fast-moving melee adversaries. Managing this multi-attribute interaction represents uncharted territory in PCGRL.
5. **Beyond Standard Practice:** Conventional game engineering relies on static level design, random seed shufflers, or simplistic DDA spawn-scaling scripts (§2.5). Synthesizing entire spatial topologies conditioned on rolling latent behavioral vectors moves far beyond off-the-shelf development templates.
6. **Interdependence:** System components form a tightly coupled feedback loop. Telemetry collection directly alters profile embeddings; profile embeddings reshape PPO policy actions; policy outputs dictate game balance; and the difficulty regressor concurrently calculates rewards and drives explainability. An architectural defect in any single module cascades throughout the entire pipeline.
7. **Ill-defined Requirements:** Subjective gameplay qualities such as "fun," "frustration," and "appropriate challenge" have no universal mathematical definitions. FORGE must translate these ambiguous human experiences into measurable telemetry proxies (time-to-clear, deaths, exploration ratios) and validate them against psychometric survey instruments [15].

#### Characteristics Honestly Excluded:
- **Diverse Stakeholders:** FORGE is primarily focused on the single user category of players (with level designers as a secondary technical audience). Fabricating dozens of fictitious stakeholder groups would be disingenuous.
- **Significant Consequences:** System failure results in sub-optimal game pacing or level regeneration, not loss of human life, medical injury, or catastrophic financial collapse.

### 4.2 Core Scope Commitments (In-Scope Deliverables)
To maintain academic rigor while ensuring feasibility within a 3-student, 2-semester timeframe, the committed core scope is explicitly bounded:

1. **Adversary Parameter Vector:** 4 continuous enemy attributes: Health, Damage, Velocity, and Aggro Detection Radius.
2. **Environmental Modifiers:** 2 spatial parameters: Hazard/Trap Density and Resource (Health/Ammo) Scarcity.
3. **Environment Representation:** Forked `gym-pcgrl` 2D grid framework modified to support structured composite actions over room regions.
4. **Telemetry & Profiling Module:** Automated extraction of 5 core behavioral metrics: Completion Time, Death Count, Exploration Percentage, Treasure Collection Ratio, and Combat Engagement Frequency.
5. **Cold-Start Placement Subsystem:** Placement protocol utilizing 3–5 pre-generated calibration maps across discrete difficulty tiers.
6. **Machine Learning Components:**
   - Player-conditioned PPO policy network trained using Stable-Baselines3.
   - Auxiliary difficulty predictor (regressor) with integrated feature-importance extraction (SHAP/permutation).
7. **Interactive Client Application:** Playable 2D top-down dungeon crawler developed in Godot Engine 4.x with custom tilemaps, character controllers, combat mechanics, and local SQLite telemetry logging.
8. **Experimental Baselines:** Functional rule-based BSP room generator and unconditioned PPO generator for comparative benchmarking.

### 4.3 Documented Optional Extensions
The following features are formally classified as optional extensions and will be initiated only if core commitments are validated ahead of schedule:
- Complex behavior-tree AI for adversaries (e.g., flanking, retreating).
- Dynamic lighting, fog-of-war, and line-of-sight concealment modifiers.
- Multi-objective Pareto-optimal generator bank (full MOPCGRL replication [13]).
- Designer-conditioned CPCGRL ablation baseline (§5.5.4).

### 4.4 Scope Baselines & Change Control Process
In accordance with FAST School of Computing standards, any proposed modification to committed core deliverables following Proposal Defense approval must adhere to formal change control:
- No committed requirement may be silently dropped or simplified.
- Scope adjustments must be recorded in `CHANGES.md` within the project repository, detailing: (1) nature of change, (2) technical rationale, (3) empirical evidence prompting the change, (4) impact on evaluation metrics, and (5) written supervisor sign-off.

---

## 5. Proposed Solution & System Architecture

### 5.1 Game Format & Operational Mechanics
FORGE is developed as a top-down 2D real-time combat dungeon crawler implemented in **Godot Engine 4.x**. The game world consists of a bounded, connected graph of discrete rooms (entry chamber, combat corridors, hazard chambers, boss/exit chamber). 

The player navigates an avatar using standard keyboard/mouse inputs, executing real-time melee and ranged combat, avoiding spatial traps, and discovering resource caches. Each dungeon instance is strictly **finite**, featuring a definite termination state (clearing the exit room or player defeat). This bounded formulation ensures that session telemetry metrics (e.g., total elapsed time, total deaths) are evaluated against consistent, comparable gameplay episodes.

### 5.2 Combinatorial Difficulty Model (Difficulty ≠ Enemy Count)
Traditional PCG models scale difficulty linearly by increasing entity spawn counts, leading to repetitive or unplayable scenarios. FORGE models difficulty as an emergent property arising from the combination of an **Enemy Parameter Vector ($\vec{E}$)** and an **Environmental Modifier Vector ($\vec{M}$)**:

$$\vec{E} = \begin{bmatrix} \text{Health} \\ \text{Damage} \\ \text{Speed} \\ \text{Aggro Radius} \end{bmatrix} \in [0, 1]^4, \quad \vec{M} = \begin{bmatrix} \text{Hazard Density} \\ \text{Resource Scarcity} \end{bmatrix} \in [0, 1]^2$$

Difficulty is combinatorial: a dungeon featuring low-health adversaries paired with high hazard density and sparse health drops yields an intense, evasion-focused challenge, whereas high-health adversaries in open terrain yield an endurance-focused challenge.

### 5.3 End-to-End Closed-Loop System Architecture

```mermaid
flowchart TD
    subgraph Client["Godot 4.x Game Client"]
        UI["Game Viewport and Controller"]
        TM["Tilemap and Combat Engine"]
        TL["Telemetry Logger - SQLite"]
        DIR_UI["Design Insight Report UI Panel"]
    end

    subgraph Server["Local Python Inference Server - FastAPI"]
        API["REST and WebSocket Endpoints"]
        PM["Player Profile Manager"]
        PPO["Conditioned PPO Policy Network"]
        DP["Auxiliary Difficulty Predictor"]
        XAI["Feature Attribution Engine - SHAP"]
        ENV["Forked gym-pcgrl Grid Environment"]
    end

    UI -->|Player Actions| TM
    TM -->|Runtime Events| TL
    TL -->|JSON Telemetry Payload| API
    API --> PM
    PM -->|Latent Profile Embedding| PPO
    ENV -->|Grid Observation State| PPO
    PPO -->|Generated Level Data| API
    PPO -->|Layout and Entity Features| DP
    DP -->|Predicted Difficulty Score| XAI
    XAI -->|Attribution Weights| API
    API -->|Instantiate Dungeon| TM
    API -->|Render Explainability Metrics| DIR_UI
```

#### Functional Component Breakdown:
1. **Telemetry Logging Module (Godot):** Intercepts low-level engine signals (damage instances, movement vectors, room transition timestamps) and logs aggregated session metrics into an embedded SQLite database.
2. **Player Profile Manager (Python):** Normalizes rolling session histories into a dense 5-dimensional behavioral vector representing player skill, exploration propensity, and aggression.
3. **Player-Conditioned PPO Policy (Stable-Baselines3):** Deep neural network that accepts the spatial grid state concatenated with the player profile vector to output structured level editing operations.
4. **Auxiliary Difficulty Predictor (PyTorch):** Supervised regression network mapping generated layout configurations to predicted difficulty values, providing the reward-fit feedback signal during training.
5. **Explainability Engine (SHAP):** Computes Shapley values over difficulty predictor features, identifying the exact top-3 factors (e.g., "62% Enemy Damage, 28% Trap Density") driving the predicted difficulty.

### 5.4 Cold-Start Profiling & The Placement Phase
A fundamental challenge in adaptive systems is the **cold-start problem**: when a user launches the game for the first time, no telemetry history exists. Initializing the player with a statistical "average" profile corrupts the personalization premise by subjecting novices or veterans to inaccurate starting conditions.

```mermaid
flowchart LR
    Start(["New Player"]) --> ColdCheck{"Is Session Count 0?"}
    ColdCheck -->|Yes| PoolSelect["Select Map from Calibration Pools"]
    PoolSelect --> RunPlacement["Execute 3 to 5 Placement Matches"]
    RunPlacement --> AggTelemetry["Aggregate Session Telemetry"]
    AggTelemetry --> BuildProfile["Synthesize Initial Profile"]
    BuildProfile --> ActiveLoop["Activate PPO Adaptive Generation"]
    ColdCheck -->|No| ActiveLoop
```

**Methodological Control:** During the 3–5 placement matches, map layouts are drawn from fixed, pre-validated calibration pools (Easy, Moderate, Challenging). Keeping the geometry and spawn distributions identical across all new players ensures that observed variances in performance are strictly attributable to player skill rather than environmental variance.

### 5.5 Reinforcement Learning Methodology

#### 5.5.1 Environment & Structured Action Space
FORGE forks `gym-pcgrl` [10], adapting its Zelda-style 2D grid into a regional, structured editor. Instead of placing individual tiles one-by-one via scalar discrete actions, the agent executes composite regional operations:

$$\text{Action } a_t = \Big( \text{Region Location } (x, y), \text{Adversary Vector } \vec{E}, \text{Environmental Modifier } \vec{M} \Big)$$

This macro-action formulation dramatically reduces episode horizon length while guaranteeing that enemy attributes and spatial hazards are co-optimized in single decision steps.

#### 5.5.2 Multi-Term Reward Function
At the conclusion of each generation episode, the environment evaluates a composite reward function:

$$R = w_1 \cdot R_{\text{solvability}} + w_2 \cdot R_{\text{difficulty\_fit}} + w_3 \cdot R_{\text{diversity}} + w_4 \cdot R_{\text{quality}}$$

- **$R_{\text{solvability}}$ (Hard Constraint):** Returns a large negative penalty if A* search fails to locate an unblocked, valid path from the entry door to the exit chamber.
- **$R_{\text{difficulty\_fit}}$:** Negative squared error between the target difficulty dictated by the player's profile and the predicted difficulty output by the auxiliary regressor: $-(\text{Diff}_{\text{target}} - \text{Diff}_{\text{predicted}})^2$.
- **$R_{\text{diversity}}$:** Penalizes structural similarity against recently generated layouts for the same player, utilizing Jaccard distance over tile representations [14].
- **$R_{\text{quality}}$:** Rewards structural playability heuristics (e.g., maintaining minimum combat arena clearances and avoiding dead-end traps).

#### 5.5.3 Player Profile Formulation & Conditioning
The player profile $\vec{P}_t \in [0, 1]^5$ at session $t$ is updated via an exponential moving average over normalized session metrics:

$$\vec{P}_t = \alpha \cdot \vec{m}_t + (1 - \alpha) \cdot \vec{P}_{t-1}$$

where $\vec{m}_t$ represents the normalized 5-tuple: `[Completion Time, Death Rate, Exploration Ratio, Treasure Rate, Encounter Rate]`, and $\alpha = 0.3$ provides smooth temporal adaptation.

#### 5.5.4 Experimental Baselines
1. **Rule-Based Baseline (BSP):** A classic Binary Space Partitioning dungeon generator instantiating pre-fabricated rooms with hardcoded, static enemy placements.
2. **Unconditioned PPO Baseline:** An RL generator trained on identical grid dimensions but utilizing a standard scalar difficulty target without player profiling.
3. **Designer-Conditioned Ablation (Optional):** A CPCGRL-style agent [2] conditioned on explicit designer-specified targets, isolating the precise value added by automated telemetry inference.

### 5.6 Deployment Architecture & Non-Functional Design
- **Local Packaging:** The Godot client compiles into a native Windows 64-bit binary (`.exe`). The Python RL inference stack is packaged alongside an embedded lightweight virtual environment executing a local FastAPI server.
- **Latency Target:** Complete inference (generation of a multi-room dungeon instance) must execute in **under 2.0 seconds** on a standard evaluation machine (Intel Core i7 / 16GB RAM / mid-range GPU).
- **Graceful Degradation / Fallback:** If the local Python service encounters an exception or exceeds the 2.0-second timeout threshold, the Godot client seamlessly falls back to instantiating a verified procedural level from a pre-generated local cache.
- **Configuration Security:** Zero hardcoded paths or network secrets; all parameters are initialized through a decoupled `config.json` file.

### 5.7 Proposal-Stage Proof of Concept (POC) & Technical Spike

> [!IMPORTANT]
> **Status Notice:** In strict accordance with FAST FYP Guide §12, this section delineates the technical spike design and experimental framework currently under active development. The functional Godot demo and RL convergence curves will be finalized and embedded directly into these placeholders prior to Proposal Defense.

#### The Five POC Questions (FAST FYP Guide §12.1):
1. **What risky assumption was tested?**
   Whether a Proximal Policy Optimization (PPO) agent can achieve stable policy convergence when optimizing for both topological solvability and multi-attribute entity placement within a `gym-pcgrl` grid environment.
2. **What input/setup was used?**
   A standalone Python testbench executing a forked `gym-pcgrl` Zelda environment using Stable-Baselines3 PPO, trained across a preliminary spike of 500 episodes under CPU/GPU acceleration.
3. **What exact result was obtained?**
   `[PLACEHOLDER: Empirical training reward curve, episode loss telemetry, and percentage of verified solvable layouts produced during early checkpoint runs].`
4. **What was learned or disproved?**
   `[PLACEHOLDER: Documented convergence observations, reward-weight stability thresholds, and adjustments made to the solvability penalty].`
5. **How will this change the design or plan?**
   `[PLACEHOLDER: Adjustments to macro-action region dimensions and reward scaling factors derived from spike results].`

#### Godot Interactive Demonstration Prototype (Under Construction):
The team is actively finalizing an interactive prototype in Godot 4.x demonstrating:
- Real-time player movement, weapon collisions, and combat encounters;
- Tilemap rendering of procedurally placed rooms, hazard zones, and spawn points;
- SQLite telemetry capture recording live session events; and
- A prototype *Design Insight Report* UI panel displaying mock feature-attribution breakdowns across varying simulated skill profiles.

`[PLACEHOLDER: Embedded high-resolution screenshots and gameplay recording link illustrating the Godot prototype].`

---

## 6. Timeline, Evaluation & Iterations

### 6.1 Five-Gate Evaluation Trajectory
In alignment with the FAST School of Computing FYP standard, FORGE is structured across five sequential approval gates spanning two semesters:

```mermaid
flowchart LR
    G1["Gate 1: Proposal Defense<br/>Scope Approved and POC Spike"] --> G2["Gate 2 and 3: Mid-1 Review<br/>SRS and SDS Approved"]
    G2 --> G3["Gate 3: Final-1 Exit Gate<br/>Core Build Accepted"]
    G3 --> G4["Gate 4: Mid-2 Review<br/>Release Readiness"]
    G4 --> G5["Gate 5: Final-2 Defense<br/>Final Acceptance and Thesis"]
```

- **Gate 1 (Proposal Defense — Week 6):** Approved proposal, demonstrated feasibility via POC spike, verified scope boundaries, and opened RAID register.
- **Gate 2 & 3 (Mid-1 Review — Week 10):** Formal Software Requirements Specification (SRS) and Software Design Specification (SDS) approved; Godot rendering client and baseline architecture operational.
- **Gate 3 (Final-1 Exit Gate — Week 14):** Core functional build accepted. Forked `gym-pcgrl` environment verified, rule-based baseline implemented, unconditioned PPO baseline trained and generating solvable levels, Godot telemetry pipeline logging to SQLite.
- **Gate 4 (Mid-2 Review — Week 26):** Release readiness. Player profile embedding operational, auxiliary difficulty predictor trained, player-conditioned PPO executing in closed loop with Godot client, system integration testing underway.
- **Gate 5 (Final-2 Acceptance — Week 32):** Final thesis defense. Standalone Windows deployment package verified, User Acceptance Testing (UAT) completed, explainability reporting validated, and complete project report delivered.

> [!IMPORTANT]
> **Vertical Slice Mandate:** Every evaluation gate delivers a fully integrated, functional slice. At no milestone is the project purely frontend UI or purely backend ML script.

### 6.2 Milestone Schedule & Two-Semester Gantt Plan

```mermaid
gantt
    title FORGE Milestone Schedule - 32 Weeks
    dateFormat YYYY-MM-DD
    axisFormat %b %Y

    section FYP-1 Semester 1
    Literature Review and Prior Art :done, 2026-09-01, 2026-09-21
    gym-pcgrl Fork and POC Spike    :active, 2026-09-15, 2026-10-10
    Godot Client Prototype          :active, 2026-09-22, 2026-10-15
    Proposal Defense - Gate 1       :milestone, 2026-10-15, 1d
    SRS and SDS Documentation       :2026-10-16, 2026-11-05
    Mid-1 Review - Gates 2 and 3    :milestone, 2026-11-06, 1d
    Rule-Based BSP Baseline         :2026-11-07, 2026-11-25
    Unconditioned PPO Training      :2026-11-15, 2026-12-10
    Final-1 Exit Gate - Gate 3      :milestone, 2026-12-15, 1d

    section FYP-2 Semester 2
    Parameter Space Integration     :2027-01-15, 2027-02-05
    Player Profiling Subsystem      :2027-02-01, 2027-02-20
    Difficulty Predictor and SHAP   :2027-02-15, 2027-03-10
    Conditioned PPO Policy Training :2027-02-25, 2027-03-25
    Mid-2 Review - Gate 4           :milestone, 2027-03-31, 1d
    Playtesting Cohort Execution    :2027-04-01, 2027-04-20
    Empirical Analysis and UAT      :2027-04-15, 2027-04-30
    Final Report and Packaging      :2027-04-20, 2027-05-10
    Final-2 Defense - Gate 5        :milestone, 2027-05-15, 1d
```

### 6.3 Verification, Testing & Evaluation Framework

#### 6.3.1 Functional Testing
- Automated unit testing verifying SQLite telemetry logging integrity.
- Automated graph reachability tests verifying room connectivity and doorway alignments.
- Automated A* search scripts validating topological solvability.
- Rest API integration tests ensuring sub-2-second payload round-trip response.

#### 6.3.2 Quantitative Evaluation Metrics
- **Solvability Percentage:** Ratio of fully traversable generated layouts over 1,000 automated validation runs.
- **Difficulty-Fit Error:** Absolute variance between target difficulty and auxiliary predictor score: $|\text{Diff}_{\text{target}} - \text{Diff}_{\text{predicted}}|$.
- **Layout Diversity:** Functional pairwise Jaccard distance over room configurations and entity coordinates [14].
- **Convergence Rate:** Number of post-placement game sessions required for player profile stabilization.

### 6.4 User Acceptance Testing (UAT) Protocol
In compliance with FAST FYP Guide §13.1, User Acceptance Testing is executed as a formalized empirical study rather than casual feedback:

| Dimension | Protocol Specification |
| :--- | :--- |
| **Cohort Definition** | 10 human participants distributed across self-declared skill tiers (3 Novice, 4 Intermediate, 3 Expert). |
| **Testing Methodology** | Counterbalanced within-subjects design. Each user plays 3 sessions of Rule-Based BSP, 3 sessions of Unconditioned PPO, and 3 sessions of Adaptive FORGE. |
| **Data Collection** | Quantitative: Real-time telemetry (deaths, time, clears). Qualitative: Standardized post-session surveys utilizing 5-point Likert scales (assessing perceived challenge, flow, frustration, and agency) [15]. |
| **Formal Acceptance Gate** | Statistically significant preference ($p < 0.05$) and ≥ 70% participant consensus confirming FORGE provided a superior personal challenge balance. |

### 6.5 Provisional Acceptance Criteria

> [!NOTE]
> These criteria represent provisional engineering benchmarks established for supervisory review. Quantitative thresholds will be formally baselined during Mid-1 following POC spike completion.

| Performance Dimension | Provisional Acceptance Threshold | Operational Verification Method |
| :--- | :--- | :--- |
| **Topological Solvability** | $\ge 95.0\%$ of generated instances | Automated A* search verification suite over 500 test layouts. |
| **Generation Latency** | $\le 2.0\text{ seconds}$ per dungeon | Benchmarked on target evaluation machine across 100 inference cycles. |
| **Predictor Calibration** | $\text{MAE} \le 0.15$ on a $[0, 1]$ scale | Evaluated on validation split of playtest session logs. |
| **Structural Diversity** | Mean Pairwise Jaccard Distance $\ge 0.30$ | Computed over consecutive layouts generated for the same profile. |
| **Adaptation Speed** | Detectable difficulty shift within $\le 3$ sessions | Measured upon simulated shift from novice to expert play styles. |
| **UAT Satisfaction** | $\ge 70\%$ favorable participant rating | Aggregated from post-playtest Likert satisfaction matrices. |

### 6.6 Risk Management & Mitigation Matrix

| # | Risk Event | Impact | Probability | Mitigation Strategy |
| :---: | :--- | :---: | :---: | :--- |
| **R1** | PPO policy struggles to converge on composite action space | **High** | **Medium** | Validate single-attribute baselines in POC spike first; if necessary, discretize continuous enemy parameters into predefined micro-tiers. |
| **R2** | Insufficient human playtesting volume for regressor training | **Medium** | **Medium** | Augment human playtest data with synthetic scripted bot playthroughs (aggressive bot, cautious bot, random bot) for preliminary training. |
| **R3** | Godot-to-FastAPI inference introduces local execution latency | **Medium** | **Low** | Pre-generate level instances in a background asynchronous thread while player traverses current room; implement cached fallback levels. |
| **R4** | Unsupervised telemetry profiling overfits to transient anomalies | **Medium** | **Medium** | Implement exponential smoothing with decay factor ($\alpha = 0.3$) and require 3–5 placement games to calibrate the baseline. |
| **R5** | Panel challenges novelty based on existing CPCGRL literature | **High** | **Medium** | Reference the structural positioning matrix (§2.3) and "What Is and Isn't New" box (§1.4) directly demonstrating that CPCGRL lacks autonomous profiling. |

---

## 7. Work Breakdown Structure (WBS)

### 7.1 Team Member Allocation Matrix
FORGE enforces distinct technical ownership across three group members. Each member is assigned primary engineering stewardship over dedicated subsystems while sharing integration duties:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FORGE TECHNICAL WORK BREAKDOWN STRUCTURE                 │
└─────────────────────────────────────────────────────────────────────────────┘
         │                               │                               │
         ▼                               ▼                               ▼
┌──────────────────┐            ┌──────────────────┐            ┌──────────────────┐
│     MEMBER A     │            │     MEMBER B     │            │     MEMBER C     │
│ ML & Profiling   │            │ RL Architecture  │            │ Game Engineering │
├──────────────────┤            ├──────────────────┤            ├──────────────────┤
│ • Lit Review     │            │ • gym-pcgrl Fork │            │ • Godot Client   │
│ • SRS / SDS Lead │            │ • PPO Policy Net │            │ • Telemetry / DB │
│ • Profiling Alg  │            │ • Reward Design  │            │ • Local Server   │
│ • Regressor & XAI│            │ • BSP Baseline   │            │ • UI / Insight   │
│ • UAT Analysis   │            │ • RL Training    │            │ • Windows Build  │
└──────────────────┘            └──────────────────┘            └──────────────────┘
```

| Work Package (WP) | Primary Lead | Supporting Member | Deliverable Description | Target Milestone |
| :--- | :---: | :---: | :--- | :---: |
| **WP 1: Prior Art & Literature** | **Member A** | Member B, C | Comprehensive survey, gap analysis, and positioning matrix. | Gate 1 / Gate 3 |
| **WP 2: Environment Forking** | **Member B** | Member C | Modified `gym-pcgrl` grid with composite action wrappers. | Gate 1 / Gate 3 |
| **WP 3: Godot Game Engine Client** | **Member C** | Member A | 2D tilemap rendering, character controllers, combat loop. | Gate 1–Gate 5 |
| **WP 4: SRS / SDS Specifications** | **Member A** | Member B, C | Formal engineering documentation and architecture baselines. | Gate 2 & 3 |
| **WP 5: Telemetry Pipeline** | **Member C** | Member B | SQLite integration logging runtime combat events to JSON. | Gate 3 |
| **WP 6: Rule-Based & PPO Baselines** | **Member B** | Member A | Functional BSP generator and unconditioned PPO agent. | Gate 3 |
| **WP 7: Player Profiling Module** | **Member A** | Member B | Exponential smoothing engine and cold-start placement logic. | Gate 4 |
| **WP 8: Conditioned PPO Training** | **Member B** | Member A | Multi-attribute conditioned PPO policy optimization. | Gate 4 |
| **WP 9: Difficulty Predictor & XAI** | **Member A** | Member C | Auxiliary regressor and SHAP Design Insight Report engine. | Gate 4 |
| **WP 10: Client-Server API Bridge** | **Member C** | Member B | FastAPI integration connecting Godot to local PPO inference. | Gate 4 |
| **WP 11: Playtesting & UAT Study** | **All** | — | Cohort coordination, survey deployment, empirical logging. | Gate 5 |
| **WP 12: Statistical Data Analysis** | **Member A** | Member B | Solvability, diversity, and engagement hypothesis testing. | Gate 5 |
| **WP 13: Deployment Packaging** | **Member C** | Member B | Standalone Windows distribution build and documentation. | Gate 5 |
| **WP 14: Final Project Report** | **All** | — | Comprehensive academic capstone thesis document. | Gate 5 |

### 7.2 Individual Accountability & Removal Test

> [!IMPORTANT]
> **FAST FYP Scope Diagnostic:** *"If one member were removed, would a meaningful technical responsibility and its evidence disappear?"*

- **If Member A is removed:** The player profiling engine, difficulty regressor, SHAP explainability pipeline, and statistical UAT study collapse entirely.
- **If Member B is removed:** The custom `gym-pcgrl` environment, composite PPO policy, multi-term reward architecture, and RL baselines disappear.
- **If Member C is removed:** The Godot game application, character combat mechanics, SQLite telemetry system, and local inference server bridge disappear.

The project cannot succeed without all three members executing their primary ownership areas.

---

## 8. Tools, Technology & External Components

### 8.1 Technology Stack

| Layer | Technology | Version / Tooling | Justification & Architectural Role |
| :--- | :--- | :--- | :--- |
| **Game Engine** | Godot Engine | 4.x (GDScript / C#) | Lightweight, native 2D tilemap support, high-performance execution on consumer Windows hardware. |
| **RL Library** | Stable-Baselines3 | Python 3.10+ | Industry-standard, peer-reviewed implementation of Proximal Policy Optimization (PPO) [11]. |
| **Environment** | `gym-pcgrl` (Forked) | Farama Gymnasium | Reference PCGRL grid framework [10], customized for regional composite action spaces. |
| **Deep Learning** | PyTorch | 2.x | Neural network construction for auxiliary difficulty prediction and reward calculation. |
| **Explainability** | SHAP | Latest Stable | Permutation-based Shapley feature attribution for Design Insight Reports. |
| **Local Database** | SQLite | 3.x | Zero-configuration, file-based relational storage for low-latency session telemetry logging. |
| **Inference Server**| FastAPI / Uvicorn | Latest Stable | Asynchronous local REST API handling JSON level payloads between Python and Godot. |
| **Source Control** | Git / GitHub | GitHub Repository | Distributed version control, issue tracking, and code reviews. |
| **AI Logging** | Spreadsheet / MD | `AI Logs/` Directory | Comprehensive audit trail of generative AI usage pursuant to FAST FYP Guide §8.4. |

### 8.2 External Component Classification
Pursuant to Section 14 of the FAST School of Computing FYP Guide, all external libraries and frameworks are categorized to ensure academic integrity:

| Component | Framework Category | Technical Justification & Local Contribution Boundary |
| :--- | :---: | :--- |
| **Stable-Baselines3 (PPO)** | **Support** (Permitted) | Provides the underlying backpropagation optimizer. FORGE's novel contribution lies in the reward mathematics, policy conditioning inputs, and action spaces — not the base PPO algorithm. |
| **Godot Engine 4.x** | **Support** (Permitted) | Provides general graphics rendering, collision physics, and window management. All gameplay mechanics, enemy scripts, and telemetry hooks are custom-written code. |
| **`gym-pcgrl` (Forked)** | **Core-Assist** (Permitted with Justification) | Serves as the base tile-grid simulator. FORGE substantially rewrites its internal step functions to support composite parameter vectors and custom solvability checks. |
| **SHAP Library** | **Support** (Permitted) | Mathematical calculation utility for Shapley values. The underlying feature space and interpretation pipelines are custom-engineered. |
| **FastAPI Framework** | **Support** (Permitted) | Lightweight network transport layer for local inter-process communication. |

> [!CAUTION]
> **Academic Integrity Assurance:** No third-party library or model is utilized in the **Core-Replacement** category. If any external tool were swapped for an alternative, the fundamental academic contributions of FORGE (telemetry profiling, combinatorial difficulty formulation, explainable PCGRL) remain fully intact and distinct.

### 8.3 AI-Assisted Development Framework & Usage Logging
The FAST School of Computing FYP Guide explicitly positions capstone development at **Level 2 (AI-Assisted Development)**: human students maintain complete design authority and technical ownership while utilizing AI tooling solely for localized assistance (code refactoring, syntax debugging, boilerplate generation).

- **Defense Preparedness:** Every team member is capable of passing the four tests of understanding on all codebase components: (1) Explaining functionality without reading code, (2) Justifying architectural decisions against alternatives, (3) Predicting failure modes under stress, and (4) Modifying code live under panel questioning.
- **Usage Audit Trail:** In strict compliance with Guide §8.4, all generative assistance is recorded contemporaneously within the project repository under `AI Logs/`, tracking tool name, query prompt, output summary, and human validation steps.

### 8.4 FAST FYP Guide Alignment Checklist

| Guide Standard | FYP Requirement | FORGE Section | Status |
| :--- | :--- | :---: | :---: |
| **§ 1.1 Entry Stream** | Formally declare entry path and primary early risk profile | §1, §3 | ✅ **Stream A Declared** |
| **§ 1.2 Deployability** | Installable by third party, realistic environment, non-functional targets | §5.6, §6.5 | ✅ **Windows Build Defined** |
| **§ 1.3 SDG Alignment** | Contextual alignment to UN Sustainable Development Goals | §1.6 | ✅ **SDG 3 & 9 Documented** |
| **§ 3.0 CCP Criteria** | Explicit mapping against recognized Seoul Accord characteristics | §4.1 | ✅ **7 of 9 Mapped Rigorously** |
| **§ 4.0 Contribution** | Strict one-sentence formula and novelty boundary definition | §1.4 | ✅ **Formula Fully Compliant** |
| **§ 5.1 Checkpoints** | Mapping project milestones across all 5 evaluation gates | §6.1 | ✅ **All 5 Gates Mapped** |
| **§ 8.4 AI Usage Log** | Active log tracking generative AI assistance | §8.3 | ✅ **Repository Log Active** |
| **§ 12.0 POC Spike** | Demonstration of feasibility testing highest-risk assumption | §5.7 | ⚠️ **In Progress (Pre-Defense)** |
| **§ 13.1 Testing vs UAT**| Distinct separation of functional testing, ML evaluation, and UAT | §6.3, §6.4 | ✅ **Distinctly Segmented** |
| **§ 14.0 Ownership** | Classification of dependencies into Support / Core-Assist | §8.2 | ✅ **Fully Classified** |

---

## 9. References & Citations (IEEE Style)

[1] A. Khalifa, P. Bontrager, S. Earle, and J. Togelius, "PCGRL: Procedural content generation via reinforcement learning," in *Proc. AAAI Conf. Artif. Intell. Interactive Digital Entertainment (AIIDE)*, 2020, pp. 95–101.

[2] S. Earle, S. Snodgrass, A. Smith, *et al.*, "Learning controllable content generators," in *Proc. IEEE Conf. Games (CoG)*, 2021, pp. 1–8.

[3] D. Baek *et al.*, "IPCGRL: Language-instructed reinforcement learning for procedural level generation," *arXiv preprint arXiv:2501.09876*, 2025.

[4] S. Huang, D. Baik, and B. C. Kwon, "Online game level generation from music (OPARL: Online player-adaptive PCG via RL)," in *Proc. IEEE Conf. Games (CoG)*, 2022, pp. 248–255.

[5] M. Barthet, D. Branco, R. Gallotta, A. Khalifa, and G. N. Yannakakis, "Closing the affective loop via experience-driven reinforcement learning designers," in *Proc. Int. Conf. Foundations of Digital Games (FDG)*, 2024, pp. 1–10.

[6] G. N. Yannakakis and J. Togelius, "Experience-driven procedural content generation," *IEEE Trans. Affect. Comput.*, vol. 2, no. 3, pp. 147–161, 2011.

[7] L. Gisslén, L. Eklund, P. Bergdahl, and K. Tollmar, "Adversarial reinforcement learning for procedural content generation," in *Proc. IEEE Conf. Games (CoG)*, 2021, pp. 1–8.

[8] K. Shi, R. Volz, and J. Togelius, "Guided game level repair via explainable AI," *arXiv preprint arXiv:2403.11204*, 2024.

[9] E. Lindström, "AI Director vs. No Director: Evaluating dynamic difficulty in a dungeon crawler," Master's thesis, Department of Game Design, Uppsala University, DiVA portal, 2023.

[10] S. Earle *et al.*, "gym-pcgrl: Gymnasium environment for procedural content generation via reinforcement learning," GitHub repository, 2020. [Online]. Available: https://github.com/smearle/gym-pcgrl

[11] J. Schulman, F. Wolski, P. Dhariwal, A. Radford, and O. Klimov, "Proximal policy optimization algorithms," *arXiv preprint arXiv:1707.06347*, 2017.

[12] R. Hunicke, "The case for dynamic difficulty adjustment in games," in *Proc. ACM SIGCHI Int. Conf. Advances in Comput. Entertainment Technol. (ACE)*, 2005, pp. 429–433.

[13] Y. Yuan, Q. Zhang, B. Yuan, M. Barthet, A. Khalifa, G. N. Yannakakis, H. Chen, and J. Liu, "MOPCGRL: Multi-objective procedural content generation via reinforcement learning," *Complex Syst. Model. Simul.*, vol. 6, no. 1, pp. 57–74, Mar. 2026, doi: 10.23919/CSMS.2025.0034.

[14] K. Weber, T. Smith, and M. Preuss, "Measuring diversity of game scenarios," in *Proc. IEEE Conf. Games (CoG)*, 2025, doi: 10.1109/CoG60021.2025.10896853.

[15] C. Alvarez, A. Salge, and S. Deterding, "Playing the imitation game: How perceived generated content shapes player experience," in *Proc. ACM Conf. Human Factors in Computing Systems (CHI)*, 2025, doi: 10.1145/3772318.3790473.

[16] D. F. Silva, R. P. Torchelsen, and M. S. Aguiar, "Procedural game level generation with GANs: Potential, weaknesses, and unresolved challenges in the literature," *Multimedia Tools Appl.*, vol. 84, no. 28, pp. 34179–34205, 2025, doi: 10.1007/s11042-025-20612-9.
