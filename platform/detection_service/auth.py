"""
auth.py - real authentication + role-based access for the ICS Guardian service.

Self-contained and dependency-light: uses only the Python standard library for
password hashing (PBKDF2-HMAC-SHA256, salted) and JWT (HS256 via hmac), plus
SQLite for the user store. No plaintext passwords are ever stored.

Roles
    admin     - full access: user management, system status, all activity
    operator  - day-to-day user: run the detector, view dashboards

Endpoints (mounted under /auth)
    POST /auth/register   {email, password}      -> creates an OPERATOR, returns a token
    POST /auth/login      {email, password}      -> {access_token, role, email}
    GET  /auth/me         Authorization: Bearer   -> {email, role}
    GET  /auth/users      (admin only)            -> list of users
    POST /auth/users/{email}/role  (admin only)  -> change a user's role

Two accounts are seeded on first run:
    admin@icsguardian.local    / Admin@12345      (admin)
    operator@icsguardian.local / Operator@12345   (operator)
Change them in production; set AUTH_SECRET to a strong random value.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

# Light e-mail check. We deliberately do NOT use pydantic EmailStr /
# email-validator here: that library rejects special-use domains such as
# ".local", which would make the seeded demo accounts (…@icsguardian.local)
# fail login with a 422 before the password is ever checked.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# --------------------------------------------------------------------------- #
DB_PATH = Path(os.getenv("AUTH_DB", Path(__file__).parent / "data" / "users.db"))
SECRET = os.getenv("AUTH_SECRET", "dev-only-change-me-in-production").encode()
TOKEN_TTL = int(os.getenv("AUTH_TOKEN_TTL", "28800"))  # 8 hours
PBKDF2_ROUNDS = 200_000
ROLES = ("admin", "operator")

# --------------------------------------------------------------------------- #
# Capabilities per role. This is the single source of truth for "who can do
# what". The UI reads it via /auth/me; the API enforces it via the guards below.
#
#   operator  - day-to-day user: run the detector on their own data, view the
#               dashboards, manage their own account (change their password).
#   admin     - everything an operator can do, PLUS manage the platform: list
#               and manage users, enable/disable accounts, change roles, view
#               system activity, and change the live detection threshold.
# --------------------------------------------------------------------------- #
_OPERATOR_CAPS = ["run_detector", "view_dashboards", "view_account", "change_own_password"]
_ADMIN_CAPS = _OPERATOR_CAPS + [
    "manage_users", "change_roles", "enable_disable_users",
    "view_activity", "manage_settings",
]
CAPABILITIES = {"operator": _OPERATOR_CAPS, "admin": _ADMIN_CAPS}


def capabilities_for(role: str) -> list[str]:
    return CAPABILITIES.get(role, [])

router = APIRouter(prefix="/auth", tags=["auth"])


# ----------------------------- storage ------------------------------------- #
def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _init_db() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS users(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   email TEXT UNIQUE NOT NULL,
                   pw_hash TEXT NOT NULL,
                   salt TEXT NOT NULL,
                   role TEXT NOT NULL DEFAULT 'operator',
                   active INTEGER NOT NULL DEFAULT 1,
                   created_at INTEGER NOT NULL)"""
        )
        # migrate older DBs that predate the 'active' column
        cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
        if "active" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1")


