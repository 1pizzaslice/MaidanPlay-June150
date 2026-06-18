from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status

from .config import (
    ACCESS_LABEL,
    AKASH_FIELDS,
    AMIT_FIELDS,
    BATCH_CONFIG,
    BATCH_ORDER,
    BATCH_REMAP,
    CONFIRM_FIELDS,
    DEFAULT_SEED_PASSWORD,
    DETAIL_FIELDS,
    GREEN_TARGET,
    KYP_FIELDS,
    ORG,
    ROLE_LABEL,
    STAGE,
    STAGE_LABEL,
    STUDENT_COLUMNS,
    SUPER,
    USERS,
)
from .db import read_json, row_to_dict, rows_to_dicts, write_json


STUDENT_ALIASES = {
    "id": ["id", "ID", "studentId", "Student ID"],
    "first": ["first", "First", "firstName", "First Name", "Player First Name"],
    "last": ["last", "Last", "lastName", "Last Name", "Player Last Name"],
    "batch": ["batch", "Batch", "Batch Type"],
    "dob": ["dob", "DOB", "Date of Birth"],
    "gender": ["gender", "Gender"],
    "school": ["school", "School", "School Name"],
    "pincode": ["pincode", "Pincode", "Home Pincode"],
    "parent": ["parent", "Parent", "Parent / Guardian Name", "Parent Name"],
    "phone": ["phone", "Phone", "WhatsApp Number", "Mobile", "Mobile Number"],
    "email": ["email", "Email"],
    "jersey": ["jersey", "Jersey", "Jersey Size"],
    "cup": ["cup", "Cup", "Cup of Nations"],
    "amount": ["amount", "Amount", "Total Amount"],
    "age": ["age", "Age"],
}

DEMO_STUDENTS = [
    {
        "id": "DEMO-TOD-001",
        "first": "Aarav",
        "last": "Demo",
        "batch": "Toddlers",
        "dob": "2019-04-12",
        "gender": "Male",
        "school": "Demo Valley School",
        "pincode": "110001",
        "parent": "Neha Demo",
        "phone": "9000000001",
        "email": "aarav.demo@example.com",
        "jersey": "XS",
        "cup": "Yes",
        "amount": "18000",
        "age": "7",
    },
    {
        "id": "DEMO-SUB-001",
        "first": "Ira",
        "last": "Sample",
        "batch": "Sub Junior",
        "dob": "2016-08-22",
        "gender": "Female",
        "school": "Sample Public School",
        "pincode": "110017",
        "parent": "Rohan Sample",
        "phone": "9000000002",
        "email": "ira.sample@example.com",
        "jersey": "S",
        "cup": "No",
        "amount": "22000",
        "age": "10",
    },
    {
        "id": "DEMO-JUN-001",
        "first": "Kabir",
        "last": "Test",
        "batch": "Junior",
        "dob": "2013-11-02",
        "gender": "Male",
        "school": "North Demo Academy",
        "pincode": "110048",
        "parent": "Meera Test",
        "phone": "9000000003",
        "email": "kabir.test@example.com",
        "jersey": "M",
        "cup": "Yes",
        "amount": "24000",
        "age": "13",
    },
    {
        "id": "DEMO-SEN-001",
        "first": "Zoya",
        "last": "Practice",
        "batch": "Senior",
        "dob": "2010-02-18",
        "gender": "Female",
        "school": "Central Practice School",
        "pincode": "110065",
        "parent": "Arjun Practice",
        "phone": "9000000004",
        "email": "zoya.practice@example.com",
        "jersey": "L",
        "cup": "Yes",
        "amount": "28000",
        "age": "16",
    },
]


