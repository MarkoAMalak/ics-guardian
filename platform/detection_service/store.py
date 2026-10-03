"""
store.py - storage backend for users and shared settings.

By default the service keeps its user store in a local SQLite file (fine for one replica or a
demo). Set AUTH_DB_URL to a PostgreSQL URL, e.g.

    AUTH_DB_URL=postgresql://ics:secret@postgres:5432/ics

and every replica shares the same users and the same detection settings, so an account created
on one pod, or a threshold changed by an administrator, is seen by all pods.

Both backends expose the same tiny interface: ``with connect() as db: db.execute(sql, params)``,
with SQL written using ``?`` placeholders and rows readable by column name.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

DB_URL = os.getenv("AUTH_DB_URL", "").strip()
DB_PATH = Path(os.getenv("AUTH_DB", Path(__file__).parent / "data" / "users.db"))
IS_POSTGRES = DB_URL.startswith(("postgresql://", "postgres://"))


class _PgConn:
    """Adapter so PostgreSQL (psycopg 3) accepts the same ``?``-style SQL as sqlite3."""

    def __init__(self, url: str):
        import psycopg
        from psycopg.rows import dict_row

        self._c = psycopg.connect(url, row_factory=dict_row, connect_timeout=5)

    def execute(self, sql: str, params: tuple = ()):
        return self._c.execute(sql.replace("?", "%s"), params)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._c.commit()
        else:
            self._c.rollback()
        self._c.close()


class _SqliteConn:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._c = sqlite3.connect(path, timeout=10)
        self._c.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()):
        return self._c.execute(sql, params)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._c.commit()
        else:
            self._c.rollback()
        self._c.close()


def connect():
    return _PgConn(DB_URL) if IS_POSTGRES else _SqliteConn(DB_PATH)


def backend() -> str:
    return "postgresql" if IS_POSTGRES else "sqlite"


def init_schema() -> None:
    pk = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts = "BIGINT" if IS_POSTGRES else "INTEGER"
    with connect() as db:
        db.execute(
            f"""CREATE TABLE IF NOT EXISTS users(
                   id {pk},
                   email TEXT UNIQUE NOT NULL,
                   pw_hash TEXT NOT NULL,
                   salt TEXT NOT NULL,
                   role TEXT NOT NULL DEFAULT 'operator',
                   active INTEGER NOT NULL DEFAULT 1,
                   created_at {ts} NOT NULL)"""
        )
        db.execute(
            f"""CREATE TABLE IF NOT EXISTS settings(
                   key TEXT PRIMARY KEY,
                   value TEXT NOT NULL,
                   updated_by TEXT,
                   updated_at {ts} NOT NULL)"""
        )
        if not IS_POSTGRES:  # migrate SQLite files that predate the 'active' column
            cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
            if "active" not in cols:
                db.execute("ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1")


def get_setting(key: str) -> str | None:
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return None if row is None else row["value"]


def set_setting(key: str, value: str, user: str | None = None) -> None:
    now = int(time.time())
    with connect() as db:
        db.execute(
            "INSERT INTO settings(key, value, updated_by, updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_by=excluded.updated_by, updated_at=excluded.updated_at",
            (key, value, user, now),
        )


def delete_setting(key: str) -> None:
    with connect() as db:
        db.execute("DELETE FROM settings WHERE key=?", (key,))
