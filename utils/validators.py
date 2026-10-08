"""
VERIDEXA — input validation helpers.
Used by the auth module and the upload pipeline. Pure functions,
no side effects, so they're trivially unit-testable.
"""
import re
from config.settings import PASSWORD_MIN_LENGTH

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,24}$")


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(_EMAIL_RE.match(email.strip()))


def is_valid_username(username: str) -> bool:
    return bool(username) and bool(_USERNAME_RE.match(username.strip()))


def password_strength_errors(password: str) -> list[str]:
    """Return a list of human-readable problems with a password.
    Empty list means the password is acceptable."""
    errors = []
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if not re.search(r"[A-Z]", password or ""):
        errors.append("Must include at least one uppercase letter.")
    if not re.search(r"[a-z]", password or ""):
        errors.append("Must include at least one lowercase letter.")
    if not re.search(r"\d", password or ""):
        errors.append("Must include at least one number.")
    return errors


def allowed_upload_extension(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in {"csv", "xlsx", "xls", "json", "parquet"}


def sanitize_identifier(name: str) -> str:
    """Sanitize a string for safe use as a SQL identifier (table/column name).
    Strips anything that isn't alphanumeric or underscore."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", str(name).strip())
    if cleaned and cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"
    return cleaned or "col"
