# FORGE — Gameplay Telemetry Store

Python access to the telemetry the game records, used to build the Judge-model corpus.

## Where the data lives
- **Game side:** `TelemetryLogger.gd` writes `user://forge_telemetry.db` when the godot-sqlite addon is
  installed (see `godot_prototype/addons/README_SQLITE.md`), otherwise `user://session_telemetry.json`.
  On Windows `user://` is `%APPDATA%\Godot\app_userdata\FORGE - Adaptive Dungeon Prototype\`.
- **Schema:** `godot_prototype/telemetry/schema.sql` + `queries.sql` — one source of truth, executed by
  both the game and this package. Tables: `sessions`, `floors` (one row per finished floor: outcome,
  the 8 difficulty parameters, 5-archetype mix, policy obs/action, frame times), `kills_by_archetype`,
  and the flattened view `v_corpus`.
- **Python side:** `telemetry_db.py` (`TelemetryDatabase`) keeps a local copy at
  `ml_spike/telemetry_data/forge_telemetry.db` (gitignored).
- **`session_telemetry.json`:** legacy pre-SQLite sample snapshots. Never imported automatically
  (`auto_populate=False` by default) so sample data can't mix with real playtests.

## Usage
```bash
# pull the latest sessions/floors from the game's user:// DB and print summary stats
python ml_spike/telemetry_data/telemetry_db.py

# Judge corpus as CSV (one row per floor)
python ml_spike/analysis/export_telemetry.py ml_spike/telemetry_data/forge_telemetry.db corpus.csv --consented-only
```
```python
from ml_spike.telemetry_data.telemetry_db import TelemetryDatabase
db = TelemetryDatabase()
db.sync_from_game_db()                # idempotent; re-syncing updates rows
data = db.get_judge_training_data()   # features/targets; rows with missing params are skipped
```

## Rules
- Sessions are keyed by id and floors by (session_id, floor_num): repeated saves update, never duplicate.
- Missing difficulty parameters are stored as NULL, never filled with defaults; the Judge loader
  skips incomplete rows and reports how many (`skipped`).
- Zero PII: sessions carry a random install id only. Export with `--consented-only` for the study corpus.
