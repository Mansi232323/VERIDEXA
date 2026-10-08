"""
VERIDEXA data cleaning actions.
Every function here is explicit and reversible-by-choice: nothing is
applied automatically. The UI lets the user pick which actions to run.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def drop_duplicate_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(df)
    out = df.drop_duplicates().reset_index(drop=True)
    return out, before - len(out)


def fill_missing(df: pd.DataFrame, strategy: str, columns: list[str] | None = None) -> tuple[pd.DataFrame, int]:
    """strategy: 'mean' | 'median' | 'mode' | 'zero' | 'drop_rows' | 'ffill' | 'bfill'"""
    df = df.copy()
    columns = columns or df.columns.tolist()
    filled = 0

    if strategy == "drop_rows":
        before = len(df)
        df = df.dropna(subset=columns).reset_index(drop=True)
        return df, before - len(df)

    for col in columns:
        if col not in df.columns:
            continue
        n_missing = int(df[col].isna().sum())
        if n_missing == 0:
            continue
        if strategy == "mean" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].mean())
        elif strategy == "median" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
        elif strategy == "mode":
            mode = df[col].mode(dropna=True)
            if not mode.empty:
                df[col] = df[col].fillna(mode.iloc[0])
        elif strategy == "zero" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(0)
        elif strategy == "ffill":
            df[col] = df[col].ffill()
        elif strategy == "bfill":
            df[col] = df[col].bfill()
        else:
            continue
        filled += n_missing - int(df[col].isna().sum())

    return df, filled


def cap_outliers_iqr(df: pd.DataFrame, columns: list[str] | None = None) -> tuple[pd.DataFrame, int]:
    """Winsorize numeric columns to the 1.5*IQR fence instead of dropping rows."""
    df = df.copy()
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    columns = [c for c in (columns or numeric_cols) if c in numeric_cols]
    capped = 0
    for col in columns:
        s = df[col]
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = (s < lo) | (s > hi)
        capped += int(mask.sum())
        df[col] = s.clip(lower=lo, upper=hi)
    return df, capped


def remove_outliers_iqr(df: pd.DataFrame, columns: list[str] | None = None) -> tuple[pd.DataFrame, int]:
    df = df.copy()
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    columns = [c for c in (columns or numeric_cols) if c in numeric_cols]
    before = len(df)
    mask = pd.Series(True, index=df.index)
    for col in columns:
        s = df[col]
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask &= s.between(lo, hi) | s.isna()
    df = df[mask].reset_index(drop=True)
    return df, before - len(df)


def convert_column_type(df: pd.DataFrame, column: str, target: str) -> pd.DataFrame:
    """target: 'numeric' | 'text' | 'datetime' | 'category'"""
    df = df.copy()
    if column not in df.columns:
        return df
    if target == "numeric":
        df[column] = pd.to_numeric(df[column], errors="coerce")
    elif target == "text":
        df[column] = df[column].astype(str)
    elif target == "datetime":
        df[column] = pd.to_datetime(df[column], errors="coerce", format="mixed")
    elif target == "category":
        df[column] = df[column].astype("category")
    return df


def cleaning_suggestions(df: pd.DataFrame) -> list[str]:
    """Human-readable, non-destructive suggestions shown to the user
    before they pick which cleaning actions to apply."""
    tips = []
    n = len(df)
    dup = int(df.duplicated().sum())
    if dup:
        tips.append(f"Found {dup} duplicate row(s) ({100*dup/n:.1f}% of data) — consider dropping them.")

    missing = df.isna().sum()
    bad_cols = missing[missing > 0].sort_values(ascending=False)
    for col, cnt in bad_cols.items():
        pct = 100 * cnt / n
        if pct > 40:
            tips.append(f"Column '{col}' is {pct:.0f}% missing consider dropping it entirely.")
        elif pct > 0:
            tips.append(f"Column '{col}' has {cnt} missing value(s) ({pct:.1f}%) — fill or drop rows.")

    numeric_cols = df.select_dtypes(include=np.number).columns
    for col in numeric_cols:
        s = df[col].dropna()
        if len(s) < 4:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((s < lo) | (s > hi)).sum())
        if n_out:
            tips.append(f"Column '{col}' has {n_out} statistical outlier(s) review before modeling.")

    if not tips:
        tips.append("No major data-quality issues detected. Your data looks clean!")
    return tips
