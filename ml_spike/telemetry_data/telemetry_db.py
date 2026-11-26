"""FORGE — Telemetry SQLite Database Manager (Python side).
-----------------------------------------------------------
Python access layer over the SAME database the game writes (``user://forge_telemetry.db``).
The schema and SQL are not duplicated here: they are loaded from
``godot_prototype/telemetry/{schema,queries}.sql`` (via ``ml_spike/analysis/export_telemetry.py``),
which TelemetryLogger.gd also executes, so the two sides cannot drift apart.

Tables (see schema.sql): ``sessions`` (one row per play session), ``floors`` (one row per finished
floor: outcome + the 8 difficulty parameters, 5-archetype mix, policy obs/action, frame times),
``kills_by_archetype``, and the flattened ``v_corpus`` view used for the Judge model.

Typical use:
    db = TelemetryDatabase()                      # ml_spike/telemetry_data/forge_telemetry.db
    db.sync_from_game_db()                        # pull new rows from the game's user:// DB
    data = db.get_judge_training_data()           # features/targets, incomplete rows skipped
    db.export_corpus_csv("corpus.csv")
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
if str(_ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_DIR))

import export_telemetry as _et  # noqa: E402  (shared schema/query loader)

GAME_DB_FILENAME = "forge_telemetry.db"
GODOT_APP_NAME = "FORGE - Adaptive Dungeon Prototype"  # project.godot -> application/config/name
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), GAME_DB_FILENAME)
# Legacy flat-JSON snapshots (pre-SQLite). Sample data only; never auto-imported.
DEFAULT_JSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "session_telemetry.json"
)

SESSION_COLUMNS = [
    "id",
    "install_id",
    "started_at",
    "ended_at",
    "game_version",
    "mode",
    "policy_version",
    "consent",
    "elapsed_seconds",
    "rooms_cleared",
    "total_deaths",
    "damage_dealt",
    "damage_taken",
    "enemies_defeated",
    "pickups_collected",
    "hazard_hits",
]

# Judge model: settings the floor was played with -> outcome.
JUDGE_FEATURES = [
    "enemy_health",
    "enemy_damage",
    "enemy_speed",
    "enemy_aggro",
    "hazard_density",
    "resource_scarcity",
    "room_count",
    "archetype_complexity",
    "archetype_mix_0",
    "archetype_mix_1",
    "archetype_mix_2",
    "archetype_mix_3",
    "archetype_mix_4",
    "enemy_count_scale",
]
JUDGE_TARGETS = ["completion_time", "deaths", "damage_taken", "damage_exchange_ratio"]

# Floor columns that must be supplied (NOT NULL without a default in schema.sql).
_FLOOR_REQUIRED = ["session_id", "floor_num", "phase", "completion_time"]


class TelemetryDatabase:
    """SQLite store of sessions and per-floor outcomes, shared schema with the game."""

    def __init__(self, db_path: Optional[str] = None, auto_populate: bool = False):
        """auto_populate imports the bundled legacy SAMPLE JSON into an empty DB. It is off by
        default so sample sessions never mix with real playtest data."""
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self._queries = _et.load_queries()
        self._init_db()
        if auto_populate and self.count_sessions() == 0 and os.path.exists(DEFAULT_JSON_PATH):
            self.import_from_json(DEFAULT_JSON_PATH)

    @contextmanager
    def connection(self):
        """Yields a connection with foreign keys on; always closed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            _et.migrate(conn)
        finally:
            conn.close()

    # ------------------------------------------------------------------ sessions
    @staticmethod
    def _session_values(record: Dict[str, Any]) -> List[Any]:
        sid = record.get("id", record.get("session_id"))
        if not sid:
            raise ValueError("session record needs 'id' (or 'session_id')")
        defaults = {
            "install_id": "unknown",
            "started_at": int(float(record.get("timestamp", 0) or 0)),
            "ended_at": None,
            "game_version": "",
            "mode": "unknown",
            "policy_version": "",
            "consent": 0,
        }
        out: List[Any] = [sid]
        for col in SESSION_COLUMNS[1:]:
            val = record.get(col, defaults.get(col, 0))
            if col in ("rooms_cleared", "total_deaths", "enemies_defeated"):
                val = int(val or 0)
            elif col in ("pickups_collected", "hazard_hits", "consent"):
                val = int(val or 0)
            out.append(val)
        return out

    def upsert_session(self, record: Dict[str, Any]) -> None:
        """Insert or update one session (keyed by id). Repeated snapshots never duplicate rows."""
        with self.connection() as conn, conn:
            conn.execute(self._queries["upsert_session"], self._session_values(record))

    def upsert_sessions(self, records: Iterable[Dict[str, Any]]) -> int:
        rows = [self._session_values(r) for r in records]
        with self.connection() as conn, conn:
            conn.executemany(self._queries["upsert_session"], rows)
        return len(rows)

    def count_sessions(self) -> int:
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY started_at, id").fetchall()
        return [self._session_dict(r) for r in rows]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(self._queries["select_session"], (session_id,)).fetchone()
        return self._session_dict(row) if row else None

    @staticmethod
    def _session_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["session_id"] = d["id"]  # alias kept for older callers
        return d

    # ------------------------------------------------------------------ floors
    def upsert_floor_record(
        self, record: Dict[str, Any], kills: Optional[Dict[int, int]] = None
    ) -> int:
        """Insert or replace one floor row (unique per session_id + floor_num) and its kill counts.

        Difficulty parameters that are missing are stored as NULL -- never invented -- so
        incomplete rows can be filtered out of the Judge corpus instead of corrupting it.
        The session row must exist (call upsert_session first). Returns the floor id.
        """
        rec = dict(record)
        if "floor_num" not in rec and "floor_number" in rec:
            rec["floor_num"] = rec["floor_number"]
        missing = [c for c in _FLOOR_REQUIRED if rec.get(c) is None]
        if missing:
            raise ValueError(f"floor record missing required fields: {missing}")
        rec.setdefault("created_at", int(float(rec.get("timestamp", 0) or 0)))
        cols = _et.insert_columns(self._queries["insert_floor"])
        not_null_defaults = {
            "deaths": 0,
            "damage_taken": 0.0,
            "damage_dealt": 0.0,
            "rooms_total": 0,
            "rooms_visited": 0,
            "exploration_pct": 0.0,
            "rooms_cleared": 0,
            "enemies_defeated": 0,
            "hazards_hit": int(rec.get("hazard_hits", 0) or 0),
            "pickups_collected": 0,
            # Rows synced from a schema-v1 game DB have no manual_override column.
            "manual_override": int(rec.get("manual_override") or 0),
            # Rows from a schema-v1/v2 game DB have no generator column (all were FORGE layouts).
            "generator": rec.get("generator") or "forge",
        }
        values = [rec.get(c, not_null_defaults.get(c)) for c in cols]
        with self.connection() as conn, conn:
            conn.execute(
                "DELETE FROM floors WHERE session_id = ? AND floor_num = ?",
                (rec["session_id"], int(rec["floor_num"])),
            )
            cur = conn.execute(self._queries["insert_floor"], values)
            floor_id = cur.lastrowid
            for idx, count in (kills or {}).items():
                conn.execute(self._queries["insert_kill"], (floor_id, int(idx), int(count)))
        return floor_id

    def count_floor_records(self) -> int:
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM floors").fetchone()[0]

    def get_all_floor_records(self) -> List[Dict[str, Any]]:
        """One flattened row per floor (v_corpus: session fields, floor columns, kills_0..4)."""
        with self.connection() as conn:
            rows = conn.execute(self._queries["export_corpus"]).fetchall()
        return [dict(r) for r in rows]

    def get_judge_training_data(self, consented_only: bool = False) -> Dict[str, Any]:
        """Features (settings the floor was played with) -> targets (outcome) for the Judge.

        Rows with any NULL feature/target are skipped and counted in 'skipped'.
        Floors played with developer overrides (manual_override = 1: Defense Panel sliders/presets,
        regenerate, auto-kill) are left out and counted in 'excluded_manual_override'.
        damage_exchange_ratio = damage_dealt / max(1, damage_taken).
        """
        key = "export_corpus_consented" if consented_only else "export_corpus"
        with self.connection() as conn:
            rows = [dict(r) for r in conn.execute(self._queries[key]).fetchall()]
        features: List[List[float]] = []
        targets: List[List[float]] = []
        skipped = 0
        excluded_override = 0
        for r in rows:
            if int(r.get("manual_override") or 0) == 1:
                excluded_override += 1
                continue
            r["damage_exchange_ratio"] = float(r["damage_dealt"] or 0.0) / max(
                1.0, float(r["damage_taken"] or 0.0)
            )
            if any(r.get(f) is None for f in JUDGE_FEATURES + JUDGE_TARGETS):
                skipped += 1
                continue
            features.append([float(r[f]) for f in JUDGE_FEATURES])
            targets.append([float(r[t]) for t in JUDGE_TARGETS])
        return {
            "features": features,
            "targets": targets,
            "feature_names": list(JUDGE_FEATURES),
            "target_names": list(JUDGE_TARGETS),
            "sample_count": len(features),
            "skipped": skipped,
            "excluded_manual_override": excluded_override,
        }

    # ------------------------------------------------------------------ import / export / sync
    def import_from_json(
        self, json_path: Optional[str] = None, clear_existing: bool = False
    ) -> int:
        """Import legacy flat-JSON session snapshots. Multiple snapshots of one session collapse to
        one row (the latest snapshot wins). Returns the number of distinct sessions imported."""
        path = json_path or DEFAULT_JSON_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"JSON telemetry not found at: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array in {path}, got {type(data)}")
        latest: Dict[str, Dict[str, Any]] = {}
        for snap in data:
            if isinstance(snap, dict) and snap.get("session_id"):
                latest[snap["session_id"]] = snap  # later snapshots overwrite earlier ones
        if clear_existing:
            with self.connection() as conn, conn:
                conn.execute("DELETE FROM sessions")
        return self.upsert_sessions(latest.values())

    def export_to_json(self, json_path: Optional[str] = None) -> int:
        """Export session rows to a JSON array. Returns the number written."""
        path = json_path or DEFAULT_JSON_PATH
        sessions = self.get_all_sessions()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=4)
        return len(sessions)

    def export_corpus_csv(self, csv_path: str, consented_only: bool = False) -> int:
        """One CSV row per floor (same columns as the game's export). Returns rows written."""
        return _et.export_corpus_csv(self.db_path, csv_path, consented_only)

    def sync_from_game_db(self, source_db_path: Optional[str] = None) -> Tuple[int, int]:
        """Copy sessions, floors and kill counts from the game's forge_telemetry.db into this DB.
        Idempotent: re-syncing updates rows instead of duplicating them.
        Returns (sessions_synced, floors_synced)."""
        src = source_db_path or self.locate_game_db()
        if not src or not os.path.exists(src):
            raise FileNotFoundError(
                "Game telemetry DB not found. Play the game with godot-sqlite installed, or pass "
                "source_db_path explicitly."
            )
        if os.path.abspath(src) == os.path.abspath(self.db_path):
            return (0, 0)
        sconn = sqlite3.connect(src)
        sconn.row_factory = sqlite3.Row
        try:
            sessions = [dict(r) for r in sconn.execute("SELECT * FROM sessions").fetchall()]
            floors = [dict(r) for r in sconn.execute("SELECT * FROM floors").fetchall()]
            kills: Dict[int, Dict[int, int]] = {}
            for r in sconn.execute("SELECT floor_id, archetype_idx, count FROM kills_by_archetype"):
                kills.setdefault(r["floor_id"], {})[r["archetype_idx"]] = r["count"]
        finally:
            sconn.close()
        self.upsert_sessions(sessions)
        for fl in floors:
            fid = fl.pop("id")
            self.upsert_floor_record(fl, kills.get(fid, {}))
        return (len(sessions), len(floors))

    @staticmethod
    def game_userdata_dir() -> Optional[str]:
        """Godot's user:// directory for this project on the current OS."""
        system = platform.system()
        if system == "Windows":
            appdata = os.environ.get("APPDATA", "")
            return (
                os.path.join(appdata, "Godot", "app_userdata", GODOT_APP_NAME) if appdata else None
            )
        home = os.path.expanduser("~")
        if system == "Darwin":
            return os.path.join(
                home, "Library", "Application Support", "Godot", "app_userdata", GODOT_APP_NAME
            )
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
        return os.path.join(base, "godot", "app_userdata", GODOT_APP_NAME)

    @classmethod
    def locate_game_db(cls) -> Optional[str]:
        """Path of the game's user://forge_telemetry.db if it exists, else None."""
        d = cls.game_userdata_dir()
        if d:
            path = os.path.join(d, GAME_DB_FILENAME)
            if os.path.exists(path):
                return path
        return None

    def get_summary_stats(self) -> Dict[str, float]:
        """Aggregates over sessions and floors."""
        with self.connection() as conn:
            s = conn.execute(
                """SELECT COUNT(*) AS n, AVG(elapsed_seconds) AS t, AVG(total_deaths) AS d,
                          AVG(damage_dealt) AS dd, AVG(damage_taken) AS dt,
                          AVG(enemies_defeated) AS e FROM sessions"""
            ).fetchone()
            f = conn.execute(
                "SELECT COUNT(*) AS n, AVG(completion_time) AS t, AVG(exploration_pct) AS x FROM floors"
            ).fetchone()
        if not s["n"]:
            return {"total_sessions": 0, "total_floors": float(f["n"] or 0)}
        return {
            "total_sessions": float(s["n"]),
            "total_floors": float(f["n"] or 0),
            "avg_elapsed_seconds": round(float(s["t"] or 0), 2),
            "avg_deaths": round(float(s["d"] or 0), 2),
            "avg_damage_dealt": round(float(s["dd"] or 0), 2),
            "avg_damage_taken": round(float(s["dt"] or 0), 2),
            "avg_enemies_defeated": round(float(s["e"] or 0), 2),
            "avg_floor_time": round(float(f["t"] or 0), 2),
            "avg_exploration_pct": round(float(f["x"] or 0), 2),
        }


if __name__ == "__main__":
    db = TelemetryDatabase()
    game_db = TelemetryDatabase.locate_game_db()
    if game_db:
        n_s, n_f = db.sync_from_game_db(game_db)
        print(f"Synced {n_s} sessions / {n_f} floors from {game_db} into {db.db_path}")
    else:
        print(f"No game DB found under {TelemetryDatabase.game_userdata_dir()}")
    for k, v in db.get_summary_stats().items():
        print(f"  {k}: {v}")
