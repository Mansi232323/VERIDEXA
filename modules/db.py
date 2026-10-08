"""
VERIDEXA persistent app database (users, sessions metadata, saved
insights). This is separate from the per-session in-memory SQLite
database that holds the user's uploaded dataset (see query_engine.py).
"""
import sqlite3
from contextlib import contextmanager
from config.settings import DB_PATH
from utils.logger import get_logger

log = get_logger(__name__)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # WAL mode lets one writer and many readers work concurrently, which
    # matters once more than one browser session is hitting this file at
    # the same time (the normal case for a multi-user deployment).
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't already exist. Safe to call every boot."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL,
                full_name     TEXT,
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                last_login_at TEXT,
                is_active     INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_attempts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT NOT NULL,
                success     INTEGER NOT NULL,
                attempted_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_insights (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title      TEXT NOT NULL,
                question   TEXT,
                summary    TEXT,
                chart_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action     TEXT NOT NULL,
                detail     TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_datasets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name         TEXT NOT NULL,
                row_count    INTEGER NOT NULL,
                col_count    INTEGER NOT NULL,
                size_bytes   INTEGER NOT NULL,
                data         BLOB NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, name)
            );
            """
        )
    log.info("Database initialized at %s", DB_PATH)


def record_audit(user_id: int | None, action: str, detail: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)",
            (user_id, action, detail),
        )


def fetch_audit_log(user_id: int | None, limit: int = 200):
    """Feature 13: Activity Log page — returns this user's recent
    audit_log rows, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT action, detail, created_at FROM audit_log "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def recent_failed_login_count(username: str, minutes: int) -> int:
    """How many failed login attempts `username` has racked up in the
    last `minutes` minutes. Used to implement a temporary lockout."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS n FROM login_attempts
               WHERE username = ? AND success = 0
                 AND attempted_at >= datetime('now', ?)""",
            (username, f"-{int(minutes)} minutes"),
        ).fetchone()
    return int(row["n"]) if row else 0
