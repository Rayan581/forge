"""Authoritative check of the telemetry SQL shared with Godot (godot-sqlite).

The game executes godot_prototype/telemetry/schema.sql and queries.sql through godot-sqlite, which is
not available in every environment, so this test runs the *same* strings through Python's stdlib
sqlite3 using the same positional `?` binding order the GDScript derives from each INSERT column list.
"""

import csv
import sqlite3

import pytest
from ml_spike.analysis.export_telemetry import (
    corpus_header,
    export_corpus_csv,
    insert_columns,
    load_queries,
    load_schema,
    migrate,
    split_statements,
)

Q = load_queries()
FLOOR_COLS = insert_columns(Q["insert_floor"])
SESSION_COLS = insert_columns(Q["upsert_session"])


def _session(sid="sess_1", install="a" * 32, consent=1, mode="adaptive"):
    return {
        "id": sid,
        "install_id": install,
        "started_at": 1_700_000_000,
        "ended_at": 1_700_000_100,
        "game_version": "test-1.0",
        "mode": mode,
        "policy_version": "md5:abc",
        "consent": consent,
        "elapsed_seconds": 100.5,
        "rooms_cleared": 7,
        "total_deaths": 2,
        "damage_dealt": 300.25,
        "damage_taken": 120.5,
        "enemies_defeated": 20,
        "pickups_collected": 3,
        "hazard_hits": 4,
    }


def _floor(sid, n, with_policy=True):
    row = {
        "session_id": sid,
        "floor_num": n,
        "phase": "calibration" if n <= 5 else "adaptive",
        "completion_time": 40.0 + n,
        "deaths": n % 2,
        "damage_taken": 10.5 * n,
        "damage_dealt": 50.25 * n,
        "player_max_hp": 100.0,
        "rooms_total": 5 + n,
        "rooms_visited": 3 + n,
        "exploration_pct": 100.0 * (3 + n) / (5 + n),
        "rooms_cleared": n,
        "enemies_defeated": 4 * n,
        "hazards_hit": n,
        "pickups_collected": 2,
        "enemy_health": 60.0 + n,
        "enemy_damage": 20.0,
        "enemy_speed": 125.0,
        "enemy_aggro": 240.0,
        "hazard_density": 0.35,
        "resource_scarcity": 0.4,
        "room_count": 6,
        "archetype_complexity": 0.5,
        "enemy_count_scale": 1.0,
        "difficulty_score": 55.5,
        "frame_avg_ms": 16.6,
        "frame_p95_ms": 18.0,
        "frame_max_ms": 40.0,
        "perceived_difficulty": None,
        "created_at": 1_700_000_050 + n,
        "manual_override": 0,
    }
    mix = [0.1, 0.2, 0.3, 0.25, 0.15]
    for a in range(5):
        row[f"archetype_mix_{a}"] = mix[a]
    for k in range(8):
        row[f"obs_{k}"] = 0.1 * k if with_policy else None
        row[f"action_{k}"] = -1 + 0.25 * k if with_policy else None
    return row


def _bind(cols, row):
    return [row.get(c) for c in cols]


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    migrate(c)
    yield c
    c.close()


def _write_floor(conn, row, kills):
    """Same sequence as SqliteBackend.save_floor: one transaction per floor."""
    with conn:
        cur = conn.execute(Q["insert_floor"], _bind(FLOOR_COLS, row))
        for idx, count in kills.items():
            if count > 0:
                conn.execute(Q["insert_kill"], [cur.lastrowid, idx, count])


def test_all_queries_have_matching_placeholder_counts():
    for name, sql in Q.items():
        if name.startswith(("insert_", "upsert_")) and "VALUES" in sql:
            cols = insert_columns(sql)
            values_part = sql.split("VALUES", 1)[1].split(")", 1)[0]
            assert values_part.count("?") == len(cols), name
    assert len(FLOOR_COLS) == 52
    assert len(set(FLOOR_COLS)) == len(FLOOR_COLS)


def test_splitter_drops_comments_and_empty_parts():
    assert split_statements("-- hi; there\nSELECT 1;\n\n-- x\nSELECT 2;") == [
        "SELECT 1",
        "SELECT 2",
    ]


def test_migrations_are_versioned_and_idempotent(conn):
    _, migs = load_schema()
    latest = migs[-1][0]
    assert conn.execute(Q["get_schema_version"]).fetchone()[0] == latest
    assert migrate(conn) == latest  # re-running applies nothing
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    assert len(rows) == len(migs)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"schema_version", "sessions", "floors", "kills_by_archetype", "meta"} <= tables


def test_foreign_key_columns_are_indexed(conn):
    idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"idx_floors_session", "idx_kills_floor"} <= idx


