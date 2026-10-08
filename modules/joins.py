"""
VERIDEXA multi-file / multi-table joins.

Lets a user combine two datasets that are already loaded in the
session (e.g. "orders.csv" + "customers.xlsx") into one table, using
an ordinary Pandas merge. This is deliberately a thin, transparent
wrapper — no query planner, no magic key-guessing beyond a helpful
suggestion — so the result is always exactly what a `pd.merge` with
those parameters would produce.
"""
from __future__ import annotations

import pandas as pd

JOIN_TYPES = {
    "Inner (only matching rows)": "inner",
    "Left (all of the left table)": "left",
    "Right (all of the right table)": "right",
    "Outer (everything, matched or not)": "outer",
}


class JoinError(Exception):
    pass


def suggest_join_keys(left: pd.DataFrame, right: pd.DataFrame) -> list[str]:
    """Columns present (by name) in both frames the most likely join keys."""
    return [c for c in left.columns if c in right.columns]


def join_datasets(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_on: str,
    right_on: str,
    how: str = "inner",
    left_suffix: str = "_left",
    right_suffix: str = "_right",
) -> pd.DataFrame:
    if left is None or right is None or left.empty or right.empty:
        raise JoinError("Both tables need data before they can be joined.")
    if left_on not in left.columns:
        raise JoinError(f"'{left_on}' is not a column in the left table.")
    if right_on not in right.columns:
        raise JoinError(f"'{right_on}' is not a column in the right table.")
    if how not in ("inner", "left", "right", "outer"):
        raise JoinError(f"Unknown join type '{how}'.")

    try:
        merged = left.merge(
            right,
            left_on=left_on,
            right_on=right_on,
            how=how,
            suffixes=(left_suffix, right_suffix),
        )
    except Exception as e:  # noqa: BLE001
        raise JoinError(f"Join failed: {e}") from e

    if merged.empty:
        raise JoinError(
            "The join produced zero rows double-check the key columns actually "
            "share values (e.g. matching IDs), or try a different join type."
        )
    return merged
