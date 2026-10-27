# FORGE — Empirical Gameplay Telemetry Store

This directory serves as the centralized repository for empirical player telemetry generated during active gameplay sessions.

## Storage Formats
- **`session_telemetry.db`**: Local SQLite database storing structured player session telemetry in the `session_telemetry` table. Provides high-performance indexing, transactional consistency, and efficient query access for machine learning training.
- **`session_telemetry.json`**: Flat JSON array format maintained for backward compatibility and human inspection.
- **`telemetry_db.py`**: Python SQLite management library providing the `TelemetryDatabase` class for inserting, querying, and migrating telemetry records.

## SQLite Schema Reference
```sql
CREATE TABLE IF NOT EXISTS session_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    elapsed_seconds REAL NOT NULL,
    rooms_cleared REAL NOT NULL,
    total_deaths REAL NOT NULL,
    damage_dealt REAL NOT NULL,
    damage_taken REAL NOT NULL,
    enemies_defeated REAL NOT NULL,
    pickups_collected REAL NOT NULL,
    hazard_hits REAL NOT NULL,
    exploration_efficiency REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telemetry_session_id ON session_telemetry(session_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON session_telemetry(timestamp);
```

## Python Usage
```python
from ml_spike.telemetry_data.telemetry_db import TelemetryDatabase

# Initialize connection (auto-creates database and table if not present)
db = TelemetryDatabase()

# Fetch all training records
sessions = db.get_all_sessions()

# Query summary statistics
stats = db.get_summary_stats()
print(f"Total sessions: {stats['total_sessions']}")

# Import from / Export to JSON
db.import_from_json("session_telemetry.json")
db.export_to_json("session_telemetry.json")
```

## Machine Learning Integration (FYP-2)
In the initial prototype (`ml_spike/train_ppo_difficulty.py`), the PPO policy is trained against a synthetic heuristic function (`_simulate_level()`). 

During FYP-2, this empirical SQLite dataset directly replaces the synthetic curves:
1. **State Observation Fitting**: Maps actual player pacing ($\Delta_{\text{time}} = \frac{\text{elapsed\_seconds}}{\text{rooms\_cleared} \times 25.0}$) and damage defense ratios to the 8D PPO input vector.
2. **Offline RL & Transition Modeling**: Fits empirical player skill transitions $P(s_{t+1} \mid s_t, a_t)$ to train the policy without human-in-the-loop bottlenecks.
3. **Reward Alignment**: Aligns the reward function $R_t$ to penalize states that trigger high death spikes or flow dropouts.
