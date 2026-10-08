"""
VERIDEXA persistent dataset storage.

By default, an uploaded dataset only lives in the browser session's
memory (`st.session_state`) and disappears when the session ends —
that's the fastest path for a one-off analysis. This module adds an
*opt-in* persistence layer on top: a user can save any dataset (or the
result of a join) into the same SQLite file used for accounts, so it's
still there the next time they log in, from any machine.

Each dataset is serialized to Parquet bytes and stored as a BLOB. That
keeps dtypes (including datetime columns) intact on round-trip, unlike
CSV. Storage is scoped per-user via a UNIQUE(user_id, name) constraint,
so two users can each have a dataset called "sales" without clashing.
"""
from __future__ import annotations

import io

import pandas as pd

from modules.db import get_conn, record_audit
from utils.logger import get_logger

log = get_logger(__name__)


class DatasetStoreError(Exception):
    pass


def save_dataset(user_id: int, name: str, df: pd.DataFrame) -> None:
    """Persist `df` under `name` for `user_id`. Overwrites any existing
    dataset with the same name for that user."""
    name = (name or "").strip()
    if not name:
        raise DatasetStoreError("Please give the dataset a name before saving.")
    if df is None or df.empty:
        raise DatasetStoreError("There's no data to save.")

    buf = io.BytesIO()
    try:
        df.to_parquet(buf, index=False)
    except Exception as e:
        raise DatasetStoreError(
            f"Could not serialize this dataset for storage ({e}). "
            "This usually means a column has mixed/unsupported types "
            "try converting it in Upload & Clean first."
        ) from e
    blob = buf.getvalue()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO saved_datasets (user_id, name, row_count, col_count, size_bytes, data)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, name) DO UPDATE SET
                row_count = excluded.row_count,
                col_count = excluded.col_count,
                size_bytes = excluded.size_bytes,
                data = excluded.data,
                created_at = datetime('now')
            """,
            (user_id, name, df.shape[0], df.shape[1], len(blob), blob),
        )
    record_audit(user_id, "save_dataset", f"name={name} rows={df.shape[0]}")
    log.info("Saved dataset '%s' for user %s (%d rows)", name, user_id, df.shape[0])


def list_saved_datasets(user_id: int) -> pd.DataFrame:
    """Returns a small metadata table (no actual data) of everything
    this user has saved, most recent first."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT name, row_count, col_count, size_bytes, created_at
               FROM saved_datasets WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
    return pd.DataFrame(
        [dict(r) for r in rows],
        columns=["name", "row_count", "col_count", "size_bytes", "created_at"],
    )


def load_dataset(user_id: int, name: str) -> pd.DataFrame:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT data FROM saved_datasets WHERE user_id = ? AND name = ?",
            (user_id, name),
        ).fetchone()
    if row is None:
        raise DatasetStoreError(f"No saved dataset called '{name}' was found.")
    df = pd.read_parquet(io.BytesIO(row["data"]))
    record_audit(user_id, "load_saved_dataset", f"name={name}")
    return df


def delete_dataset(user_id: int, name: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM saved_datasets WHERE user_id = ? AND name = ?",
            (user_id, name),
        )
    record_audit(user_id, "delete_saved_dataset", f"name={name}")
