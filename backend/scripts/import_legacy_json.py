#!/usr/bin/env python3
"""Import a legacy sheet export JSON file into the SQLite app database.

Expected input shape matches the old Apps Script response:
{
  "students": [...],
  "verify": {"student-id": {...}},
  "config": {"users": [...], "batchcfg": {...}}
}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import DEFAULT_SEED_PASSWORD  # noqa: E402
from app.db import init_db, session, write_json  # noqa: E402
from app.logic import seed_if_empty, upsert_batch, upsert_student, upsert_user  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.json_file.read_text())
    init_db()
    with session() as con:
        seed_if_empty(con, include_demo=False)
        if args.replace:
            con.execute("DELETE FROM workflows")
            con.execute("DELETE FROM students")
        for student in payload.get("students", []):
            upsert_student(con, student)
        for student_id, record in (payload.get("verify") or {}).items():
            exists = con.execute("SELECT 1 FROM students WHERE id = ?", (student_id,)).fetchone()
            if not exists:
                continue
            con.execute(
                """
                INSERT INTO workflows (student_id, record_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(student_id) DO UPDATE SET
                  record_json = excluded.record_json,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (student_id, write_json(record)),
            )
        config = payload.get("config") or {}
        for user in config.get("users") or []:
            if not user.get("email"):
                handle = (user.get("name") or "user").strip().lower().replace(" ", "")
                user["email"] = f"{handle}@maidanplay.com"
            upsert_user(con, user, default_password=DEFAULT_SEED_PASSWORD)
        for batch, cfg in (config.get("batchcfg") or {}).items():
            upsert_batch(con, batch, cfg)
    print("Import complete")


if __name__ == "__main__":
    main()
