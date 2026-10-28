# FORGE — Empirical Gameplay Telemetry Store

This directory serves as the centralized repository for empirical player telemetry generated during active gameplay sessions.

## Storage Architecture
- **`session_telemetry.json`**: Flat JSON array format maintained as the source dataset.
- **SQLite Database (`session_telemetry.db` / `telemetry.db`)**: Dynamically generated local SQLite database (gitignored to prevent tracking binary build artifacts). Automatically populated from JSON or synced from the game client runtime.
- **`telemetry_db.py`**: Python SQLite management library providing the `TelemetryDatabase` class for sessions, floor-level telemetry, and syncing.

## Relational Schema Reference

### 1. Distinct Sessions (`session_telemetry`)
Aggregates session-level cumulative stats keyed uniquely by `session_id` (preventing duplicate rows across multiple in-run checkpoints):
```sql
CREATE TABLE IF NOT EXISTS session_telemetry (
    session_id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    elapsed_seconds REAL NOT NULL,
    rooms_cleared REAL NOT NULL,
    total_deaths REAL NOT NULL,
    damage_dealt REAL NOT NULL,
    damage_taken REAL NOT NULL,
    enemies_defeated REAL NOT NULL,
    pickups_collected REAL NOT NULL,
    hazard_hits REAL NOT NULL,
    exploration_efficiency REAL NOT NULL, -- rooms cleared per minute
    rooms_per_minute REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. Per-Floor Outcome Traces for "The Judge" (`floor_telemetry`)
Captures the exact mapping of **applied difficulty parameters & enemy mix $\rightarrow$ resulting player outcome** for training the supervised XGBoost / TreeSHAP Judge model:
```sql
CREATE TABLE IF NOT EXISTS floor_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    floor_number INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    -- Outcomes
    completion_time REAL NOT NULL,
    deaths INTEGER NOT NULL,
    damage_dealt REAL NOT NULL,
    damage_taken REAL NOT NULL,
    damage_exchange_ratio REAL DEFAULT 0.0,
    rooms_cleared INTEGER NOT NULL,
    enemies_defeated INTEGER NOT NULL,
    hazard_hits INTEGER NOT NULL,
    pickups_collected INTEGER NOT NULL,
    -- 8 Difficulty Settings
    enemy_health REAL NOT NULL,
    enemy_damage REAL NOT NULL,
    enemy_speed REAL NOT NULL,
    enemy_aggro REAL NOT NULL,
    hazard_density REAL NOT NULL,
    resource_scarcity REAL NOT NULL,
    room_count REAL NOT NULL,
    enemy_count_scale REAL DEFAULT 1.0,
    -- Archetype Mix
    crawler_ratio REAL DEFAULT 0.5,
    pyromancer_ratio REAL DEFAULT 0.5,
    archetype_mix TEXT DEFAULT '',
    -- Policy Vectors
    observation_vector TEXT DEFAULT '',
    action_vector TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, floor_number)
);
```

## Python Usage
```python
from ml_spike.telemetry_data.telemetry_db import TelemetryDatabase

# Initialize connection (auto-generates and populates SQLite on first run)
db = TelemetryDatabase()

# Fetch all distinct sessions
sessions = db.get_all_sessions()

# Retrieve Judge training dataset (features X -> outcomes Y)
judge_dataset = db.get_judge_training_data()
X = judge_dataset["features"]  # 8 difficulty parameters + enemy mix
Y = judge_dataset["targets"]   # completion time, deaths, damage taken, ratio

# Sync live game records from Godot client (user://telemetry.db)
imported_sess, imported_floors = db.sync_from_game_db()
print(f"Synced {imported_sess} sessions and {imported_floors} floors from game DB.")
```
