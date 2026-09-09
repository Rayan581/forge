# FORGE — Scope Change Control Register (`CHANGES.md`)

Pursuant to FAST School of Computing standards and Section 4.5 of the FORGE Proposal, this document records all formal modifications to committed scope, architecture baselines, and engineering parameters following initial proposal draft and POC spike validation.

---

## Change Log

### Change CR-01: Shift from Local REST Server (FastAPI) to Embedded GDScript Neural Runtime
- **Date:** September 2026
- **Nature of Change:** Architectural simplification / Latency optimization
- **Subsystem:** Inference Engine (`PPOPolicy.gd`)
- **Technical Rationale:** The original architecture assumed a Python-based REST microservice (FastAPI/Uvicorn) was required for PPO policy forward passes. The Gate 1 Proof of Concept (POC) demonstrated that the multi-layer perceptron (MLP) weights and biases could be serialized to a lightweight JSON bundle (`policy_weights.json`, < 50 KB) and executed directly in GDScript via native matrix-vector dot products.
- **Empirical Evidence:** In-process GDScript inference executes in $< 0.5\text{ ms}$, completely eliminating network serialization overhead ($\sim 50\text{ ms}$) and avoiding port/firewall conflicts or Python packaging on client evaluation machines.
- **Impact on Evaluation Metrics:** Positive. Reduces generation latency from $\approx 2.0\text{s}$ to sub-second; reduces external client dependencies to zero.
- **Disposition:** Approved by team and documented in Proposal §5.6, §5.7.

---

### Change CR-02: Replacement of `gym-pcgrl` Fork with Standalone Custom Gymnasium Environment
- **Date:** September 2026
- **Nature of Change:** Environment redesign
- **Subsystem:** Training Environment (`DungeonDifficultyEnv`)
- **Technical Rationale:** The original proposal plan considered forking the external `gym-pcgrl` codebase. However, `gym-pcgrl` is primarily structured for tile-by-tile micro-editing in 2D platformers and Sokoban grids, which introduced unnecessary abstraction layers and dependency overhead for 30-level top-down dungeon episodes.
- **Empirical Evidence:** A custom, clean-slate Gymnasium environment (`ml_spike/train_ppo_difficulty.py`) was implemented from first principles. It models stochastic player skill drift, continuous 7D/8D parameter scaling, and anti-reward-hacking per-room pacing directly.
- **Impact on Evaluation Metrics:** Positive. Improves training convergence speed (300k timesteps in minutes) and eliminates external library fragility.
- **Disposition:** Approved by team and documented in Proposal §5.5, §7.1, §8.2.

---

### Change CR-03: Reward Function Pacing Reformulation (Anti-Reward-Hacking Loop)
- **Date:** September 2026
- **Nature of Change:** RL reward function mathematical correction
- **Subsystem:** RL Training Pipeline (`train_ppo_difficulty.py`)
- **Technical Rationale:** The initial reward formulation evaluated total episode completion time against a static duration target. The PPO policy discovered a reward-hacking exploit: when faced with a skilled player, instead of increasing enemy stats, it generated tiny 4-room dungeons to minimize total completion time.
- **Empirical Evidence:** Sensitivity inspection revealed the agent collapsed room counts to $N=4$. The reward function was revised to evaluate per-room clearance rate ($t_{\text{room}} = T / N_{\text{rooms}}$) and penalize room count mismatches against target skill bands.
- **Impact on Evaluation Metrics:** Successfully eliminated the exploit; stabilized room generation within appropriate ranges ($[4, 12]$ rooms).
- **Disposition:** Approved by team and documented in Proposal §5.5.2, §5.7.1.
