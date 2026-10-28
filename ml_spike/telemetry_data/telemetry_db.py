"""FORGE — Telemetry SQLite Database Manager
-----------------------------------------
Provides zero-configuration, local SQLite persistence for player session telemetry,
per-floor difficulty adaptation traces, and empirical training data for both PPO
and the supervised Judge model (TreeSHAP).
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_telemetry.db")
DEFAULT_JSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "session_telemetry.json"
)

CREATE_SESSION_TABLE_SQL = """
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
    exploration_efficiency REAL NOT NULL,
    rooms_per_minute REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_FLOOR_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS floor_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    floor_number INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    -- Outcome metrics
    completion_time REAL NOT NULL,
    deaths INTEGER NOT NULL,
    damage_dealt REAL NOT NULL,
    damage_taken REAL NOT NULL,
    damage_exchange_ratio REAL DEFAULT 0.0,
    rooms_cleared INTEGER NOT NULL,
    enemies_defeated INTEGER NOT NULL,
    hazard_hits INTEGER NOT NULL,
    pickups_collected INTEGER NOT NULL,
    -- 8 Difficulty settings applied to this floor
    enemy_health REAL NOT NULL,
    enemy_damage REAL NOT NULL,
    enemy_speed REAL NOT NULL,
    enemy_aggro REAL NOT NULL,
    hazard_density REAL NOT NULL,
    resource_scarcity REAL NOT NULL,
    room_count REAL NOT NULL,
    enemy_count_scale REAL DEFAULT 1.0,
    -- Enemy archetype mix
    crawler_ratio REAL DEFAULT 0.5,
    pyromancer_ratio REAL DEFAULT 0.5,
    archetype_mix TEXT DEFAULT '',
    -- Policy observation and action vectors
    observation_vector TEXT DEFAULT '',
    action_vector TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, floor_number)
);
"""

CREATE_INDICES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON session_telemetry(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_floor_session_num ON floor_telemetry(session_id, floor_number);",
]

SESSION_FIELDS = [
    "session_id",
    "timestamp",
    "elapsed_seconds",
    "rooms_cleared",
    "total_deaths",
    "damage_dealt",
    "damage_taken",
    "enemies_defeated",
    "pickups_collected",
    "hazard_hits",
    "exploration_efficiency",
    "rooms_per_minute",
]

FLOOR_FIELDS = [
    "session_id",
    "floor_number",
    "timestamp",
    "completion_time",
    "deaths",
    "damage_dealt",
    "damage_taken",
    "damage_exchange_ratio",
    "rooms_cleared",
    "enemies_defeated",
    "hazard_hits",
    "pickups_collected",
    "enemy_health",
    "enemy_damage",
    "enemy_speed",
    "enemy_aggro",
    "hazard_density",
    "resource_scarcity",
    "room_count",
    "enemy_count_scale",
    "crawler_ratio",
    "pyromancer_ratio",
    "archetype_mix",
    "observation_vector",
    "action_vector",
]


class TelemetryDatabase:
    """Manages SQLite storage and retrieval of player sessions and floor-by-floor difficulty outcomes."""

    def __init__(self, db_path: Optional[str] = None, auto_populate: bool = True):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._init_db()
        if auto_populate and self.count_sessions() == 0 and os.path.exists(DEFAULT_JSON_PATH):
            self.import_from_json(DEFAULT_JSON_PATH)

    @contextmanager
    def connection(self):
        """Context manager that yields an active SQLite connection and always closes it cleanly."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_SESSION_TABLE_SQL)
            cursor.execute(CREATE_FLOOR_TABLE_SQL)
            for index_sql in CREATE_INDICES_SQL:
                cursor.execute(index_sql)
            conn.commit()

    # -------------------------------------------------------------------------
    # Session-Level Telemetry
    # -------------------------------------------------------------------------
    def upsert_session(self, record: Dict[str, Any]) -> None:
        """Inserts or updates a session record keyed by unique session_id (deduplication)."""
        # exploration_efficiency represents rooms cleared per minute
        elapsed_sec = float(record.get("elapsed_seconds", 0.0))
        rooms = float(record.get("rooms_cleared", 0.0))
        calculated_rpm = round(rooms / max(1.0, elapsed_sec / 60.0), 2)
        rpm = float(
            record.get("rooms_per_minute", record.get("exploration_efficiency", calculated_rpm))
        )

        sql = """
        INSERT INTO session_telemetry (
            session_id, timestamp, elapsed_seconds, rooms_cleared, total_deaths,
            damage_dealt, damage_taken, enemies_defeated, pickups_collected,
            hazard_hits, exploration_efficiency, rooms_per_minute, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            timestamp = excluded.timestamp,
            elapsed_seconds = excluded.elapsed_seconds,
            rooms_cleared = excluded.rooms_cleared,
            total_deaths = excluded.total_deaths,
            damage_dealt = excluded.damage_dealt,
            damage_taken = excluded.damage_taken,
            enemies_defeated = excluded.enemies_defeated,
            pickups_collected = excluded.pickups_collected,
            hazard_hits = excluded.hazard_hits,
            exploration_efficiency = excluded.exploration_efficiency,
            rooms_per_minute = excluded.rooms_per_minute,
            updated_at = CURRENT_TIMESTAMP;
        """
        values = (
            str(record.get("session_id", "")),
            float(record.get("timestamp", 0.0)),
            elapsed_sec,
            rooms,
            float(record.get("total_deaths", 0.0)),
            float(record.get("damage_dealt", 0.0)),
            float(record.get("damage_taken", 0.0)),
            float(record.get("enemies_defeated", 0.0)),
            float(record.get("pickups_collected", 0.0)),
            float(record.get("hazard_hits", 0.0)),
            rpm,
            rpm,
        )
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()

    def upsert_sessions(self, records: List[Dict[str, Any]]) -> int:
        """Batch-upserts session records inside a single transaction."""
        for rec in records:
            self.upsert_session(rec)
        return len(records)

    def count_sessions(self) -> int:
        """Returns the number of unique recorded sessions."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM session_telemetry;")
            return cursor.fetchone()[0]

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Returns all distinct session records in chronological order."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM session_telemetry ORDER BY timestamp ASC;")
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a single session by session_id."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM session_telemetry WHERE session_id = ?;", (session_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    # -------------------------------------------------------------------------
    # Floor-Level Telemetry (For Judge Model: "these settings -> this outcome")
    # -------------------------------------------------------------------------
    def upsert_floor_record(self, record: Dict[str, Any]) -> int:
        """Inserts or updates a per-floor performance slice for Judge model training."""
        obs = record.get("observation_vector", "")
        if isinstance(obs, (list, tuple)):
            obs = json.dumps(obs)
        act = record.get("action_vector", "")
        if isinstance(act, (list, tuple)):
            act = json.dumps(act)

        sql = """
        INSERT INTO floor_telemetry (
            session_id, floor_number, timestamp, completion_time, deaths,
            damage_dealt, damage_taken, damage_exchange_ratio, rooms_cleared,
            enemies_defeated, hazard_hits, pickups_collected, enemy_health,
            enemy_damage, enemy_speed, enemy_aggro, hazard_density,
            resource_scarcity, room_count, enemy_count_scale, crawler_ratio,
            pyromancer_ratio, archetype_mix, observation_vector, action_vector
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, floor_number) DO UPDATE SET
            timestamp = excluded.timestamp,
            completion_time = excluded.completion_time,
            deaths = excluded.deaths,
            damage_dealt = excluded.damage_dealt,
            damage_taken = excluded.damage_taken,
            damage_exchange_ratio = excluded.damage_exchange_ratio,
            rooms_cleared = excluded.rooms_cleared,
            enemies_defeated = excluded.enemies_defeated,
            hazard_hits = excluded.hazard_hits,
            pickups_collected = excluded.pickups_collected,
            enemy_health = excluded.enemy_health,
            enemy_damage = excluded.enemy_damage,
            enemy_speed = excluded.enemy_speed,
            enemy_aggro = excluded.enemy_aggro,
            hazard_density = excluded.hazard_density,
            resource_scarcity = excluded.resource_scarcity,
            room_count = excluded.room_count,
            enemy_count_scale = excluded.enemy_count_scale,
            crawler_ratio = excluded.crawler_ratio,
            pyromancer_ratio = excluded.pyromancer_ratio,
            archetype_mix = excluded.archetype_mix,
            observation_vector = excluded.observation_vector,
            action_vector = excluded.action_vector;
        """
        values = (
            str(record.get("session_id", "")),
            int(record.get("floor_number", 1)),
            float(record.get("timestamp", 0.0)),
            float(record.get("completion_time", 0.0)),
            int(record.get("deaths", 0)),
            float(record.get("damage_dealt", 0.0)),
            float(record.get("damage_taken", 0.0)),
            float(record.get("damage_exchange_ratio", 0.0)),
            int(record.get("rooms_cleared", 0)),
            int(record.get("enemies_defeated", 0)),
            int(record.get("hazard_hits", 0)),
            int(record.get("pickups_collected", 0)),
            float(record.get("enemy_health", 50.0)),
            float(record.get("enemy_damage", 15.0)),
            float(record.get("enemy_speed", 100.0)),
            float(record.get("enemy_aggro", 200.0)),
            float(record.get("hazard_density", 0.3)),
            float(record.get("resource_scarcity", 0.5)),
            float(record.get("room_count", 6.0)),
            float(record.get("enemy_count_scale", 1.0)),
            float(record.get("crawler_ratio", 0.5)),
            float(record.get("pyromancer_ratio", 0.5)),
            str(record.get("archetype_mix", "")),
            str(obs),
            str(act),
        )
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            return cursor.lastrowid

    def count_floor_records(self) -> int:
        """Returns the number of recorded floor outcomes."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM floor_telemetry;")
            return cursor.fetchone()[0]

    def get_all_floor_records(self) -> List[Dict[str, Any]]:
        """Returns all floor records in chronological sequence."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM floor_telemetry ORDER BY session_id, floor_number ASC;")
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_judge_training_data(self) -> Dict[str, Any]:
        """Formats the per-floor telemetry into feature inputs and target outcomes

        for training the supervised Judge regressor (Settings -> Outcomes).
        """
        records = self.get_all_floor_records()
        feature_names = [
            "enemy_health",
            "enemy_damage",
            "enemy_speed",
            "enemy_aggro",
            "hazard_density",
            "resource_scarcity",
            "room_count",
            "enemy_count_scale",
            "crawler_ratio",
            "pyromancer_ratio",
        ]
        target_names = [
            "completion_time",
            "deaths",
            "damage_taken",
            "damage_exchange_ratio",
        ]

        features: List[List[float]] = []
        targets: List[List[float]] = []
        for r in records:
            features.append([float(r[f]) for f in feature_names])
            targets.append([float(r[t]) for t in target_names])

        return {
            "features": features,
            "targets": targets,
            "feature_names": feature_names,
            "target_names": target_names,
            "sample_count": len(records),
        }

    # -------------------------------------------------------------------------
    # Import / Export / Game DB Sync
    # -------------------------------------------------------------------------
    def import_from_json(
        self, json_path: Optional[str] = None, clear_existing: bool = False
    ) -> int:
        """Imports training snapshots from a JSON file into SQLite, consolidating

        rolling snapshots by session_id into accurate session records.
        """
        path = json_path or DEFAULT_JSON_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"JSON training data not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array in {path}, got {type(data)}")

        with self.connection() as conn:
            cursor = conn.cursor()
            if clear_existing:
                cursor.execute("DELETE FROM session_telemetry;")
                cursor.execute("DELETE FROM floor_telemetry;")
            conn.commit()

        # Sort chronological so upsert maintains latest state for each session
        sorted_records = sorted(
            data, key=lambda x: (x.get("session_id", ""), float(x.get("elapsed_seconds", 0.0)))
        )
        for rec in sorted_records:
            self.upsert_session(rec)

        return self.count_sessions()

    def export_to_json(self, json_path: Optional[str] = None) -> int:
        """Exports unique session records to a JSON array file."""
        path = json_path or DEFAULT_JSON_PATH
        sessions = self.get_all_sessions()
        clean_sessions = []
        for s in sessions:
            clean = {k: s[k] for k in SESSION_FIELDS if k in s}
            clean_sessions.append(clean)

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean_sessions, f, indent=4)
        return len(clean_sessions)

    def sync_from_game_db(self, source_db_path: Optional[str] = None) -> Tuple[int, int]:
        """Copies session and floor records from Godot's runtime user://telemetry.db

        into this training database.
        """
        if not source_db_path:
            source_db_path = self.locate_game_db()

        if not source_db_path or not os.path.exists(source_db_path):
            return (0, 0)

        imported_sessions = 0
        imported_floors = 0
        src_conn = sqlite3.connect(source_db_path)
        src_conn.row_factory = sqlite3.Row
        try:
            cursor = src_conn.cursor()

            # Sync session_telemetry if present
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='session_telemetry';"
            )
            if cursor.fetchone():
                cursor.execute("SELECT * FROM session_telemetry;")
                for row in cursor.fetchall():
                    self.upsert_session(dict(row))
                    imported_sessions += 1

            # Sync floor_telemetry if present
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='floor_telemetry';"
            )
            if cursor.fetchone():
                cursor.execute("SELECT * FROM floor_telemetry;")
                for row in cursor.fetchall():
                    self.upsert_floor_record(dict(row))
                    imported_floors += 1
        finally:
            src_conn.close()

        return (imported_sessions, imported_floors)

    @staticmethod
    def locate_game_db() -> Optional[str]:
        """Locates Godot's user://telemetry.db file based on current OS conventions."""
        app_name = "FORGE - Adaptive Dungeon Prototype"
        system = platform.system()
        if system == "Windows":
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                path = os.path.join(appdata, "Godot", "app_userdata", app_name, "telemetry.db")
                if os.path.exists(path):
                    return path
        elif system == "Darwin":
            home = os.path.expanduser("~")
            path = os.path.join(
                home,
                "Library",
                "Application Support",
                "Godot",
                "app_userdata",
                app_name,
                "telemetry.db",
            )
            if os.path.exists(path):
                return path
        else:  # Linux / BSD
            home = os.path.expanduser("~")
            path = os.path.join(
                home, ".local", "share", "godot", "app_userdata", app_name, "telemetry.db"
            )
            if os.path.exists(path):
                return path
        return None

    def get_summary_stats(self) -> Dict[str, float]:
        """Calculates aggregated summary metrics across distinct sessions."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_sessions,
                    AVG(elapsed_seconds) as avg_elapsed_seconds,
                    AVG(rooms_cleared) as avg_rooms_cleared,
                    AVG(total_deaths) as avg_deaths,
                    AVG(damage_dealt) as avg_damage_dealt,
                    AVG(damage_taken) as avg_damage_taken,
                    AVG(enemies_defeated) as avg_enemies_defeated,
                    AVG(rooms_per_minute) as avg_rooms_per_minute
                FROM session_telemetry;
            """)
            row = cursor.fetchone()
            if not row or row["total_sessions"] == 0:
                return {"total_sessions": 0.0}
            return {
                "total_sessions": float(row["total_sessions"]),
                "avg_elapsed_seconds": round(float(row["avg_elapsed_seconds"] or 0), 2),
                "avg_rooms_cleared": round(float(row["avg_rooms_cleared"] or 0), 2),
                "avg_deaths": round(float(row["avg_deaths"] or 0), 2),
                "avg_damage_dealt": round(float(row["avg_damage_dealt"] or 0), 2),
                "avg_damage_taken": round(float(row["avg_damage_taken"] or 0), 2),
                "avg_enemies_defeated": round(float(row["avg_enemies_defeated"] or 0), 2),
                "avg_rooms_per_minute": round(float(row["avg_rooms_per_minute"] or 0), 2),
            }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)


if __name__ == "__main__":
    db = TelemetryDatabase()
    print(f"TelemetryDatabase active at: {db.db_path}")
    print(f"Distinct sessions: {db.count_sessions()}")
    print(f"Floor telemetry records: {db.count_floor_records()}")
    print("Summary Stats:", db.get_summary_stats())