# ----------------------------- password hashing ---------------------------- #
def _hash(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return base64.b64encode(dk).decode()


def _make_user(email: str, password: str, role: str) -> None:
    salt = os.urandom(16)
    with _conn() as c:
        c.execute(
            "INSERT INTO users(email,pw_hash,salt,role,created_at) VALUES(?,?,?,?,?)",
            (email.lower(), _hash(password, salt), base64.b64encode(salt).decode(),
             role, int(time.time())),
        )


def _get(email: str) -> sqlite3.Row | None:
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()


def _verify_pw(row: sqlite3.Row, password: str) -> bool:
    salt = base64.b64decode(row["salt"])
    return hmac.compare_digest(_hash(password, salt), row["pw_hash"])


# ----------------------------- JWT (HS256, stdlib) ------------------------- #
def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(email: str, role: str) -> str:
    header = _b64u(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64u(json.dumps({"sub": email.lower(), "role": role,
                                "exp": int(time.time()) + TOKEN_TTL}).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = _b64u(hmac.new(SECRET, signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def decode_token(token: str) -> dict:
    try:
        header, payload, sig = token.split(".")
    except ValueError as exc:
        raise HTTPException(401, "malformed token") from exc
    expected = _b64u(hmac.new(SECRET, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(401, "bad signature")
    data = json.loads(_b64u_dec(payload))
    if data.get("exp", 0) < time.time():
        raise HTTPException(401, "token expired")
    return data


def _current_user(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    return decode_token(authorization.split(" ", 1)[1])


def _require_admin(authorization: str | None) -> dict:
    u = _current_user(authorization)
    if u.get("role") != "admin":
        raise HTTPException(403, "admin only")
    return u


# ----------------------------- schemas ------------------------------------- #
class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("please enter a valid email address")
        return v


class RoleChange(BaseModel):
    role: str


class ActiveChange(BaseModel):
    active: bool


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


# ----------------------------- endpoints ----------------------------------- #
@router.post("/register")
def register(body: Credentials) -> dict:
    if _get(body.email):
        raise HTTPException(409, "email already registered")
    _make_user(body.email, body.password, "operator")  # self-signup is always operator
    return {"access_token": make_token(body.email, "operator"),
            "token_type": "bearer", "email": body.email.lower(), "role": "operator",
            "capabilities": capabilities_for("operator")}


@router.post("/login")
def login(body: Credentials) -> dict:
    row = _get(body.email)
    if not row or not _verify_pw(row, body.password):
        raise HTTPException(401, "invalid email or password")
    if not row["active"]:
        raise HTTPException(403, "this account has been disabled by an administrator")
    return {"access_token": make_token(row["email"], row["role"]),
            "token_type": "bearer", "email": row["email"], "role": row["role"],
            "capabilities": capabilities_for(row["role"])}


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    u = _current_user(authorization)
    return {"email": u["sub"], "role": u["role"],
            "capabilities": capabilities_for(u["role"])}


@router.post("/change-password")
def change_password(body: PasswordChange, authorization: str | None = Header(default=None)) -> dict:
    """Any signed-in user can change their OWN password (operator or admin)."""
    u = _current_user(authorization)
    row = _get(u["sub"])
    if not row or not _verify_pw(row, body.current_password):
        raise HTTPException(401, "current password is incorrect")
    salt = os.urandom(16)
    with _conn() as c:
        c.execute("UPDATE users SET pw_hash=?, salt=? WHERE email=?",
                  (_hash(body.new_password, salt), base64.b64encode(salt).decode(), u["sub"]))
    return {"email": u["sub"], "changed": True}


@router.get("/users")
def list_users(authorization: str | None = Header(default=None)) -> dict:
    _require_admin(authorization)
    with _conn() as c:
        rows = c.execute("SELECT email, role, active, created_at FROM users ORDER BY id").fetchall()
    return {"count": len(rows),
            "users": [{"email": r["email"], "role": r["role"],
                       "active": bool(r["active"]), "created_at": r["created_at"]} for r in rows]}


@router.post("/users/{email}/role")
def set_role(email: str, body: RoleChange, authorization: str | None = Header(default=None)) -> dict:
    admin = _require_admin(authorization)
    if body.role not in ROLES:
        raise HTTPException(422, f"role must be one of {ROLES}")
    if not _get(email):
        raise HTTPException(404, "user not found")
    if email.lower() == admin["sub"] and body.role != "admin":
        raise HTTPException(400, "you cannot remove your own admin role")
    with _conn() as c:
        c.execute("UPDATE users SET role=? WHERE email=?", (body.role, email.lower()))
    return {"email": email.lower(), "role": body.role}


@router.post("/users/{email}/active")
def set_active(email: str, body: ActiveChange, authorization: str | None = Header(default=None)) -> dict:
    """Admin-only: enable or disable a user account. Disabled users cannot log in."""
    admin = _require_admin(authorization)
    if not _get(email):
        raise HTTPException(404, "user not found")
    if email.lower() == admin["sub"] and not body.active:
        raise HTTPException(400, "you cannot disable your own account")
    with _conn() as c:
        c.execute("UPDATE users SET active=? WHERE email=?", (1 if body.active else 0, email.lower()))
    return {"email": email.lower(), "active": body.active}


# ----------------------------- seed ---------------------------------------- #
def seed_users() -> None:
    """Create the DB and the two demo accounts if they do not exist yet."""
    _init_db()
    seeds = [
        ("admin@icsguardian.local", "Admin@12345", "admin"),
        ("operator@icsguardian.local", "Operator@12345", "operator"),
    ]
    for email, pw, role in seeds:
        if not _get(email):
            _make_user(email, pw, role)
