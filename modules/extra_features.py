"""
VERIDEXA extra features module.
Self-contained helpers for: data health scoring, per-column quality
traffic lights, word clouds, dataset diffing, period-over-period
comparison, sparklines, CSV templates, and chart-type suggestion.
Every function here only reads data already in memory — no new
external dependency, no network call, no LLM.
"""
from __future__ import annotations

import io
import math
import random

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from modules.visualization import ACCENT, ACCENT2, PALETTE, TEMPLATE, _base_layout


# ----------------------------------------------------------------------
# 3. Data Health Score
# ----------------------------------------------------------------------
def health_score(df: pd.DataFrame) -> dict:
    """A single 0-100 score plus its three ingredients, so the number is
    always explainable rather than a black box."""
    if df.empty:
        return {"score": 0, "completeness": 0, "uniqueness": 0, "consistency": 0}

    completeness = 100 * (1 - df.isna().sum().sum() / (df.shape[0] * df.shape[1]))
    dup_ratio = df.duplicated().sum() / max(len(df), 1)
    uniqueness = 100 * (1 - dup_ratio)

    # "Consistency": share of columns whose dtype looks stable (not an
    # object column secretly holding mixed numeric/text values).
    consistent_cols = 0
    for col in df.columns:
        if df[col].dtype != object:
            consistent_cols += 1
            continue
        sample = df[col].dropna().astype(str).head(200)
        if sample.empty:
            consistent_cols += 1
            continue
        looks_numeric = sample.str.replace(".", "", regex=False).str.replace("-", "", regex=False).str.isnumeric()
        ratio = looks_numeric.mean()
        if ratio == 0 or ratio == 1:
            consistent_cols += 1
    consistency = 100 * consistent_cols / max(df.shape[1], 1)

    score = round(0.45 * completeness + 0.25 * uniqueness + 0.30 * consistency)
    return {
        "score": int(max(0, min(100, score))),
        "completeness": round(completeness, 1),
        "uniqueness": round(uniqueness, 1),
        "consistency": round(consistency, 1),
    }


def health_score_badge_color(score: int) -> str:
    if score >= 85:
        return "#1DD1A1"
    if score >= 60:
        return "#FFC048"
    return "#FF6B6B"


