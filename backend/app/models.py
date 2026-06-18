from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserPayload(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    access: Literal["edit", "confirm", "view"]
    role: Literal["employee", "coach", "kush", "amit", "akash", "admin", "viewer"]
    batch: str | None = None
    mobile: str | None = None
    password: str | None = Field(default=None, min_length=6)


class UserPatch(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    access: Literal["edit", "confirm", "view"] | None = None
    role: Literal["employee", "coach", "kush", "amit", "akash", "admin", "viewer"] | None = None
    batch: str | None = None
    mobile: str | None = None


class PasswordChange(BaseModel):
    password: str = Field(min_length=6)


class BatchPatch(BaseModel):
    coach: str | None = None
    employees: list[str] | None = None


class ConfirmPatch(BaseModel):
    key: str
    opt: Literal["o1", "o2"] | None = None
    val: Any = None
    rel: str | None = None


class SectionPatch(BaseModel):
    section: Literal["amit", "akash", "kyp"]
    key: str
    value: Any


class ApproveRequest(BaseModel):
    step: Literal["kush", "amit", "akash"]


class SendBackRequest(BaseModel):
    note: str = ""


class CommentRequest(BaseModel):
    text: str = Field(min_length=1)


class StudentPayload(BaseModel):
    id: str
    first: str | None = None
    last: str | None = None
    batch: str
    dob: str | None = None
    gender: str | None = None
    school: str | None = None
    pincode: str | None = None
    parent: str | None = None
    phone: str | None = None
    email: str | None = None
    jersey: str | None = None
    cup: str | None = None
    amount: str | int | float | None = None
    age: str | int | None = None


class ImportPayload(BaseModel):
    students: list[dict[str, Any]] = Field(default_factory=list)
    verify: dict[str, dict[str, Any]] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    replace: bool = False


class TokenResponse(BaseModel):
    ok: bool = True
    token: str
    user: dict[str, Any]
