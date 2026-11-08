"""Tests for ml_spike/telemetry_data/telemetry_db.py (Python layer over the game's telemetry DB).

The schema comes from godot_prototype/telemetry/schema.sql, the same file the game executes.
"""

import csv
import json
import os
import tempfile

import pytest
from ml_spike.telemetry_data.telemetry_db import (
    DEFAULT_JSON_PATH,
    JUDGE_FEATURES,
    TelemetryDatabase,
)

SESSION = {
    "id": "sess_100",
    "install_id": "abc123",
    "started_at": 1000,
    "mode": "adaptive",
    "elapsed_seconds": 30.0,
    "rooms_cleared": 1,
    "total_deaths": 0,
    "damage_dealt": 50.0,
    "damage_taken": 10.0,
    "enemies_defeated": 2,
}


def full_floor(session_id="sess_100", floor_num=1, **over):
    rec = {
        "session_id": session_id,
        "floor_num": floor_num,
        "phase": "adaptive",
        "completion_time": 42.5,
        "deaths": 1,
        "damage_dealt": 350.0,
        "damage_taken": 25.0,
        "rooms_total": 6,
        "rooms_visited": 5,
        "exploration_pct": 83.3,
        "rooms_cleared": 5,
        "enemies_defeated": 8,
        "hazards_hit": 1,
        "pickups_collected": 2,
        "enemy_health": 45.0,
        "enemy_damage": 12.0,
        "enemy_speed": 110.0,
        "enemy_aggro": 210.0,
        "hazard_density": 0.25,
        "resource_scarcity": 0.4,
        "room_count": 6,
        "archetype_complexity": 0.45,
        "archetype_mix_0": 0.2,
        "archetype_mix_1": 0.3,
        "archetype_mix_2": 0.1,
        "archetype_mix_3": 0.25,
        "archetype_mix_4": 0.15,
        "enemy_count_scale": 1.0,
        "created_at": 1001,
    }
    rec.update(over)
    return rec


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield TelemetryDatabase(db_path=os.path.join(tmpdir, "t.db"))


def test_schema_tables_and_view_exist(temp_db):
    with temp_db.connection() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    for name in ("sessions", "floors", "kills_by_archetype", "v_corpus", "schema_version"):
        assert name in names


def test_session_upsert_deduplicates(temp_db):
    temp_db.upsert_session(SESSION)
    temp_db.upsert_session({**SESSION, "elapsed_seconds": 50.0, "total_deaths": 1})
    assert temp_db.count_sessions() == 1
    stored = temp_db.get_session("sess_100")
    assert stored["elapsed_seconds"] == 50.0
    assert stored["total_deaths"] == 1
    assert stored["session_id"] == "sess_100"


def test_json_import_collapses_snapshots(temp_db):
    with open(DEFAULT_JSON_PATH, encoding="utf-8") as f:
        snaps = json.load(f)
    distinct = {s["session_id"] for s in snaps}
    n = temp_db.import_from_json(DEFAULT_JSON_PATH, clear_existing=True)
    assert n == len(distinct) == temp_db.count_sessions()
    # latest snapshot wins
    last = [s for s in snaps if s["session_id"] == snaps[-1]["session_id"]][-1]
    assert temp_db.get_session(last["session_id"])["elapsed_seconds"] == last["elapsed_seconds"]


def test_auto_populate_off_by_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = TelemetryDatabase(db_path=os.path.join(tmpdir, "t.db"))
        assert db.count_sessions() == 0
        db2 = TelemetryDatabase(db_path=os.path.join(tmpdir, "t2.db"), auto_populate=True)
        assert db2.count_sessions() > 0


def test_floor_upsert_and_kills(temp_db):
    temp_db.upsert_session(SESSION)
    temp_db.upsert_floor_record(full_floor(), kills={0: 3, 4: 6})
    temp_db.upsert_floor_record(full_floor(completion_time=40.0), kills={1: 2})  # re-record
    assert temp_db.count_floor_records() == 1
    row = temp_db.get_all_floor_records()[0]
    assert row["completion_time"] == 40.0
    assert (row["kills_0"], row["kills_1"], row["kills_4"]) == (0, 2, 0)


def test_missing_params_stored_as_null_not_invented(temp_db):
    temp_db.upsert_session(SESSION)
    rec = full_floor()
    del rec["enemy_damage"]
    temp_db.upsert_floor_record(rec)
    assert temp_db.get_all_floor_records()[0]["enemy_damage"] is None


def test_floor_requires_core_fields(temp_db):
    temp_db.upsert_session(SESSION)
    rec = full_floor()
    del rec["phase"]
    with pytest.raises(ValueError):
        temp_db.upsert_floor_record(rec)


def test_judge_training_data_skips_incomplete_rows(temp_db):
    temp_db.upsert_session(SESSION)
    temp_db.upsert_floor_record(full_floor(floor_num=1))
    temp_db.upsert_floor_record(full_floor(floor_num=2, archetype_complexity=None))
    data = temp_db.get_judge_training_data()
    assert data["sample_count"] == 1 and data["skipped"] == 1
    assert data["feature_names"] == JUDGE_FEATURES
    assert len(data["features"][0]) == len(JUDGE_FEATURES)
    assert data["targets"][0][3] == pytest.approx(350.0 / 25.0)


