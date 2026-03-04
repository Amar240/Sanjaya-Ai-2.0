from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


def require_admin(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> str:
    expected = os.getenv("SANJAYA_ADMIN_TOKEN", "dev-admin-token").strip()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_admin_token:
        token = x_admin_token.strip()

    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
    return "authorized"


def admin_username(x_admin_user: str | None = Header(default=None)) -> str:
    value = (x_admin_user or "").strip()
    return value or "advisor"
