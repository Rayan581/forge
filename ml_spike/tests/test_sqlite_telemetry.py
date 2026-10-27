"""Tests for the FORGE Telemetry SQLite Database.

Validates schema, indexing, JSON migration parity, batch inserts, and summary metrics.
"""

import json
import os
import tempfile

import pytest
from ml_spike.telemetry_data.telemetry_db import (
    DEFAULT_JSON_PATH,
    TELEMETRY_FIELDS,
    TelemetryDatabase,
)


@pytest.fixture
def temp_db():
    """Provides a fresh temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_telemetry.db")
        db = TelemetryDatabase(db_path=db_path)
        yield db


def test_sqlite_table_and_indices_creation(temp_db):
    """Verifies that session_telemetry table and indices are properly created."""
    with temp_db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='session_telemetry';"
        )
        assert cursor.fetchone() is not None

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_telemetry_%';"
        )
        indices = [row[0] for row in cursor.fetchall()]
        assert "idx_telemetry_session_id" in indices
        assert "idx_telemetry_timestamp" in indices


def test_insert_single_session(temp_db):
    """Verifies single session insertion and retrieval."""
    sample = {
        "session_id": "sess_test_001",
        "timestamp": 1700000000.0,
        "elapsed_seconds": 65.4,
        "rooms_cleared": 5.0,
        "total_deaths": 1.0,
        "damage_dealt": 150.0,
        "damage_taken": 40.0,
        "enemies_defeated": 6.0,
        "pickups_collected": 3.0,
        "hazard_hits": 1.0,
        "exploration_efficiency": 1.25,
    }
    rec_id = temp_db.insert_session(sample)
    assert rec_id == 1
    assert temp_db.count() == 1

    sessions = temp_db.get_all_sessions()
    assert len(sessions) == 1
    stored = sessions[0]
    for field in TELEMETRY_FIELDS:
        assert stored[field] == sample[field]


def test_json_migration_parity(temp_db):
    """Verifies that migrating session_telemetry.json into SQLite achieves 100% data parity."""
    assert os.path.exists(DEFAULT_JSON_PATH), f"Missing JSON dataset: {DEFAULT_JSON_PATH}"

    with open(DEFAULT_JSON_PATH, "r", encoding="utf-8") as f:
        original_json_data = json.load(f)

    imported_count = temp_db.import_from_json(DEFAULT_JSON_PATH, clear_existing=True)
    assert imported_count == len(original_json_data)
    assert temp_db.count() == len(original_json_data)

    sqlite_records = temp_db.get_all_sessions()
    assert len(sqlite_records) == len(original_json_data)

    for i, orig in enumerate(original_json_data):
        rec = sqlite_records[i]
        for field in TELEMETRY_FIELDS:
            assert rec[field] == orig[field], f"Mismatch at index {i} on field '{field}'"


def test_recent_sessions_limit(temp_db):
    """Verifies that get_recent_sessions respects limits and maintains chronological ordering."""
    records = [
        {
            "session_id": f"sess_{i}",
            "timestamp": 1700000000.0 + i,
            "elapsed_seconds": 50.0 + i,
            "rooms_cleared": float(i),
            "total_deaths": 0.0,
            "damage_dealt": 10.0 * i,
            "damage_taken": 5.0,
            "enemies_defeated": float(i),
            "pickups_collected": 1.0,
            "hazard_hits": 0.0,
            "exploration_efficiency": 1.0,
        }
        for i in range(10)
    ]
    temp_db.insert_sessions(records)
    assert temp_db.count() == 10

    recent_3 = temp_db.get_recent_sessions(limit=3)
    assert len(recent_3) == 3
    # Check that the 3 most recent (sess_7, sess_8, sess_9) are returned in order
    assert [r["session_id"] for r in recent_3] == ["sess_7", "sess_8", "sess_9"]


def test_export_to_json_roundtrip(temp_db):
    """Verifies round-trip export from SQLite to JSON preserves dataset content."""
    temp_db.import_from_json(DEFAULT_JSON_PATH, clear_existing=True)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        export_path = tmp.name

    try:
        exported_count = temp_db.export_to_json(export_path)
        assert exported_count == temp_db.count()

        with open(export_path, "r", encoding="utf-8") as f:
            exported_data = json.load(f)

        assert len(exported_data) == exported_count
        assert exported_data[0]["session_id"] == temp_db.get_all_sessions()[0]["session_id"]
    finally:
        if os.path.exists(export_path):
            os.remove(export_path)


def test_summary_stats_calculation(temp_db):
    """Verifies aggregate summary calculation across sessions."""
    records = [
        {
            "session_id": "sess_1",
            "timestamp": 1000.0,
            "elapsed_seconds": 100.0,
            "rooms_cleared": 4.0,
            "total_deaths": 2.0,
            "damage_dealt": 200.0,
            "damage_taken": 50.0,
            "enemies_defeated": 10.0,
            "pickups_collected": 2.0,
            "hazard_hits": 1.0,
            "exploration_efficiency": 2.0,
        },
        {
            "session_id": "sess_2",
            "timestamp": 2000.0,
            "elapsed_seconds": 200.0,
            "rooms_cleared": 6.0,
            "total_deaths": 0.0,
            "damage_dealt": 400.0,
            "damage_taken": 30.0,
            "enemies_defeated": 20.0,
            "pickups_collected": 4.0,
            "hazard_hits": 3.0,
            "exploration_efficiency": 4.0,
        },
    ]
    temp_db.insert_sessions(records)
    stats = temp_db.get_summary_stats()

    assert stats["total_sessions"] == 2.0
    assert stats["avg_elapsed_seconds"] == 150.0
    assert stats["avg_rooms_cleared"] == 5.0
    assert stats["avg_deaths"] == 1.0
    assert stats["avg_damage_dealt"] == 300.0
    assert stats["avg_damage_taken"] == 40.0
    assert stats["avg_enemies_defeated"] == 15.0
    assert stats["avg_exploration_efficiency"] == 3.0


def test_load_training_data_from_sqlite_integration(temp_db):
    """Verifies train_ppo_difficulty.load_training_data_from_sqlite reads from the database."""
    from train_ppo_difficulty import load_training_data_from_sqlite

    temp_db.import_from_json(DEFAULT_JSON_PATH, clear_existing=True)
    sessions = load_training_data_from_sqlite(temp_db.db_path)
    assert len(sessions) == 50
    assert sessions[0]["session_id"].startswith("sess_")
