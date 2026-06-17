from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
# We talk to Postgres (Supabase in production) but keep the rest of the
# codebase written in the original sqlite3 idiom: `con.execute(sql, params)`
# returning a cursor you can `.fetchone()` / `.fetchall()` on, `?` query
# placeholders, `INSERT OR IGNORE`, and `CURRENT_TIMESTAMP`. The thin
# ConnWrapper / _translate shim below bridges those to psycopg so logic.py,
# main.py, security.py and the import script need no changes.


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("JUNE_ONE50_DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Point it at your Postgres/Supabase connection string, e.g. "
            "postgresql://user:pass@host:5432/postgres"
        )
    # Supabase (and most managed Postgres) require TLS.
    if "sslmode=" not in dsn:
        sep = "&" if "?" in dsn else "?"
        dsn = f"{dsn}{sep}sslmode=require"
    return dsn


_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_dsn(),
            min_size=1,
            max_size=int(os.environ.get("JUNE_ONE50_DB_POOL_MAX", "10")),
            # dict_row -> rows behave like sqlite3.Row (row["col"] and dict(row)).
            # prepare_threshold=None disables auto-prepared statements so the app
            # also works behind Supabase's transaction pooler (pgBouncer).
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
        )
    return _pool


def _translate(sql: str) -> str:
    """Translate the sqlite dialect used across the codebase to Postgres."""
    out = sql.replace("?", "%s")
    out = re.sub(r"\bCURRENT_TIMESTAMP\b", "now()::text", out)
    if re.search(r"INSERT\s+OR\s+IGNORE", out, flags=re.IGNORECASE):
        out = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", out, flags=re.IGNORECASE)
        out = out.rstrip().rstrip(";")
        out += " ON CONFLICT DO NOTHING"
    return out


class ConnWrapper:
    """sqlite3.Connection-compatible facade over a psycopg connection."""

    def __init__(self, raw: psycopg.Connection) -> None:
        self._raw = raw

    def execute(self, sql: str, params: Any = ()) -> psycopg.Cursor:
        return self._raw.execute(_translate(sql), params)

    def executescript(self, script: str) -> None:
        for statement in _split_statements(script):
            self._raw.execute(_translate(statement))

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()


def _split_statements(script: str) -> list[str]:
    return [stmt.strip() for stmt in script.split(";") if stmt.strip()]


@contextmanager
def session() -> Iterator[ConnWrapper]:
    # pool.connection() commits on clean exit and rolls back on exception,
    # matching the original session() semantics.
    with _get_pool().connection() as raw:
        yield ConnWrapper(raw)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA = """
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


def init_db() -> None:
    with session() as con:
        con.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# Row / JSON helpers (unchanged public API)
# ---------------------------------------------------------------------------
def row_to_dict(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
