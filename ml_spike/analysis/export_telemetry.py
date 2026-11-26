"""Export the FORGE telemetry SQLite database (one row per floor) to the Judge-model CSV.

Pure standard library. The SQL lives in godot_prototype/telemetry/{schema,queries}.sql and is shared
with the Godot side (TelemetryLogger / TelemetrySQL.gd); the parsing helpers here mirror the GDScript
ones so the schema test can exercise exactly the strings the game executes.

Usage:
    python ml_spike/analysis/export_telemetry.py forge_telemetry.db corpus.csv [--consented-only]
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path

TELEMETRY_DIR = Path(__file__).resolve().parents[2] / "godot_prototype" / "telemetry"
SCHEMA_PATH = TELEMETRY_DIR / "schema.sql"
QUERIES_PATH = TELEMETRY_DIR / "queries.sql"

_MIGRATION_RE = re.compile(r"^--\s*migration\s+v(\d+)\s*$", re.IGNORECASE)
_BOOTSTRAP_RE = re.compile(r"^--\s*bootstrap\s*$", re.IGNORECASE)
_NAME_RE = re.compile(r"^--\s*name:\s*(\w+)\s*$")


def _strip_comments(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("--"))


def split_statements(sql: str) -> list[str]:
    """Split a SQL block on ';' (comment lines removed first). Mirrors TelemetrySQL.split_statements."""
    parts = [p.strip() for p in _strip_comments(sql).split(";")]
    return [p for p in parts if p]


def load_schema(path: Path = SCHEMA_PATH) -> tuple[list[str], list[tuple[int, list[str]]]]:
    """Return (bootstrap_statements, [(version, statements), ...]) sorted by version."""
    sections: dict[str, list[str]] = {"bootstrap": []}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _MIGRATION_RE.match(line.strip())
        if m:
            current = f"v{int(m.group(1))}"
            sections[current] = []
        elif _BOOTSTRAP_RE.match(line.strip()):
            current = "bootstrap"
        elif current is not None:
            sections[current].append(line)
    boot = split_statements("\n".join(sections["bootstrap"]))
    migs = sorted(
        (int(k[1:]), split_statements("\n".join(v)))
        for k, v in sections.items()
        if k != "bootstrap"
    )
    return boot, migs


def load_queries(path: Path = QUERIES_PATH) -> dict[str, str]:
    """Parse '-- name: id' blocks into {id: single statement (no trailing ';')}."""
    blocks: dict[str, list[str]] = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _NAME_RE.match(line.strip())
        if m:
            current = m.group(1)
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return {k: " ".join(split_statements("\n".join(v))[0].split()) for k, v in blocks.items()}


def insert_columns(sql: str) -> list[str]:
    """Column list of the first '(...)' group of an INSERT; defines positional bind order."""
    m = re.search(r"\(([^)]*)\)", sql)
    if not m:
        raise ValueError("no column list in statement")
    return [c.strip() for c in m.group(1).split(",")]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply bootstrap + pending migrations (one transaction each). Returns the schema version."""
    queries = load_queries()
    boot, migs = load_schema()
    conn.execute("PRAGMA foreign_keys = ON")
    for stmt in boot:
        conn.execute(stmt)
    current = conn.execute(queries["get_schema_version"]).fetchone()[0]
    for version, stmts in migs:
        if version <= current:
            continue
        with conn:  # commit or roll back the whole migration
            for stmt in stmts:
                conn.execute(stmt)
            conn.execute(queries["insert_schema_version"], (version, 0))
        current = version
    return current


def corpus_header(conn: sqlite3.Connection) -> list[str]:
    return [row[1] for row in conn.execute(load_queries()["corpus_columns"])]


def csv_cell(value: object) -> object:
    return "" if value is None else value


def export_corpus_csv(
    db_path: str | Path, csv_path: str | Path, consented_only: bool = False
) -> int:
    """Write one CSV row per floor. Returns the number of data rows written."""
    queries = load_queries()
    conn = sqlite3.connect(str(db_path))
    try:
        header = corpus_header(conn)
        key = "export_corpus_consented" if consented_only else "export_corpus"
        rows = conn.execute(queries[key]).fetchall()
    finally:
        conn.close()
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([csv_cell(v) for v in row])
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("db", help="path to forge_telemetry.db")
    parser.add_argument("csv", help="output CSV path")
    parser.add_argument(
        "--consented-only", action="store_true", help="only sessions with consent=1"
    )
    args = parser.parse_args(argv)
    n = export_corpus_csv(args.db, args.csv, args.consented_only)
    print(f"wrote {n} floor rows to {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
