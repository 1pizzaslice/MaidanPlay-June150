from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


DB_PATH = Path(os.environ.get("JUNE_ONE50_DB", Path(__file__).resolve().parents[1] / "june_one50.sqlite3"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    con = connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with session() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              email TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              access TEXT NOT NULL,
              role TEXT NOT NULL,
              batch TEXT,
              mobile TEXT,
              password_hash TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS batch_config (
              batch TEXT PRIMARY KEY,
              coach TEXT NOT NULL,
              employees_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS students (
              id TEXT PRIMARY KEY,
              first TEXT,
              last TEXT,
              batch TEXT NOT NULL,
              dob TEXT,
              gender TEXT,
              school TEXT,
              pincode TEXT,
              parent TEXT,
              phone TEXT,
              email TEXT,
              jersey TEXT,
              cup TEXT,
              amount TEXT,
              age TEXT,
              raw_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_students_batch ON students(batch);
            CREATE INDEX IF NOT EXISTS idx_students_name ON students(first, last);
            CREATE INDEX IF NOT EXISTS idx_students_phone ON students(phone);

            CREATE TABLE IF NOT EXISTS workflows (
              student_id TEXT PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
              record_json TEXT NOT NULL DEFAULT '{}',
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def read_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def write_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
