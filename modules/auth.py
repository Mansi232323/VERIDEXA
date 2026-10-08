"""
VERIDEXA authentication.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib `hashlib`, no
external crypto dependency required). Each user gets a unique random
salt. This is intentionally dependency-free so the app has zero
extra install friction; swap in `bcrypt`/`argon2-cffi` here later
if you want a drop-in stronger KDF — the rest of the app never touches
raw passwords, so the change is fully contained to this file.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass

from config.settings import LOGIN_LOCKOUT_MINUTES, MAX_LOGIN_ATTEMPTS, PBKDF2_ITERATIONS
from modules.db import get_conn, record_audit, recent_failed_login_count
from utils.logger import get_logger
from utils.validators import is_valid_email, is_valid_username, password_strength_errors

log = get_logger(__name__)


@dataclass
class User:
    id: int
    username: str
    email: str
    full_name: str | None


class AuthError(Exception):
    """Raised for any user-facing auth failure (bad creds, dup account, etc.)."""


# --------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------
def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return dk.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    candidate, _ = _hash_password(password, salt)
    return secrets.compare_digest(candidate, stored_hash)


# --------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------
def signup(username: str, email: str, password: str, confirm_password: str,
           full_name: str = "") -> User:
    username = (username or "").strip()
    email = (email or "").strip().lower()

    if not is_valid_username(username):
        raise AuthError("Username must be 3-24 characters: letters, numbers, underscore only.")
    if not is_valid_email(email):
        raise AuthError("Please enter a valid email address.")
    if password != confirm_password:
        raise AuthError("Passwords do not match.")
    pw_errors = password_strength_errors(password)
    if pw_errors:
        raise AuthError(" ".join(pw_errors))

    password_hash, salt = _hash_password(password)

    try:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO users (username, email, password_hash, salt, full_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (username, email, password_hash, salt, full_name.strip() or None),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if "username" in msg:
            raise AuthError("That username is already taken.") from e
        if "email" in msg:
            raise AuthError("An account with that email already exists.") from e
        raise AuthError("Could not create account please try different details.") from e

    record_audit(user_id, "signup", f"username={username}")
    log.info("New user signed up: %s", username)
    return User(id=user_id, username=username, email=email, full_name=full_name or None)


def login(identifier: str, password: str) -> User:
    """`identifier` may be a username or an email."""
    identifier = (identifier or "").strip()
    if not identifier or not password:
        raise AuthError("Please enter your username/email and password.")

    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM users
               WHERE (username = ? OR email = ?) AND is_active = 1""",
            (identifier, identifier.lower()),
        ).fetchone()

    if row is None:
        record_audit(None, "login_failed", f"identifier={identifier}")
        raise AuthError("No account found with those credentials.")

    recent_failures = recent_failed_login_count(row["username"], LOGIN_LOCKOUT_MINUTES)
    if recent_failures >= MAX_LOGIN_ATTEMPTS:
        record_audit(row["id"], "login_blocked_lockout")
        raise AuthError(
            f"Too many failed attempts. Please try again in {LOGIN_LOCKOUT_MINUTES} minutes."
        )

    if not _verify_password(password, row["password_hash"], row["salt"]):
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO login_attempts (username, success) VALUES (?, 0)",
                (row["username"],),
            )
        record_audit(row["id"], "login_failed")
        raise AuthError("Incorrect password.")

    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (row["id"],)
        )
        conn.execute(
            "INSERT INTO login_attempts (username, success) VALUES (?, 1)",
            (row["username"],),
        )
    record_audit(row["id"], "login_success")
    log.info("User logged in: %s", row["username"])
    return User(id=row["id"], username=row["username"], email=row["email"],
                full_name=row["full_name"])


def change_password(user_id: int, old_password: str, new_password: str,
                     confirm_password: str) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise AuthError("User not found.")
    if not _verify_password(old_password, row["password_hash"], row["salt"]):
        raise AuthError("Current password is incorrect.")
    if new_password != confirm_password:
        raise AuthError("New passwords do not match.")
    pw_errors = password_strength_errors(new_password)
    if pw_errors:
        raise AuthError(" ".join(pw_errors))

    new_hash, new_salt = _hash_password(new_password)
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (new_hash, new_salt, user_id),
        )
    record_audit(user_id, "password_changed")
