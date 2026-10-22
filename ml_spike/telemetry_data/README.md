# FORGE — Empirical Gameplay Telemetry Store

This directory serves as the centralized repository for empirical player telemetry generated during active gameplay sessions.

## File Contents
- **`session_telemetry.json`**: An array of rolling session performance records captured by `TelemetryLogger.gd` at key runtime milestones:
  - **Room Clear (`_on_room_cleared`)**: Intercepts combat outcomes and room progression rates.
  - **Player Death (`_on_player_died`)**: Captures health deltas, time-to-failure, and hazard interactions.
  - **Dungeon Escaped (`_on_dungeon_escaped`)**: Records floor completion metrics upon stepping through the exit portal.

## Telemetry Schema Reference
```json
[
  {
    "session_id": "sess_1792128297.327",
    "timestamp": 1792128297.0,
    "elapsed_seconds": 128.1,
    "rooms_cleared": 3.0,
    "total_deaths": 1.0,
    "damage_dealt": 420.0,
    "damage_taken": 85.0,
    "enemies_defeated": 8.0,
    "pickups_collected": 4.0,
    "hazard_hits": 2.0,
    "exploration_efficiency": 0.85
  }
]
```

## Machine Learning Integration (FYP-2)
In the initial prototype (`ml_spike/train_ppo_difficulty.py`), the PPO policy is trained against a synthetic heuristic function (`_simulate_level()`). 

During FYP-2, this empirical dataset directly replaces the synthetic curves:
1. **State Observation Fitting**: Maps actual player pacing ($\Delta_{\text{time}} = \frac{\text{elapsed\_seconds}}{\text{rooms\_cleared} \times 25.0}$) and damage defense ratios to the 8D PPO input vector.
2. **Offline RL & Transition Modeling**: Fits empirical player skill transitions $P(s_{t+1} \mid s_t, a_t)$ to train the policy without human-in-the-loop bottlenecks.
3. **Reward Alignment**: Aligns the reward function $R_t$ to penalize states that trigger high death spikes or flow dropouts.