# ----------------------------------------------------------------------
# 4. Per-column quality traffic lights
# ----------------------------------------------------------------------
def quality_traffic_lights(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(df)
    for col in df.columns:
        missing_pct = round(100 * df[col].isna().sum() / n, 1) if n else 0.0
        nunique = df[col].nunique(dropna=True)
        if missing_pct >= 20:
            status = "🔴"
        elif missing_pct >= 5:
            status = "🟡"
        else:
            status = "🟢"
        rows.append({
            "column": col, "status": status, "dtype": str(df[col].dtype),
            "missing_%": missing_pct, "unique_values": nunique,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 6. Word cloud (dependency-free — sized/positioned scatter of top terms)
# ----------------------------------------------------------------------
def wordcloud_figure(df: pd.DataFrame, col: str, top_n: int = 40, title: str = "") -> go.Figure:
    text = df[col].dropna().astype(str)
    tokens: list[str] = []
    for val in text:
        tokens.extend([t.lower() for t in val.replace(",", " ").split() if len(t) > 2])
    if not tokens:
        return _base_layout(go.Figure(), title or f"No text tokens found in '{col}'")

    counts = pd.Series(tokens).value_counts().head(top_n)
    rng = random.Random(42)
    xs, ys, sizes, colors, labels = [], [], [], [], []
    max_count = counts.max()
    for i, (word, cnt) in enumerate(counts.items()):
        angle = i * 2.399963  # golden-angle spiral so words don't overlap much
        radius = 0.9 * math.sqrt(i + 1)
        xs.append(radius * math.cos(angle) + rng.uniform(-0.3, 0.3))
        ys.append(radius * math.sin(angle) + rng.uniform(-0.3, 0.3))
        sizes.append(14 + 46 * (cnt / max_count))
        colors.append(PALETTE[i % len(PALETTE)])
        labels.append(f"{word} ({cnt})")

    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="text",
        text=[w for w in counts.index],
        textfont=dict(size=sizes, color=colors),
        hovertext=labels, hoverinfo="text",
    ))
    fig.update_xaxes(visible=False, showgrid=False, zeroline=False)
    fig.update_yaxes(visible=False, showgrid=False, zeroline=False)
    fig.update_layout(template=TEMPLATE, title=title or f"Word cloud — {col}",
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       margin=dict(l=10, r=10, t=50, b=10), height=460)
    return fig


# ----------------------------------------------------------------------
# 7. Period-over-period comparison
# ----------------------------------------------------------------------
def period_over_period(df: pd.DataFrame, date_col: str, metric_col: str, freq: str = "ME") -> dict | None:
    work = df[[date_col, metric_col]].dropna()
    if work.empty:
        return None
    series = work.set_index(date_col)[metric_col].resample(freq).sum()
    if len(series) < 2:
        return None
    current, previous = series.iloc[-1], series.iloc[-2]
    pct_change = None if previous == 0 else 100 * (current - previous) / previous
    return {
        "current_period": series.index[-1], "previous_period": series.index[-2],
        "current_value": float(current), "previous_value": float(previous),
        "pct_change": None if pct_change is None else round(pct_change, 1),
    }


# ----------------------------------------------------------------------
# 8. Dataset diff / schema compare
# ----------------------------------------------------------------------
def diff_datasets(df1: pd.DataFrame, df2: pd.DataFrame, name1: str, name2: str) -> pd.DataFrame:
    cols1, cols2 = set(df1.columns), set(df2.columns)
    rows = [
        {"metric": "Rows", name1: df1.shape[0], name2: df2.shape[0]},
        {"metric": "Columns", name1: df1.shape[1], name2: df2.shape[1]},
        {"metric": "Only in " + name1, name1: ", ".join(sorted(cols1 - cols2)) or "—", name2: ""},
        {"metric": "Only in " + name2, name1: "", name2: ", ".join(sorted(cols2 - cols1)) or "—"},
        {"metric": "Duplicate rows", name1: int(df1.duplicated().sum()), name2: int(df2.duplicated().sum())},
        {"metric": "Missing values", name1: int(df1.isna().sum().sum()), name2: int(df2.isna().sum().sum())},
    ]
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 12. CSV template
# ----------------------------------------------------------------------
def csv_template_bytes(columns: list[str]) -> bytes:
    buf = io.StringIO()
    pd.DataFrame(columns=columns).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


# ----------------------------------------------------------------------
# 5. Inline sparkline (pure SVG string — no JS, safe inside st.markdown)
# ----------------------------------------------------------------------
def sparkline_svg(values, color: str = ACCENT, width: int = 110, height: int = 30) -> str:
    vals = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = (i / (n - 1)) * (width - 4) + 2
        y = height - 2 - ((v - lo) / span) * (height - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    points = " ".join(pts)
    last_x, last_y = pts[-1].split(",")
    return f"""<svg width="{width}" height="{height}" style="vertical-align:middle;">
      <polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="{last_x}" cy="{last_y}" r="2.6" fill="{ACCENT2}"/>
    </svg>"""


# ----------------------------------------------------------------------
# 20. Chart-type suggestion
# ----------------------------------------------------------------------
def suggest_chart(df: pd.DataFrame, col_a: str, col_b: str | None = None) -> dict:
    a_is_num = pd.api.types.is_numeric_dtype(df[col_a])
    a_is_date = pd.api.types.is_datetime64_any_dtype(df[col_a])
    if col_b is None:
        if a_is_date:
            return {"chart": "line", "reason": f"'{col_a}' is a date a line chart shows it over time."}
        if a_is_num:
            return {"chart": "histogram", "reason": f"'{col_a}' is numeric a histogram shows its distribution."}
        return {"chart": "bar", "reason": f"'{col_a}' is categorical a bar chart shows value frequency."}

    b_is_num = pd.api.types.is_numeric_dtype(df[col_b])
    b_is_date = pd.api.types.is_datetime64_any_dtype(df[col_b])

    if a_is_date and b_is_num:
        return {"chart": "line", "reason": "date + numeric → trend line over time."}
    if b_is_date and a_is_num:
        return {"chart": "line", "reason": "date + numeric → trend line over time."}
    if a_is_num and b_is_num:
        return {"chart": "scatter", "reason": "two numeric columns → scatter shows their relationship."}
    if (not a_is_num) and b_is_num:
        nun = df[col_a].nunique(dropna=True)
        if nun <= 8:
            return {"chart": "pie", "reason": f"'{col_a}' has only {nun} categories → pie shows the share of each."}
        return {"chart": "bar", "reason": f"'{col_a}' is categorical, '{col_b}' numeric → bar compares totals."}
    if a_is_num and (not b_is_num):
        return {"chart": "bar", "reason": f"'{col_b}' is categorical, '{col_a}' numeric → bar compares totals."}
    return {"chart": "bar", "reason": "two categorical columns → bar shows counts."}
