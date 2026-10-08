"""
VERIDEXA automated EDA (exploratory data analysis).
One-click report: correlations, outliers, and key findings — all
derived from data_profiler.py's real computations, then phrased.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from modules.data_profiler import correlation_matrix, outlier_scan, overview


def generate_eda_report(df: pd.DataFrame) -> dict:
    ov = overview(df)
    corr = correlation_matrix(df)
    outliers = outlier_scan(df)

    findings = []
    findings.append(f"Dataset contains {ov['rows']:,} rows and {ov['columns']} columns "
                     f"({ov['memory_mb']} MB in memory).")

    if ov["duplicate_rows"]:
        findings.append(f"{ov['duplicate_rows']:,} duplicate row(s) detected "
                         f"({100*ov['duplicate_rows']/max(ov['rows'],1):.1f}% of data).")

    if ov["total_missing_cells"]:
        findings.append(f"{ov['total_missing_cells']:,} missing cell(s) overall "
                         f"({ov['missing_pct']}% of all values).")
    else:
        findings.append("No missing values detected the dataset is complete.")

    strong_pairs = []
    if not corr.empty:
        cols = corr.columns.tolist()
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                r = corr.iloc[i, j]
                if pd.notna(r) and abs(r) >= 0.6:
                    strong_pairs.append((cols[i], cols[j], round(float(r), 3)))
        strong_pairs.sort(key=lambda t: -abs(t[2]))
        for a, b, r in strong_pairs[:5]:
            direction = "positively" if r > 0 else "negatively"
            findings.append(f"'{a}' and '{b}' are strongly {direction} correlated (r = {r}).")

    if not outliers.empty:
        top_outlier_col = outliers.sort_values("outlier_count", ascending=False).iloc[0]
        if top_outlier_col["outlier_count"] > 0:
            findings.append(
                f"'{top_outlier_col['column']}' has the most statistical outliers "
                f"({int(top_outlier_col['outlier_count'])}, {top_outlier_col['outlier_pct']}% of values)."
            )

    recommendations = []
    if ov["duplicate_rows"]:
        recommendations.append("Drop duplicate rows before running any aggregation or model.")
    if ov["total_missing_cells"]:
        recommendations.append("Review columns with high missingness fill, impute, or drop as appropriate.")
    if strong_pairs:
        recommendations.append("Investigate the strongly correlated pairs above for potential redundancy or causal levers.")
    if not outliers.empty and outliers["outlier_count"].sum() > 0:
        recommendations.append("Review flagged outliers in Anomaly Detection before forecasting or segmenting.")
    if not recommendations:
        recommendations.append("Data looks clean and ready head to the AI Analyst or Dashboard to start exploring.")

    return {
        "overview": ov,
        "correlation_matrix": corr,
        "outliers": outliers,
        "key_findings": findings,
        "recommendations": recommendations,
        "strong_correlations": strong_pairs,
    }
