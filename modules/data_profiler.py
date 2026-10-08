"""
VERIDEXA data profiling.
Pure Pandas/NumPy computation; produces the numbers behind the
Data Explorer page. No LLM involved anywhere in this file.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def overview(df: pd.DataFrame) -> dict:
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    datetime_cols = df.select_dtypes(include="datetime64[ns]").columns.tolist()
    categorical_cols = [c for c in df.columns if c not in numeric_cols and c not in datetime_cols]

    return {
        "rows": len(df),
        "columns": df.shape[1],
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
        "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 3),
        "duplicate_rows": int(df.duplicated().sum()),
        "total_missing_cells": int(df.isna().sum().sum()),
        "missing_pct": round(100 * df.isna().sum().sum() / (df.shape[0] * df.shape[1]), 2)
        if df.size else 0.0,
    }


def data_quality_report(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        missing = int(s.isna().sum())
        rows.append({
            "column": col,
            "dtype": str(s.dtype),
            "missing": missing,
            "missing_pct": round(100 * missing / n, 2) if n else 0.0,
            "unique": int(s.nunique(dropna=True)),
            "unique_pct": round(100 * s.nunique(dropna=True) / n, 2) if n else 0.0,
        })
    return pd.DataFrame(rows)


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=np.number).columns
    if len(numeric_cols) == 0:
        return pd.DataFrame()
    desc = df[numeric_cols].describe().T
    desc["skew"] = df[numeric_cols].skew()
    desc["missing"] = df[numeric_cols].isna().sum()
    return desc.round(3)


def categorical_summary(df: pd.DataFrame, top_n: int = 5) -> dict[str, pd.DataFrame]:
    numeric_cols = set(df.select_dtypes(include=np.number).columns)
    datetime_cols = set(df.select_dtypes(include="datetime64[ns]").columns)
    cat_cols = [c for c in df.columns if c not in numeric_cols and c not in datetime_cols]

    out = {}
    for col in cat_cols:
        vc = df[col].value_counts(dropna=True).head(top_n)
        pct = (100 * vc / len(df)).round(2)
        out[col] = pd.DataFrame({"value": vc.index, "count": vc.values, "pct": pct.values})
    return out


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=np.number).columns
    if len(numeric_cols) < 2:
        return pd.DataFrame()
    return df[numeric_cols].corr(numeric_only=True).round(3)


def outlier_scan(df: pd.DataFrame) -> pd.DataFrame:
    """IQR-based outlier counts per numeric column used both in the
    quality report and to seed the Anomaly Detection page."""
    numeric_cols = df.select_dtypes(include=np.number).columns
    rows = []
    for col in numeric_cols:
        s = df[col].dropna()
        if len(s) < 4:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((s < lo) | (s > hi)).sum())
        rows.append({
            "column": col, "q1": round(q1, 3), "q3": round(q3, 3),
            "lower_bound": round(lo, 3), "upper_bound": round(hi, 3),
            "outlier_count": n_out, "outlier_pct": round(100 * n_out / len(s), 2),
        })
    return pd.DataFrame(rows)
