from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .config import AKASH_FIELDS, AMIT_FIELDS, KYP_FIELDS, STAGE
from .db import init_db, session, write_json
from .logic import (
    akash_done,
    amit_done,
    bootstrap_payload,
    build_clean_record,
    can_akash_edit,
    can_amit_edit,
    can_coach_confirm,
    can_fill_confirm,
    can_kyp,
    confirm_done,
    delete_user,
    get_student,
    get_user_by_email,
    get_user_with_password,
    kyp_done,
    list_batch_config,
    list_students,
    list_users,
    merge_confirm,
    merge_section_value,
    norm_email,
    norm_num,
    rec_of,
    require,
    reset_config,
    seed_if_empty,
    set_password,
    set_rec,
    upsert_batch,
    upsert_student,
    upsert_user,
    verify_password,
    now_stamp,
)
from .models import (
    ApproveRequest,
    BatchPatch,
    ConfirmPatch,
    ImportPayload,
    LoginRequest,
    PasswordChange,
    SectionPatch,
    SendBackRequest,
    StudentPayload,
    TokenResponse,
    UserPatch,
    UserPayload,
)
from .security import create_token, current_user, require_admin, require_super


app = FastAPI(title="June One50 API", version="1.0.0")

origins = [
    origin.strip()
    for origin in os.environ.get("JUNE_ONE50_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    include_demo = os.environ.get("JUNE_ONE50_SEED_DEMO", "1") != "0"
    with session() as con:
        seed_if_empty(con, include_demo=include_demo)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> dict[str, Any]:
    with session() as con:
        row = get_user_with_password(con, payload.email)
    if not row or not verify_password(row.get("password_hash"), payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user = {k: v for k, v in row.items() if k != "password_hash"}
    return {"ok": True, "token": create_token(user, row.get("password_hash")), "user": user}


@app.get("/api/bootstrap")
def bootstrap(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with session() as con:
        return bootstrap_payload(con, user)


@app.get("/api/export/clean")
def export_clean(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with session() as con:
        cfg = list_batch_config(con)
        rows = [build_clean_record(student, rec_of(con, student["id"]), cfg) for student in list_students(con)]
    return {"ok": True, "rows": rows}


@app.get("/api/export/clean.csv")
def export_clean_csv(user: dict[str, Any] = Depends(current_user)) -> Response:
    with session() as con:
        cfg = list_batch_config(con)
        rows = [build_clean_record(student, rec_of(con, student["id"]), cfg) for student in list_students(con)]
    if not rows:
        return Response("", media_type="text/csv")
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        cells = []
        for key in headers:
            value = str(row.get(key, "")).replace('"', '""')
            cells.append(f'"{value}"' if any(ch in value for ch in [",", "\n", '"']) else value)
        lines.append(",".join(cells))
    return Response("\n".join(lines), media_type="text/csv")


@app.get("/api/users")
def users(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with session() as con:
        return {"ok": True, "users": list_users(con)}


@app.post("/api/users")
def create_user(payload: UserPayload, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    from .config import DEFAULT_SEED_PASSWORD

    with session() as con:
        body = payload.model_dump()
        if not body.get("password"):
            body.pop("password", None)
        user = upsert_user(con, body, default_password=DEFAULT_SEED_PASSWORD)
        return {"ok": True, "user": user, "users": list_users(con)}


@app.patch("/api/users/{email}")
def patch_user(email: str, payload: UserPatch, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    target = norm_email(email)
    with session() as con:
        existing = get_user_by_email(con, target)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")
        patch = {k: v for k, v in payload.model_dump().items() if v is not None}
        new_email = norm_email(patch.get("email") or existing["email"])
        if new_email != target:
            if get_user_by_email(con, new_email):
                raise HTTPException(status_code=409, detail="That email is already in use")
            con.execute("UPDATE users SET email = ? WHERE email = ?", (new_email, target))
        merged = {**existing, **patch, "email": new_email}
        user = upsert_user(con, merged)
        return {"ok": True, "user": user, "users": list_users(con)}


@app.post("/api/users/{email}/password")
def change_password(email: str, payload: PasswordChange, _: dict[str, Any] = Depends(require_super)) -> dict[str, Any]:
    with session() as con:
        set_password(con, email, payload.password)
        return {"ok": True}


@app.delete("/api/users/{email}")
def remove_user(email: str, actor: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with session() as con:
        delete_user(con, email, actor)
        return {"ok": True, "users": list_users(con)}


@app.patch("/api/batches/{batch}")
def patch_batch(batch: str, payload: BatchPatch, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with session() as con:
        cfg = upsert_batch(con, batch, payload.model_dump(exclude_unset=True))
        return {"ok": True, "batch": cfg, "batchcfg": list_batch_config(con)}


@app.post("/api/admin/reset-config")
def reset_defaults(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with session() as con:
        reset_config(con)
        return {"ok": True, "users": list_users(con), "batchcfg": list_batch_config(con)}


@app.post("/api/students")
def create_student(payload: StudentPayload, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with session() as con:
        student = upsert_student(con, payload.model_dump())
        return {"ok": True, "student": student}


@app.post("/api/students/import")
def import_students(payload: ImportPayload, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with session() as con:
        if payload.replace:
            con.execute("DELETE FROM workflows")
            con.execute("DELETE FROM students")
        for student in payload.students:
            upsert_student(con, student)
        for student_id, record in payload.verify.items():
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
        from .config import DEFAULT_SEED_PASSWORD

        config = payload.config or {}
        if isinstance(config.get("users"), list):
            for user in config["users"]:
                if not user.get("email"):
                    handle = (user.get("name") or "user").strip().lower().replace(" ", "")
                    user["email"] = f"{handle}@maidanplay.com"
                upsert_user(con, user, default_password=DEFAULT_SEED_PASSWORD)
        if isinstance(config.get("batchcfg"), dict):
            for batch, cfg in config["batchcfg"].items():
                upsert_batch(con, batch, cfg)
        return {"ok": True, "students": len(payload.students), "verify": len(payload.verify)}


@app.patch("/api/workflows/{student_id}/confirm")
def patch_confirm(
    student_id: str,
    payload: ConfirmPatch,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    with session() as con:
        student = get_student(con, student_id)
        cfg = list_batch_config(con)
        rec = rec_of(con, student_id)
        require(can_fill_confirm(user, student, rec, cfg), "Confirm fields are locked for this user")
        patch = payload.model_dump(exclude_unset=True)
        key = patch.pop("key")
        updated = merge_confirm(con, student_id, key, patch)
        return {"ok": True, "record": updated}


@app.patch("/api/workflows/{student_id}/section")
def patch_section(
    student_id: str,
    payload: SectionPatch,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    with session() as con:
        student = get_student(con, student_id)
        rec = rec_of(con, student_id)
        if payload.section == "amit":
            require(can_amit_edit(user, rec), "Amit section is locked for this user")
        elif payload.section == "akash":
            require(can_akash_edit(user, rec), "Akash section is locked for this user")
        else:
            require(can_kyp(user, student), "Know Your Player is locked for this user")
        updated = merge_section_value(con, student_id, payload.section, payload.key, payload.value)
        return {"ok": True, "record": updated}


@app.post("/api/workflows/{student_id}/coach-confirm")
def coach_confirm(student_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with session() as con:
        student = get_student(con, student_id)
        cfg = list_batch_config(con)
        rec = rec_of(con, student_id)
        require(can_coach_confirm(user, student, rec, cfg), "Only the batch coach can cross-check")
        current = rec.get("coachConfirm") or {}
        next_value = {"ok": False} if current.get("ok") else {"ok": True, "by": user["name"], "at": now_stamp()}
        updated = set_rec(con, student_id, {"coachConfirm": next_value})
        return {"ok": True, "record": updated}


@app.post("/api/workflows/{student_id}/approve")
def approve(student_id: str, payload: ApproveRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with session() as con:
        student = get_student(con, student_id)
        cfg = list_batch_config(con)
        rec = rec_of(con, student_id)
        stage = rec.get("stage") or STAGE["DRAFT"]
        if payload.step == "kush":
            require((user.get("role") == "kush" or user.get("name") in {"Akash", "Abhimanyu", "Ruchir"}) and stage == STAGE["DRAFT"], "Kush approval is locked")
            require(confirm_done(rec), "Confirm all fields first")
            updated = set_rec(
                con,
                student_id,
                {
                    "stage": STAGE["AMIT"],
                    "submittedBy": user["name"],
                    "submittedAt": now_stamp(),
                    "sentBack": None,
                    "sentBackBy": None,
                    "sentBackAt": None,
                    "sentBackTo": None,
                },
            )
        elif payload.step == "amit":
            require((user.get("role") == "amit" or user.get("name") in {"Akash", "Abhimanyu", "Ruchir"}) and stage == STAGE["AMIT"], "Amit approval is locked")
            require(amit_done(rec), "Fill all Amit fields first")
            updated = set_rec(
                con,
                student_id,
                {
                    "stage": STAGE["AKASH"],
                    "amitBy": user["name"],
                    "amitAt": now_stamp(),
                    "sentBack": None,
                    "sentBackBy": None,
                    "sentBackAt": None,
                    "sentBackTo": None,
                },
            )
        else:
            require((user.get("role") == "akash" or user.get("name") in {"Akash", "Abhimanyu", "Ruchir"}) and stage == STAGE["AKASH"], "Akash approval is locked")
            require(akash_done(rec), "Fill all Akash fields first")
            updated = set_rec(
                con,
                student_id,
                {"stage": STAGE["DONE"], "akashBy": user["name"], "akashAt": now_stamp(), "closedAt": now_stamp()},
            )
        return {"ok": True, "record": updated, "clean": build_clean_record(student, updated, cfg)}


@app.post("/api/workflows/{student_id}/send-back")
def send_back(student_id: str, payload: SendBackRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with session() as con:
        get_student(con, student_id)
        rec = rec_of(con, student_id)
        stage = rec.get("stage") or STAGE["DRAFT"]
        if stage == STAGE["AMIT"]:
            require(user.get("role") == "amit" or user.get("name") in {"Akash", "Abhimanyu", "Ruchir"}, "Only Amit can send this back")
            target, to_name = STAGE["DRAFT"], "Kush"
        elif stage == STAGE["AKASH"]:
            require(user.get("role") == "akash" or user.get("name") in {"Akash", "Abhimanyu", "Ruchir"}, "Only Akash can send this back")
            target, to_name = STAGE["AMIT"], "Amit"
        else:
            raise HTTPException(status_code=400, detail="This stage cannot be sent back")
        updated = set_rec(
            con,
            student_id,
            {
                "stage": target,
                "sentBack": payload.note.strip(),
                "sentBackBy": user["name"],
                "sentBackAt": now_stamp(),
                "sentBackTo": to_name,
            },
        )
        return {"ok": True, "record": updated}


@app.post("/api/workflows/{student_id}/reopen")
def reopen(student_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with session() as con:
        rec = rec_of(con, student_id)
        require(
            user.get("role") in {"akash", "kush"} or user.get("name") in {"Akash", "Abhimanyu", "Ruchir"},
            "Only Akash, Kush, or a super-editor can reopen",
        )
        updated = set_rec(
            con,
            student_id,
            {"stage": STAGE["DRAFT"], "akashBy": None, "akashAt": None, "amitBy": None, "amitAt": None, "closedAt": None},
        )
        return {"ok": True, "record": updated}


@app.post("/api/workflows/{student_id}/kyp/publish")
def publish_kyp(student_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with session() as con:
        student = get_student(con, student_id)
        rec = rec_of(con, student_id)
        require(can_kyp(user, student), "Know Your Player is locked for this user")
        require(kyp_done(rec), "Fill all KYP fields first")
        kyp = dict(rec.get("kyp") or {})
        kyp.update({"published": True, "publishedBy": user["name"], "publishedAt": now_stamp()})
        updated = set_rec(con, student_id, {"kyp": kyp})
        return {"ok": True, "record": updated}


@app.get("/api/students/{student_id}")
def get_one_student(student_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with session() as con:
        student = get_student(con, student_id)
        rec = rec_of(con, student_id)
        return {"ok": True, "student": student, "record": rec}
