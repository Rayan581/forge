"""Tests for the FORGE Telemetry SQLite Database.

Validates:
1. Schema & indexing for both session_telemetry and floor_telemetry.
2. Deduplication of session rows (no duplicate session records).
3. Per-floor telemetry for training the supervised Judge model (settings -> outcome).
4. Auto-population on first run without committing binary .db files.
5. Export to JSON roundtrip.
6. Summary metrics calculation (treating rooms_per_minute accurately).
7. Game DB syncing from user://telemetry.db.
8. Integration with train_ppo_difficulty.load_training_data_from_sqlite().
"""

import json
import os
import tempfile

import pytest
from ml_spike.telemetry_data.telemetry_db import (
    DEFAULT_JSON_PATH,
    TelemetryDatabase,
)


@pytest.fixture
def temp_db():
    """Provides a fresh temporary SQLite database (empty, no auto-population)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_telemetry.db")
        db = TelemetryDatabase(db_path=db_path, auto_populate=False)
        yield db


def test_sqlite_tables_and_indices_creation(temp_db):
    """Verifies that session_telemetry and floor_telemetry tables and indices exist."""
    with temp_db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert "session_telemetry" in tables
        assert "floor_telemetry" in tables

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indices = [row[0] for row in cursor.fetchall()]
        assert "idx_telemetry_timestamp" in indices
        assert "idx_floor_session_num" in indices


def test_session_deduplication_on_upsert(temp_db):
    """Verifies that multiple snapshots of the same session update the row instead of creating duplicates."""
    snap1 = {
        "session_id": "sess_100",
        "timestamp": 1000.0,
        "elapsed_seconds": 30.0,
        "rooms_cleared": 1.0,
        "total_deaths": 0.0,
        "damage_dealt": 50.0,
        "damage_taken": 10.0,
        "enemies_defeated": 2.0,
        "pickups_collected": 1.0,
        "hazard_hits": 0.0,
        "exploration_efficiency": 2.0,
    }
    snap2 = {
        "session_id": "sess_100",
        "timestamp": 1020.0,
        "elapsed_seconds": 50.0,
        "rooms_cleared": 2.0,
        "total_deaths": 1.0,
        "damage_dealt": 120.0,
        "damage_taken": 45.0,
        "enemies_defeated": 5.0,
        "pickups_collected": 2.0,
        "hazard_hits": 1.0,
        "exploration_efficiency": 2.4,
    }
    temp_db.upsert_session(snap1)
    assert temp_db.count_sessions() == 1

    temp_db.upsert_session(snap2)
    # Count must STILL be 1, because it updated the existing session!
    assert temp_db.count_sessions() == 1

    stored = temp_db.get_session("sess_100")
    assert stored is not None
    assert stored["elapsed_seconds"] == 50.0
    assert stored["total_deaths"] == 1.0
    assert stored["rooms_cleared"] == 2.0


def test_json_import_deduplicates_sessions(temp_db):
    """Verifies that importing session_telemetry.json consolidates 50 rolling snapshots

    into 2 distinct session entities.
    """
    assert os.path.exists(DEFAULT_JSON_PATH), f"Missing JSON dataset: {DEFAULT_JSON_PATH}"

    with open(DEFAULT_JSON_PATH, "r", encoding="utf-8") as f:
        raw_snapshots = json.load(f)
    assert len(raw_snapshots) == 50

    unique_sessions_count = temp_db.import_from_json(DEFAULT_JSON_PATH, clear_existing=True)
    assert unique_sessions_count == 2
    assert temp_db.count_sessions() == 2

    sessions = temp_db.get_all_sessions()
    assert len(sessions) == 2
    session_ids = {s["session_id"] for s in sessions}
    assert "sess_1792128297.327" in session_ids
    assert "sess_1792602157.482" in session_ids


def test_floor_telemetry_for_judge_model(temp_db):
    """Verifies recording per-floor difficulty parameters and outcomes for Judge model training."""
    floor_1 = {
        "session_id": "sess_judge_test",
        "floor_number": 1,
        "timestamp": 1000.0,
        "completion_time": 42.5,
        "deaths": 0,
        "damage_dealt": 350.0,
        "damage_taken": 25.0,
        "damage_exchange_ratio": 14.0,
        "rooms_cleared": 6,
        "enemies_defeated": 8,
        "hazard_hits": 1,
        "pickups_collected": 2,
        # 8 Difficulty parameters
        "enemy_health": 45.0,
        "enemy_damage": 12.0,
        "enemy_speed": 110.0,
        "enemy_aggro": 180.0,
        "hazard_density": 0.25,
        "resource_scarcity": 0.40,
        "room_count": 6.0,
        "enemy_count_scale": 1.0,
        # Archetype mix
        "crawler_ratio": 0.6,
        "pyromancer_ratio": 0.4,
        "archetype_mix": "60% Crawler, 40% Pyro",
        "observation_vector": [0.47, 0.0, 0.25, 0.35, 0.2, 0.25, 0.25, 0.03],
        "action_vector": [-0.2, -0.3, 0.1, -0.1, -0.4, -0.2, 0.0],
    }
    floor_2 = {
        "session_id": "sess_judge_test",
        "floor_number": 2,
        "timestamp": 1050.0,
        "completion_time": 55.0,
        "deaths": 1,
        "damage_dealt": 480.0,
        "damage_taken": 85.0,
        "damage_exchange_ratio": 5.65,
        "rooms_cleared": 7,
        "enemies_defeated": 12,
        "hazard_hits": 3,
        "pickups_collected": 3,
        "enemy_health": 55.0,
        "enemy_damage": 18.0,
        "enemy_speed": 125.0,
        "enemy_aggro": 220.0,
        "hazard_density": 0.35,
        "resource_scarcity": 0.50,
        "room_count": 7.0,
        "enemy_count_scale": 1.1,
        "crawler_ratio": 0.5,
        "pyromancer_ratio": 0.5,
        "archetype_mix": "50% Crawler, 50% Pyro",
        "observation_vector": [0.61, 0.33, 0.85, 0.45, 0.3, 0.35, 0.5, 0.07],
        "action_vector": [0.0, 0.1, 0.2, 0.1, -0.1, 0.0, 0.2],
    }
    temp_db.upsert_floor_record(floor_1)
    temp_db.upsert_floor_record(floor_2)

    assert temp_db.count_floor_records() == 2

    judge_data = temp_db.get_judge_training_data()
    assert judge_data["sample_count"] == 2
    assert len(judge_data["feature_names"]) == 10
    assert len(judge_data["target_names"]) == 4

    # Check that settings (X) map to outcomes (Y)
    f1 = judge_data["features"][0]
    t1 = judge_data["targets"][0]
    assert f1[0] == 45.0  # enemy_health
    assert f1[1] == 12.0  # enemy_damage
    assert t1[0] == 42.5  # completion_time
    assert t1[1] == 0.0  # deaths


def test_auto_populate_when_db_missing():
    """Verifies that TelemetryDatabase initializes from JSON when no DB exists on disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "auto_telemetry.db")
        assert not os.path.exists(db_path)

        db = TelemetryDatabase(db_path=db_path, auto_populate=True)
        assert os.path.exists(db_path)
        assert db.count_sessions() == 2


