from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import session
from .logic import get_user_with_password, is_super, norm_email, password_fingerprint


AUTH_SECRET = os.environ.get("JUNE_ONE50_SECRET", "dev-change-me-before-production")
TOKEN_TTL_SECONDS = int(os.environ.get("JUNE_ONE50_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 14)))
bearer = HTTPBearer(auto_error=False)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(user: dict[str, Any], password_hash: str | None) -> str:
    payload = {
        "email": norm_email(user["email"]),
        "pf": password_fingerprint(password_hash),
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"


def verify_token(token: str) -> dict[str, Any]:
    try:
        body, sig = token.split(".", 1)
        expected = _b64(hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        payload = json.loads(_unb64(body))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    payload = verify_token(credentials.credentials)
    with session() as con:
        row = get_user_with_password(con, payload["email"])
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    if payload.get("pf") != password_fingerprint(row.get("password_hash")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password changed - please log in again")
    return {k: v for k, v in row.items() if k != "password_hash"}


def require_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") != "admin" and not is_super(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_super(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not is_super(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super-admin access required")
    return user
