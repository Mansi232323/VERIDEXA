"""
VERIDEXA anomaly detection.
IQR-based outlier flagging (classical statistics, not a black-box
model) so every flag comes with a plain-language, defensible reason.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect_anomalies(df: pd.DataFrame, column: str, id_cols: list[str] | None = None) -> pd.DataFrame:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")
    s = df[column]
    if not pd.api.types.is_numeric_dtype(s):
        raise ValueError(f"Column '{column}' is not numeric.")

    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    extreme_lo, extreme_hi = q1 - 3.0 * iqr, q3 + 3.0 * iqr

    mask = (s < lo) | (s > hi)
    if not mask.any():
        return pd.DataFrame()

    result = df.loc[mask].copy()
    result["_value"] = s[mask]

    def _risk(v):
        if v < extreme_lo or v > extreme_hi:
            return "High"
        return "Medium"

    def _reason(v):
        if v > hi:
            return f"{v:,.2f} is above the upper fence ({hi:,.2f}) — unusually high for '{column}'."
        return f"{v:,.2f} is below the lower fence ({lo:,.2f}) — unusually low for '{column}'."

    result["risk_level"] = result["_value"].apply(_risk)
    result["reason"] = result["_value"].apply(_reason)
    result = result.drop(columns=["_value"])

    cols_to_show = (id_cols or []) + [column, "risk_level", "reason"]
    cols_to_show = [c for c in dict.fromkeys(cols_to_show) if c in result.columns]
    ordered = result[cols_to_show + [c for c in result.columns if c not in cols_to_show]]
    return ordered.sort_values("risk_level").reset_index(drop=True)


def anomaly_summary(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = []
    for col in columns:
        try:
            found = detect_anomalies(df, col)
        except ValueError:
            continue
        rows.append({
            "column": col,
            "anomalies_found": len(found),
            "high_risk": int((found["risk_level"] == "High").sum()) if len(found) else 0,
            "pct_of_data": round(100 * len(found) / len(df), 2) if len(df) else 0.0,
        })
    return pd.DataFrame(rows).sort_values("anomalies_found", ascending=False)
