"""FORGE — Telemetry SQLite Database Manager
-----------------------------------------
Provides zero-configuration, local SQLite persistence for player session telemetry
and empirical training data. Replaces legacy flat JSON storage with structured,
queryable relational tables for FYP-2 offline RL and model fine-tuning.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_telemetry.db")
DEFAULT_JSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "session_telemetry.json"
)

CREATE_TABLE_SQL = """
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
"""

CREATE_INDICES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_telemetry_session_id ON session_telemetry(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON session_telemetry(timestamp);",
]

TELEMETRY_FIELDS = [
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
]


class TelemetryDatabase:
    """Manages SQLite storage and retrieval of player session telemetry training data."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._init_db()

    @contextmanager
    def connection(self):
        """Context manager that yields an active SQLite connection and always closes it."""
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
            cursor.execute(CREATE_TABLE_SQL)
            for index_sql in CREATE_INDICES_SQL:
                cursor.execute(index_sql)
            conn.commit()

    def insert_session(self, record: Dict[str, Any]) -> int:
        """Inserts a single session record into SQLite. Returns the new record ID."""
        sql = f"""
        INSERT INTO session_telemetry (
            {", ".join(TELEMETRY_FIELDS)}
        ) VALUES (
            {", ".join(["?" for _ in TELEMETRY_FIELDS])}
        );
        """
        values = [
            record.get(field, 0.0 if field != "session_id" else "") for field in TELEMETRY_FIELDS
        ]
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            return cursor.lastrowid

    def insert_sessions(self, records: List[Dict[str, Any]]) -> int:
        """Batch-inserts session records inside a single transaction. Returns count inserted."""
        if not records:
            return 0
        sql = f"""
        INSERT INTO session_telemetry (
            {", ".join(TELEMETRY_FIELDS)}
        ) VALUES (
            {", ".join(["?" for _ in TELEMETRY_FIELDS])}
        );
        """
        rows = [
            [rec.get(field, 0.0 if field != "session_id" else "") for field in TELEMETRY_FIELDS]
            for rec in records
        ]
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, rows)
            conn.commit()
            return len(records)

    def count(self) -> int:
        """Returns the total number of records in the database."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM session_telemetry;")
            return cursor.fetchone()[0]

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Returns all session telemetry records in chronological (ID) order."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM session_telemetry ORDER BY id ASC;")
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_recent_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the most recent `limit` sessions in chronological order."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM (
                    SELECT * FROM session_telemetry ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC;
                """,
                (limit,),
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def import_from_json(
        self, json_path: Optional[str] = None, clear_existing: bool = False
    ) -> int:
        """Imports training data from a JSON file into the SQLite database.

        If clear_existing is True, existing rows are dropped first.
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
            conn.commit()

        return self.insert_sessions(data)

    def export_to_json(self, json_path: Optional[str] = None, limit: Optional[int] = None) -> int:
        """Exports SQLite session data to a JSON array file."""
        path = json_path or DEFAULT_JSON_PATH
        sessions = self.get_recent_sessions(limit) if limit else self.get_all_sessions()
        # Clean internal SQLite fields for exact schema matching
        clean_sessions = []
        for s in sessions:
            clean = {k: s[k] for k in TELEMETRY_FIELDS if k in s}
            clean_sessions.append(clean)

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean_sessions, f, indent=4)
        return len(clean_sessions)

    def get_summary_stats(self) -> Dict[str, float]:
        """Calculates aggregated performance summary metrics across all recorded sessions."""
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
                    AVG(exploration_efficiency) as avg_exploration_efficiency
                FROM session_telemetry;
            """)
            row = cursor.fetchone()
            if not row or row["total_sessions"] == 0:
                return {"total_sessions": 0}
            return {
                "total_sessions": float(row["total_sessions"]),
                "avg_elapsed_seconds": round(float(row["avg_elapsed_seconds"] or 0), 2),
                "avg_rooms_cleared": round(float(row["avg_rooms_cleared"] or 0), 2),
                "avg_deaths": round(float(row["avg_deaths"] or 0), 2),
                "avg_damage_dealt": round(float(row["avg_damage_dealt"] or 0), 2),
                "avg_damage_taken": round(float(row["avg_damage_taken"] or 0), 2),
                "avg_enemies_defeated": round(float(row["avg_enemies_defeated"] or 0), 2),
                "avg_exploration_efficiency": round(
                    float(row["avg_exploration_efficiency"] or 0), 3
                ),
            }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        return d


if __name__ == "__main__":
    db = TelemetryDatabase()
    count = db.import_from_json(clear_existing=True)
    print(f"Successfully migrated {count} session telemetry records into SQLite: {db.db_path}")
    stats = db.get_summary_stats()
    print("Database Summary Stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
