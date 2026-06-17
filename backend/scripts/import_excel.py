#!/usr/bin/env python3
"""Import the "June One50.xlsx" workbook into the app database.

The workbook has four sheets:
  - "Web App Data Set"  -> raw player submissions (source for the students table)
  - "Cleaned Database"  -> workflow records (the `Data (JSON)` column == record_json)
  - "Know Your Player"  -> KYP section, merged into each player's record_json["kyp"]
  - "Config"            -> legacy users list (skipped: users are already seeded)

Usage:
  DATABASE_URL=... python scripts/import_excel.py "/path/to/June One50.xlsx" --replace
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import init_db, session, write_json  # noqa: E402
from app.logic import seed_if_empty, upsert_student  # noqa: E402


def cval(value):
    """Coerce an Excel cell to the clean string the app expects."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()


def read_sheet(ws):
    it = ws.iter_rows(values_only=True)
    header = next(it)
    rows = []
    for raw in it:
        if raw is None or all(cell is None for cell in raw):
            continue
        rows.append(dict(zip(header, raw)))
    return rows


def build_student(row):
    return {
        "id": cval(row.get("Player ID")),
        "first": cval(row.get("Player First Name")),
        "last": cval(row.get("Player Last Name")),
        "batch": cval(row.get("Batch Type")),
        "dob": cval(row.get("Date of Birth")),
        "gender": cval(row.get("Gender")),
        "school": cval(row.get("School Name")),
        "pincode": cval(row.get("Home Pincode")),
        "parent": cval(row.get("Parent / Guardian Name")),
        "phone": cval(row.get("WhatsApp Number")),
        "email": cval(row.get("Email")),
        "jersey": cval(row.get("Jersey Size")),
        "cup": cval(row.get("Cup of Nations")),
        "amount": cval(row.get("Total Amount")),
        "age": cval(row.get("Age")),
        # extra submission fields -> stored in students.raw_json
        "Arena": cval(row.get("Arena")),
        "Frequency": cval(row.get("Frequency")),
        "Time Slot": cval(row.get("Time Slot")),
        "Existing Student": cval(row.get("Existing Student")),
        "Onboarding Kit": cval(row.get("Onboarding Kit")),
        "Timestamp": cval(row.get("Timestamp")),
    }


def build_kyp(row):
    return {
        "position": cval(row.get("Preferred Position")),
        "club": cval(row.get("Favourite Club")),
        "foot": cval(row.get("Preferred Foot")),
        "ig": cval(row.get("Active on IG")),
        "favPlayer": cval(row.get("Favourite Player")),
        "level": cval(row.get("Football Level")),
        "publishedBy": cval(row.get("Published By")),
        "publishedAt": cval(row.get("Published At")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--replace", action="store_true", help="wipe students + workflows first")
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.xlsx, read_only=True, data_only=True)
    web = read_sheet(wb["Web App Data Set"])
    cleaned = read_sheet(wb["Cleaned Database"])
    kyp = read_sheet(wb["Know Your Player"])

    students = [build_student(r) for r in web if cval(r.get("Player ID"))]

    # verify[player_id] -> record_json
    verify: dict[str, dict] = {}
    for r in cleaned:
        pid = cval(r.get("Player ID"))
        blob = r.get("Data (JSON)")
        if pid and blob:
            verify[pid] = json.loads(blob)
    for r in kyp:
        pid = cval(r.get("Player ID"))
        if pid:
            verify.setdefault(pid, {})["kyp"] = build_kyp(r)

    init_db()
    with session() as con:
        seed_if_empty(con, include_demo=False)
        if args.replace:
            con.execute("DELETE FROM workflows")
            con.execute("DELETE FROM students")
        for student in students:
            upsert_student(con, student)
        written = 0
        for student_id, record in verify.items():
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
            written += 1

    print(f"Imported {len(students)} students, {written} workflow records "
          f"({len(verify)} record candidates from cleaned/KYP sheets).")


if __name__ == "__main__":
    main()