def test_sync_from_game_db_is_idempotent(temp_db):
    with tempfile.TemporaryDirectory() as tmpdir:
        game = TelemetryDatabase(db_path=os.path.join(tmpdir, "forge_telemetry.db"))
        game.upsert_session(SESSION)
        game.upsert_floor_record(full_floor(), kills={2: 1})
        assert temp_db.sync_from_game_db(game.db_path) == (1, 1)
        assert temp_db.sync_from_game_db(game.db_path) == (1, 1)
    assert temp_db.count_sessions() == 1 and temp_db.count_floor_records() == 1
    assert temp_db.get_all_floor_records()[0]["kills_2"] == 1


def test_sync_missing_source_raises(temp_db):
    with pytest.raises(FileNotFoundError):
        temp_db.sync_from_game_db("/nonexistent/forge_telemetry.db")


def test_locate_game_db_windows_path(monkeypatch):
    import ml_spike.telemetry_data.telemetry_db as mod

    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", "C:\\Users\\x\\AppData\\Roaming")
    d = TelemetryDatabase.game_userdata_dir()
    assert d.endswith(os.path.join("Godot", "app_userdata", mod.GODOT_APP_NAME))


def test_export_corpus_csv(temp_db):
    temp_db.upsert_session(SESSION)
    temp_db.upsert_floor_record(full_floor(floor_num=1))
    temp_db.upsert_floor_record(full_floor(floor_num=2))
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "c.csv")
        assert temp_db.export_corpus_csv(out) == 2
        with open(out, encoding="utf-8") as f:
            rows = list(csv.reader(f))
    assert len(rows) == 3 and "archetype_complexity" in rows[0]


def test_load_training_data_from_sqlite(temp_db):
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from train_ppo_difficulty import load_training_data_from_sqlite

    temp_db.upsert_session(SESSION)
    temp_db.upsert_floor_record(full_floor())
    data = load_training_data_from_sqlite(temp_db.db_path)
    assert data["sample_count"] == 1


def test_judge_training_data_excludes_manual_override_floors(temp_db):
    temp_db.upsert_session(SESSION)
    temp_db.upsert_floor_record(full_floor(floor_num=1))
    temp_db.upsert_floor_record(full_floor(floor_num=2, manual_override=1))
    data = temp_db.get_judge_training_data()
    assert data["sample_count"] == 1
    assert data["excluded_manual_override"] == 1 and data["skipped"] == 0
    rows = temp_db.get_all_floor_records()
    assert [r["manual_override"] for r in rows] == [0, 1]  # still exported, just flagged


def test_sync_from_schema_v1_game_db(temp_db):
    """A game DB created before migration v2 (no manual_override column) still syncs."""
    import sqlite3

    from ml_spike.analysis import export_telemetry as et

    bootstrap, migs = et.load_schema()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "forge_telemetry.db")
        conn = sqlite3.connect(path)
        for stmt in bootstrap:
            conn.execute(stmt)
        version, stmts = migs[0]
        assert version == 1
        for stmt in stmts:
            conn.execute(stmt)
        conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (1, 0)")
        q = et.load_queries()
        cols = et.insert_columns(q["upsert_session"])
        conn.execute(q["upsert_session"].split(" ON CONFLICT")[0],
                     [SESSION.get(c, 0 if c != "install_id" else "x") for c in cols])  # fmt: skip
        fl = full_floor(created_at=1)
        v1_cols = [c for c in et.insert_columns(q["insert_floor"]) if c != "manual_override"]
        conn.execute(
            f"INSERT INTO floors ({', '.join(v1_cols)}) VALUES ({', '.join('?' * len(v1_cols))})",
            [fl.get(c) for c in v1_cols],
        )
        conn.commit()
        conn.close()
        assert temp_db.sync_from_game_db(path) == (1, 1)
    row = temp_db.get_all_floor_records()[0]
    assert row["manual_override"] == 0 and row["completion_time"] == 42.5


def test_opening_v1_db_migrates_to_latest(tmp_path):
    """Opening an existing v1 database adds manual_override = 0 to its rows and rebuilds v_corpus."""
    import sqlite3

    from ml_spike.analysis import export_telemetry as et

    bootstrap, migs = et.load_schema()
    path = tmp_path / "forge_telemetry.db"
    conn = sqlite3.connect(path)
    for stmt in bootstrap + migs[0][1]:
        conn.execute(stmt)
    conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (1, 0)")
    conn.execute("INSERT INTO sessions (id, install_id, started_at) VALUES ('s1', 'i', 1)")
    conn.execute(
        "INSERT INTO floors (session_id, floor_num, phase, completion_time, created_at) "
        "VALUES ('s1', 1, 'adaptive', 10.0, 1)"
    )
    conn.commit()
    conn.close()
    db = TelemetryDatabase(db_path=str(path))
    rows = db.get_all_floor_records()
    assert len(rows) == 1 and rows[0]["manual_override"] == 0
    with db.connection() as c:
        assert c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == migs[-1][0]