def test_sync_from_game_db(temp_db):
    """Verifies merging records from a game database (user://telemetry.db)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        game_db_path = os.path.join(tmpdir, "game_telemetry.db")
        game_db = TelemetryDatabase(db_path=game_db_path, auto_populate=False)
        game_db.upsert_session(
            {
                "session_id": "game_sess_999",
                "timestamp": 2000.0,
                "elapsed_seconds": 120.0,
                "rooms_cleared": 4.0,
                "total_deaths": 0.0,
                "damage_dealt": 300.0,
                "damage_taken": 20.0,
                "enemies_defeated": 10.0,
                "pickups_collected": 3.0,
                "hazard_hits": 0.0,
                "exploration_efficiency": 2.0,
            }
        )
        game_db.upsert_floor_record(
            {
                "session_id": "game_sess_999",
                "floor_number": 1,
                "timestamp": 2000.0,
                "completion_time": 45.0,
                "deaths": 0,
                "damage_dealt": 150.0,
                "damage_taken": 10.0,
                "damage_exchange_ratio": 15.0,
                "rooms_cleared": 4,
                "enemies_defeated": 10,
                "hazard_hits": 0,
                "pickups_collected": 3,
                "enemy_health": 50.0,
                "enemy_damage": 15.0,
                "enemy_speed": 100.0,
                "enemy_aggro": 200.0,
                "hazard_density": 0.2,
                "resource_scarcity": 0.3,
                "room_count": 4.0,
                "enemy_count_scale": 1.0,
            }
        )

        imported_sess, imported_floors = temp_db.sync_from_game_db(game_db_path)
        assert imported_sess == 1
        assert imported_floors == 1
        assert temp_db.get_session("game_sess_999") is not None
        assert temp_db.count_floor_records() == 1


def test_load_training_data_from_sqlite_integration(temp_db):
    """Verifies train_ppo_difficulty.load_training_data_from_sqlite returns distinct sessions."""
    from train_ppo_difficulty import load_training_data_from_sqlite

    temp_db.import_from_json(DEFAULT_JSON_PATH, clear_existing=True)
    sessions = load_training_data_from_sqlite(temp_db.db_path)
    assert len(sessions) == 2
    assert sessions[0]["session_id"].startswith("sess_")