def norm_num(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def now_stamp() -> str:
    return datetime.now().strftime("%d %b")


def clean_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def first_present(payload: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return ""


def normalize_student(payload: dict[str, Any]) -> dict[str, Any]:
    student: dict[str, Any] = {}
    for key in STUDENT_COLUMNS:
        value = first_present(payload, STUDENT_ALIASES.get(key, [key]))
        student[key] = clean_string(value)
    if not student["id"]:
        phone = norm_num(student.get("phone"))
        name = re.sub(r"[^A-Z0-9]+", "-", f"{student.get('first','')}-{student.get('last','')}".upper()).strip("-")
        student["id"] = f"STU-{phone[-4:] or name or int(datetime.now().timestamp())}"
    student["batch"] = BATCH_REMAP.get(student.get("batch"), student.get("batch") or "Unassigned")
    return student


def student_from_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {key: row.get(key) or "" for key in STUDENT_COLUMNS}
    raw = read_json(row.get("raw_json"), {})
    if raw:
        out["raw"] = raw
    return out


def safe_user(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    out.pop("password_hash", None)
    return out


def norm_email(value: Any) -> str:
    return str(value or "").strip().lower()


def hash_password(plain: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(plain.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return base64.b64encode(salt + derived).decode("ascii")


def password_fingerprint(password_hash: str | None) -> str:
    return (password_hash or "")[:8]


def verify_password(stored: str | None, plain: str) -> bool:
    if not stored:
        return False
    try:
        raw = base64.b64decode(stored.encode("ascii"))
    except Exception:
        return False
    if len(raw) < 17:
        return False
    salt, derived = raw[:16], raw[16:]
    test = hashlib.scrypt(plain.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return hmac.compare_digest(derived, test)


def list_users(con) -> list[dict[str, Any]]:
    rows = con.execute("SELECT * FROM users ORDER BY name").fetchall()
    return [safe_user(dict(row)) for row in rows]  # type: ignore[misc]


def get_user_by_email(con, email: str) -> dict[str, Any] | None:
    row = con.execute("SELECT * FROM users WHERE email = ?", (norm_email(email),)).fetchone()
    return safe_user(row_to_dict(row))


def get_user_with_password(con, email: str) -> dict[str, Any] | None:
    return row_to_dict(con.execute("SELECT * FROM users WHERE email = ?", (norm_email(email),)).fetchone())


def upsert_user(con, user: dict[str, Any], default_password: str | None = None) -> dict[str, Any]:
    email = norm_email(user.get("email"))
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    role = user.get("role") or "viewer"
    batch = user.get("batch") if role == "employee" else None
    mobile = norm_num(user.get("mobile")) or None
    existing = con.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if "password_hash" in user and user.get("password_hash"):
        password_hash = user["password_hash"]
    elif "password" in user and user.get("password"):
        password_hash = hash_password(str(user["password"]))
    elif existing and existing["password_hash"]:
        password_hash = existing["password_hash"]
    elif default_password:
        password_hash = hash_password(default_password)
    else:
        password_hash = ""
    con.execute(
        """
        INSERT INTO users (email, name, access, role, batch, mobile, password_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
          name = excluded.name,
          access = excluded.access,
          role = excluded.role,
          batch = excluded.batch,
          mobile = excluded.mobile,
          password_hash = excluded.password_hash
        """,
        (email, clean_string(user.get("name")), user.get("access") or "view", role, batch, mobile, password_hash),
    )
    return get_user_by_email(con, email) or {}


def set_password(con, email: str, plain: str) -> None:
    if not plain or len(plain) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    email = norm_email(email)
    row = con.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    con.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hash_password(plain), email))


def delete_user(con, email: str, actor: dict[str, Any]) -> None:
    email = norm_email(email)
    if email == norm_email(actor.get("email")):
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    con.execute("DELETE FROM users WHERE email = ?", (email,))


def list_batch_config(con) -> dict[str, dict[str, Any]]:
    rows = con.execute("SELECT * FROM batch_config").fetchall()
    cfg = {
        row["batch"]: {
            "coach": row["coach"],
            "employees": read_json(row["employees_json"], []),
        }
        for row in rows
    }
    for batch in BATCH_ORDER:
        cfg.setdefault(batch, BATCH_CONFIG[batch])
    return cfg


def upsert_batch(con, batch: str, patch: dict[str, Any]) -> dict[str, Any]:
    cfg = list_batch_config(con).get(batch, {"coach": "Unassigned", "employees": []})
    coach = clean_string(patch.get("coach")) if patch.get("coach") is not None else cfg.get("coach", "Unassigned")
    employees = patch.get("employees") if patch.get("employees") is not None else cfg.get("employees", [])
    employees = [clean_string(name) for name in employees if clean_string(name)]
    con.execute(
        """
        INSERT INTO batch_config (batch, coach, employees_json)
        VALUES (?, ?, ?)
        ON CONFLICT(batch) DO UPDATE SET
          coach = excluded.coach,
          employees_json = excluded.employees_json
        """,
        (batch, coach or "Unassigned", write_json(employees)),
    )
    return list_batch_config(con)[batch]


def reset_config(con) -> None:
    con.execute("DELETE FROM users")
    con.execute("DELETE FROM batch_config")
    for user in USERS:
        upsert_user(con, user, default_password=DEFAULT_SEED_PASSWORD)
    for batch, cfg in BATCH_CONFIG.items():
        upsert_batch(con, batch, cfg)


def upsert_student(con, payload: dict[str, Any]) -> dict[str, Any]:
    student = normalize_student(payload)
    raw = {k: v for k, v in payload.items() if k not in STUDENT_COLUMNS}
    con.execute(
        """
        INSERT INTO students (
          id, first, last, batch, dob, gender, school, pincode, parent, phone,
          email, jersey, cup, amount, age, raw_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
          first = excluded.first,
          last = excluded.last,
          batch = excluded.batch,
          dob = excluded.dob,
          gender = excluded.gender,
          school = excluded.school,
          pincode = excluded.pincode,
          parent = excluded.parent,
          phone = excluded.phone,
          email = excluded.email,
          jersey = excluded.jersey,
          cup = excluded.cup,
          amount = excluded.amount,
          age = excluded.age,
          raw_json = excluded.raw_json,
          updated_at = CURRENT_TIMESTAMP
        """,
        tuple(student[col] for col in STUDENT_COLUMNS) + (write_json(raw),),
    )
    con.execute(
        "INSERT OR IGNORE INTO workflows (student_id, record_json) VALUES (?, '{}')",
        (student["id"],),
    )
    return student


def get_student(con, student_id: str) -> dict[str, Any]:
    row = con.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student_from_row(dict(row))


def list_students(con) -> list[dict[str, Any]]:
    rows = con.execute("SELECT * FROM students ORDER BY batch, first, last").fetchall()
    return [student_from_row(dict(row)) for row in rows]


def rec_of(con, student_id: str) -> dict[str, Any]:
    row = con.execute("SELECT record_json FROM workflows WHERE student_id = ?", (student_id,)).fetchone()
    if not row:
        con.execute("INSERT INTO workflows (student_id, record_json) VALUES (?, '{}')", (student_id,))
        return {}
    return read_json(row["record_json"], {})


def set_rec(con, student_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    rec = rec_of(con, student_id)
    rec.update(patch)
    con.execute(
        """
        INSERT INTO workflows (student_id, record_json, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(student_id) DO UPDATE SET
          record_json = excluded.record_json,
          updated_at = CURRENT_TIMESTAMP
        """,
        (student_id, write_json(rec)),
    )
    return rec


def all_workflows(con) -> dict[str, dict[str, Any]]:
    rows = con.execute("SELECT * FROM workflows").fetchall()
    return {row["student_id"]: read_json(row["record_json"], {}) for row in rows}


def stage_of(rec: dict[str, Any]) -> str:
    return rec.get("stage") or STAGE["DRAFT"]


def stage_order(stage: str) -> int:
    return {
        STAGE["DRAFT"]: 0,
        STAGE["AMIT"]: 1,
        STAGE["AKASH"]: 2,
        STAGE["DONE"]: 3,
    }.get(stage, 0)


def has_comment(rec: dict[str, Any]) -> bool:
    return bool((rec.get("comment") or {}).get("text"))


def status_of(rec: dict[str, Any]) -> str:
    stage = stage_of(rec)
    if stage == STAGE["DONE"]:
        # A super-admin comment holds the profile back from going green.
        return "p" if has_comment(rec) else "g"
    if stage == STAGE["DRAFT"]:
        return "r"
    return "p"


def is_super(user: dict[str, Any] | None) -> bool:
    return bool(user and user.get("name") in SUPER)


def is_admin(user: dict[str, Any] | None) -> bool:
    return bool(user and user.get("role") == "admin")


def coach_of(cfg: dict[str, dict[str, Any]], batch: str) -> str:
    return cfg.get(batch, {}).get("coach") or "Unassigned"


def emp_list(cfg: dict[str, dict[str, Any]], batch: str) -> list[str]:
    employees = cfg.get(batch, {}).get("employees", [])
    if isinstance(employees, list):
        return [name for name in employees if name]
    return [employees] if employees else []


def owns_batch(user: dict[str, Any] | None, batch: str, cfg: dict[str, dict[str, Any]]) -> bool:
    if not user:
        return False
    if user.get("role") == "kush":
        return True
    if user.get("role") == "employee":
        return user.get("name") in emp_list(cfg, batch)
    if user.get("role") == "coach":
        return coach_of(cfg, batch) == user.get("name")
    return False


def can_fill_confirm(user: dict[str, Any], student: dict[str, Any], rec: dict[str, Any], cfg: dict[str, dict[str, Any]]) -> bool:
    if is_super(user):
        return True
    if not user or user.get("access") != "edit":
        return False
    stage = stage_of(rec)
    if user.get("role") == "amit" and stage == STAGE["AMIT"]:
        return True
    return stage == STAGE["DRAFT"] and owns_batch(user, student["batch"], cfg)


def can_coach_confirm(user: dict[str, Any], student: dict[str, Any], rec: dict[str, Any], cfg: dict[str, dict[str, Any]]) -> bool:
    return (
        bool(user)
        and user.get("role") == "coach"
        and stage_of(rec) == STAGE["DRAFT"]
        and coach_of(cfg, student["batch"]) == user.get("name")
    )


def can_kyp(user: dict[str, Any], _student: dict[str, Any]) -> bool:
    if is_super(user):
        return True
    return bool(user) and user.get("role") in {"kush", "coach"}


def can_amit_edit(user: dict[str, Any], rec: dict[str, Any]) -> bool:
    return bool(user) and (is_super(user) or (user.get("role") == "amit" and stage_of(rec) == STAGE["AMIT"]))


def can_akash_edit(user: dict[str, Any], rec: dict[str, Any]) -> bool:
    return bool(user) and (is_super(user) or (user.get("role") == "akash" and stage_of(rec) == STAGE["AKASH"]))


def confirm_green(rec: dict[str, Any], field: dict[str, Any]) -> bool:
    current = (rec.get("confirm") or {}).get(field["key"]) or {}
    if current.get("opt") == "o1":
        return True
    if current.get("opt") == "o2":
        return bool(clean_string(current.get("val"))) if field.get("o3") else True
    return False


def confirm_done(rec: dict[str, Any]) -> bool:
    return all(confirm_green(rec, field) for field in CONFIRM_FIELDS)


def confirm_count(rec: dict[str, Any]) -> int:
    return sum(1 for field in CONFIRM_FIELDS if confirm_green(rec, field))


def cond_met(rec: dict[str, Any], field: dict[str, Any], section: str) -> bool:
    when = field.get("when")
    if not when:
        return True
    key, expected = when.split("=", 1)
    return (rec.get(section) or {}).get(key) == expected


def val_green(rec: dict[str, Any], field: dict[str, Any], section: str) -> bool:
    if not cond_met(rec, field, section):
        return True
    value = (rec.get(section) or {}).get(field["key"])
    field_type = field.get("type")
    if field_type == "cleared":
        return value is True
    if field_type == "yesno":
        return value == field.get("greenOn") if field.get("greenOn") else value in {"Yes", "No"}
    if field_type in {"choice", "select"}:
        return bool(value)
    if field_type == "value":
        return value is not None and clean_string(value) != ""
    return bool(value)


def stage_done(rec: dict[str, Any], fields: list[dict[str, Any]], section: str) -> bool:
    return all(val_green(rec, field, section) for field in fields)


def amit_done(rec: dict[str, Any]) -> bool:
    return stage_done(rec, AMIT_FIELDS, "amit")


def akash_done(rec: dict[str, Any]) -> bool:
    return stage_done(rec, AKASH_FIELDS, "akash")


def kyp_done(rec: dict[str, Any]) -> bool:
    return stage_done(rec, KYP_FIELDS, "kyp")


def kyp_count(rec: dict[str, Any]) -> int:
    return sum(1 for field in KYP_FIELDS if val_green(rec, field, "kyp"))


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def merge_section_value(con, student_id: str, section: str, key: str, value: Any) -> dict[str, Any]:
    rec = rec_of(con, student_id)
    obj = dict(rec.get(section) or {})
    obj[key] = value
    return set_rec(con, student_id, {section: obj})


def merge_confirm(con, student_id: str, key: str, patch: dict[str, Any]) -> dict[str, Any]:
    rec = rec_of(con, student_id)
    confirm = dict(rec.get("confirm") or {})
    current = dict(confirm.get(key) or {})
    for patch_key, value in patch.items():
        if value is not None:
            current[patch_key] = value
    confirm[key] = current
    return set_rec(con, student_id, {"confirm": confirm})


def corrected_val(student: dict[str, Any], rec: dict[str, Any], key: str) -> Any:
    current = (rec.get("confirm") or {}).get(key) or {}
    if current.get("opt") == "o2" and clean_string(current.get("val")):
        return current.get("val")
    return student.get(key)


def build_clean_record(student: dict[str, Any], rec: dict[str, Any], cfg: dict[str, dict[str, Any]]) -> dict[str, Any]:
    amit = rec.get("amit") or {}
    akash = rec.get("akash") or {}
    kyp = rec.get("kyp") or {}
    confirm = rec.get("confirm") or {}
    parent_confirm = confirm.get("parent") or {}
    coach_confirm = rec.get("coachConfirm") or {}
    batch = student["batch"]
    return {
        "id": student["id"],
        "first": corrected_val(student, rec, "first"),
        "last": corrected_val(student, rec, "last"),
        "batch": batch,
        "coach": coach_of(cfg, batch),
        "employee": " + ".join(emp_list(cfg, batch)) or "Unassigned",
        "dob": corrected_val(student, rec, "dob"),
        "gender": corrected_val(student, rec, "gender"),
        "school": corrected_val(student, rec, "school"),
        "pincode": corrected_val(student, rec, "pincode"),
        "parent": corrected_val(student, rec, "parent"),
        "relationship": parent_confirm.get("rel") or "",
        "coachCheck": f"{coach_confirm.get('by') or ''} · {coach_confirm.get('at') or ''}"
        if coach_confirm.get("ok")
        else "",
        "phone": corrected_val(student, rec, "phone"),
        "email": corrected_val(student, rec, "email"),
        "jersey": corrected_val(student, rec, "jersey"),
        "cup": corrected_val(student, rec, "cup"),
        "amount": corrected_val(student, rec, "amount"),
        "age": corrected_val(student, rec, "age"),
        "stage": stage_of(rec),
        "submittedBy": rec.get("submittedBy") or "",
        "submittedAt": rec.get("submittedAt") or "",
        "amitBy": rec.get("amitBy") or "",
        "amitAt": rec.get("amitAt") or "",
        "akashBy": rec.get("akashBy") or "",
        "akashAt": rec.get("akashAt") or "",
        "ytdJersey": "Cleared" if amit.get("ytdJersey") else "",
        "ytdPayment": "Cleared" if amit.get("ytdPayment") else "",
        "ytdOthers": "Cleared" if amit.get("ytdOthers") else "",
        "scholarshipFlag": amit.get("scholarshipFlag") or "",
        "scholarshipFees": amit.get("scholarshipFees") or "",
        "oneVone": amit.get("oneVone") or "",
        "oneVoneRev": amit.get("oneVoneRev") or "",
        "prominence": amit.get("prominence") or "",
        "prominenceFees": amit.get("prominenceFees") or "",
        "planMonths": amit.get("planMonths") or "",
        "academyFee": amit.get("academyFee") or "",
        "feeReceived": akash.get("feeReceived") or "",
        "invoiceShared": akash.get("invoiceShared") or "",
        "paymentType": akash.get("paymentType") or "",
        "cashFeeValue": akash.get("cashFeeValue") or "",
        "noDuesMail": akash.get("noDuesMail") or "",
        "legalSigned": akash.get("legalSigned") or "",
        "kitDelivered": akash.get("kitDelivered") or "",
        "position": kyp.get("position") or "",
        "club": kyp.get("club") or "",
        "foot": kyp.get("foot") or "",
        "activeIG": kyp.get("ig") or "",
        "favPlayer": kyp.get("favPlayer") or "",
        "level": kyp.get("level") or "",
    }


def enrich_workflow(rec: dict[str, Any]) -> dict[str, Any]:
    out = dict(rec)
    out["_meta"] = {
        "stage": stage_of(rec),
        "status": status_of(rec),
        "confirmCount": confirm_count(rec),
        "confirmDone": confirm_done(rec),
        "amitDone": amit_done(rec),
        "akashDone": akash_done(rec),
        "kypDone": kyp_done(rec),
        "kypCount": kyp_count(rec),
    }
    return out


def constants_payload() -> dict[str, Any]:
    return {
        "batchOrder": BATCH_ORDER,
        "org": ORG,
        "accessLabel": ACCESS_LABEL,
        "roleLabel": ROLE_LABEL,
        "stage": STAGE,
        "stageLabel": STAGE_LABEL,
        "confirmFields": CONFIRM_FIELDS,
        "amitFields": AMIT_FIELDS,
        "akashFields": AKASH_FIELDS,
        "detailFields": DETAIL_FIELDS,
        "kypFields": KYP_FIELDS,
        "greenTarget": GREEN_TARGET,
        "super": SUPER,
    }


def bootstrap_payload(con, user: dict[str, Any]) -> dict[str, Any]:
    workflows = all_workflows(con)
    enriched = {student_id: enrich_workflow(record) for student_id, record in workflows.items()}
    return {
        "ok": True,
        "user": user,
        "students": list_students(con),
        "verify": enriched,
        "config": {
            "users": list_users(con),
            "batchcfg": list_batch_config(con),
            **constants_payload(),
        },
    }


def seed_if_empty(con, include_demo: bool) -> None:
    if con.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0:
        for user in USERS:
            upsert_user(con, user, default_password=DEFAULT_SEED_PASSWORD)
    if con.execute("SELECT COUNT(*) AS n FROM batch_config").fetchone()["n"] == 0:
        for batch, cfg in BATCH_CONFIG.items():
            upsert_batch(con, batch, cfg)
    if include_demo and con.execute("SELECT COUNT(*) AS n FROM students").fetchone()["n"] == 0:
        for student in DEMO_STUDENTS:
            upsert_student(con, student)