def test_floor_columns_cover_judge_corpus_fields(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(floors)")}
    needed = {
        "phase", "completion_time", "deaths", "damage_taken", "damage_dealt", "player_max_hp",
        "rooms_total", "rooms_visited", "exploration_pct", "rooms_cleared", "enemies_defeated",
        "hazards_hit", "pickups_collected", "enemy_health", "enemy_damage", "enemy_speed",
        "enemy_aggro", "hazard_density", "resource_scarcity", "room_count",
        "archetype_complexity", "enemy_count_scale", "difficulty_score", "frame_avg_ms",
        "frame_p95_ms", "frame_max_ms", "perceived_difficulty", "created_at",
    }  # fmt: skip
    needed |= {f"archetype_mix_{i}" for i in range(5)}
    needed |= {f"action_{i}" for i in range(8)} | {f"obs_{i}" for i in range(8)}
    assert needed <= cols
    assert set(FLOOR_COLS) <= cols | {"session_id"}
    sess_cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
    assert {
        "id",
        "started_at",
        "game_version",
        "mode",
        "policy_version",
        "consent",
        "install_id",
    } <= sess_cols


def test_three_floors_round_trip(conn):
    conn.execute(Q["upsert_session"], _bind(SESSION_COLS, _session()))
    kills = [{0: 2, 4: 3}, {}, {2: 1, 1: 5}]
    rows = [_floor("sess_1", n, with_policy=(n != 2)) for n in (1, 2, 3)]
    for row, k in zip(rows, kills):
        _write_floor(conn, row, k)

    conn.row_factory = sqlite3.Row
    got = conn.execute(Q["select_floors"], ["sess_1"]).fetchall()
    assert [g["floor_num"] for g in got] == [1, 2, 3]
    for g, want in zip(got, rows):
        for col, val in want.items():
            if val is None:
                assert g[col] is None, col
            elif isinstance(val, float):
                assert g[col] == pytest.approx(val, abs=1e-4), col
            else:
                assert g[col] == val, col
    assert got[1]["obs_0"] is None and got[1]["action_7"] is None  # no policy step -> NULL
    for g, want_kills in zip(got, kills):
        read = {r["archetype_idx"]: r["count"] for r in conn.execute(Q["select_kills"], [g["id"]])}
        assert read == {k: v for k, v in want_kills.items() if v > 0}

    conn.execute(Q["set_perceived_difficulty"], [4.5, "sess_1", 2])
    assert conn.execute(Q["select_floors"], ["sess_1"]).fetchall()[1]["perceived_difficulty"] == 4.5


def test_session_upsert_updates_in_place(conn):
    conn.execute(Q["upsert_session"], _bind(SESSION_COLS, _session()))
    later = _session()
    later.update(ended_at=1_700_000_999, rooms_cleared=9, mode="static")
    conn.execute(Q["upsert_session"], _bind(SESSION_COLS, later))
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"] == 1
    row = conn.execute(Q["select_session"], ["sess_1"]).fetchone()
    assert (row["ended_at"], row["rooms_cleared"], row["mode"]) == (1_700_000_999, 9, "static")


def test_constraints_reject_bad_rows(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):  # floor for an unknown session
        _write_floor(conn, _floor("nope", 1), {})
    conn.execute(Q["upsert_session"], _bind(SESSION_COLS, _session()))
    _write_floor(conn, _floor("sess_1", 1), {})
    with pytest.raises(sqlite3.IntegrityError):  # duplicate (session, floor)
        _write_floor(conn, _floor("sess_1", 1), {})
    bad = _floor("sess_1", 2)
    bad["phase"] = "bogus"
    with pytest.raises(sqlite3.IntegrityError):
        _write_floor(conn, bad, {})
    # the failed transactions left nothing behind
    assert conn.execute("SELECT COUNT(*) FROM floors").fetchone()[0] == 1


def test_legacy_import_is_ignored_when_session_exists(conn):
    cols = insert_columns(Q["insert_legacy_session"])
    conn.execute(Q["upsert_session"], _bind(SESSION_COLS, _session()))
    legacy = _session(sid="sess_1", install="legacy", mode="unknown")
    conn.execute(Q["insert_legacy_session"], _bind(cols, legacy))
    assert (
        conn.execute("SELECT install_id FROM sessions WHERE id='sess_1'").fetchone()[0] == "a" * 32
    )
    conn.execute(
        Q["insert_legacy_session"],
        _bind(cols, _session(sid="old", install="legacy", mode="unknown")),
    )
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
    assert conn.execute(Q["get_meta"], ["legacy_json_imported"]).fetchone() is None
    conn.execute(Q["set_meta"], ["legacy_json_imported", "1 sessions"])
    conn.execute(Q["set_meta"], ["legacy_json_imported", "2 sessions"])
    assert conn.execute(Q["get_meta"], ["legacy_json_imported"]).fetchone()[0] == "2 sessions"


def test_corpus_csv_export(tmp_path):
    db = tmp_path / "forge_telemetry.db"
    c = sqlite3.connect(db)
    migrate(c)
    c.execute(Q["upsert_session"], _bind(SESSION_COLS, _session("sess_a", consent=1)))
    c.execute(
        Q["upsert_session"], _bind(SESSION_COLS, _session("sess_b", install="b" * 32, consent=0))
    )
    c.commit()
    for n in (1, 2, 3):
        _write_floor(c, _floor("sess_a", n), {0: n, 3: 1})
    _write_floor(c, _floor("sess_b", 1), {})
    header = corpus_header(c)
    c.close()

    out = tmp_path / "corpus.csv"
    assert export_corpus_csv(db, out) == 4
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 4
    assert list(rows[0].keys()) == header
    assert header[:6] == [
        "session_id",
        "install_id",
        "mode",
        "policy_version",
        "game_version",
        "consent",
    ]
    assert header[-5:] == [f"kills_{i}" for i in range(5)]
    # same column rule the GDScript JSON fallback uses: session fields + floor cols (-session_id) + kills
    expected = header[:6] + [c for c in FLOOR_COLS if c != "session_id"] + header[-5:]
    assert header == expected
    first = rows[0]
    assert (first["session_id"], first["floor_num"], first["kills_0"], first["kills_3"]) == (
        "sess_a",
        "1",
        "1",
        "1",
    )
    assert float(first["completion_time"]) == pytest.approx(41.0)
    assert first["perceived_difficulty"] == ""  # NULL -> empty cell
    assert rows[2]["kills_0"] == "3" and rows[2]["kills_4"] == "0"
    assert export_corpus_csv(db, tmp_path / "c2.csv", consented_only=True) == 3
