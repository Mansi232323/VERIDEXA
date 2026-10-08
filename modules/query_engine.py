"""
VERIDEXA query engine.

This is the architectural backbone of the AI Analyst: the ONLY code
path that is allowed to produce numbers shown to the user. It parses
a natural-language question into a small validated "plan" (operation +
column(s) + optional group-by/filter), checks every piece against the
real DataFrame's actual columns, and only then executes it via Pandas.

There is no `eval`, no blind execution of generated code, and no path
where an LLM's output is displayed as a fact without having been
computed here first. If you wire in an LLM (see ai_analyzer.py), its
only job is allowed to be: propose a plan in this schema, which this
file will independently validate before running anything.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

AGG_ALIASES = {
    "sum": "sum", "total": "sum", "add up": "sum",
    "average": "mean", "avg": "mean", "mean": "mean",
    "max": "max", "maximum": "max", "highest": "max", "largest": "max", "top": "max",
    "min": "min", "minimum": "min", "lowest": "min", "smallest": "min",
    "count": "count", "number of": "count", "how many": "count",
    "median": "median",
    "std": "std", "standard deviation": "std",
    "unique": "nunique", "distinct": "nunique",
}

TREND_HINTS = ("trend", "over time", "by month", "monthly", "by day", "daily",
               "by year", "yearly", "by week", "weekly", "growth")

CORR_HINTS = ("correlation", "correlate", "relationship between", "related to")


class QueryError(Exception):
    """Raised when a question can't be safely mapped to a validated plan."""


@dataclass
class QueryPlan:
    operation: str                       # aggregate | groupby | trend | correlation | filter | describe | topn
    metric_col: str | None = None
    agg_func: str = "sum"
    group_col: str | None = None
    filter_col: str | None = None
    filter_value: str | None = None
    date_col: str | None = None
    freq: str = "ME"
    n: int = 5
    raw_question: str = ""
    resolved_note: str = field(default="")   # e.g. "resolved 'it' -> revenue"


@dataclass
class QueryResult:
    plan: QueryPlan
    data: pd.DataFrame
    scalar: float | int | None
    chart_hint: str          # "kpi" | "bar" | "line" | "table" | "heatmap"
    narration_facts: dict


# ----------------------------------------------------------------------
# Column resolution helpers
# ----------------------------------------------------------------------
def _find_column(question: str, columns: list[str]) -> str | None:
    q = question.lower()
    # exact token match first (longest columns first to prefer specificity)
    for col in sorted(columns, key=len, reverse=True):
        label = col.replace("_", " ")
        if label in q or col in q:
            return col
    return None


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=np.number).columns.tolist()


def _categorical_columns(df: pd.DataFrame) -> list[str]:
    numeric = set(_numeric_columns(df))
    dt = set(df.select_dtypes(include="datetime64[ns]").columns)
    return [c for c in df.columns if c not in numeric and c not in dt]


def _date_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include="datetime64[ns]").columns.tolist()


def _detect_agg(question: str) -> str:
    q = question.lower()
    for phrase, func in sorted(AGG_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if phrase in q:
            return func
    return "sum"


def resolve_pronoun(question: str, last_metric_col: str | None) -> str:
    """Very small conversational-memory resolver: swaps a leading 'it' /
    'that' for the last metric column discussed, e.g. 'what about its
    monthly trend?' -> 'what about revenue's monthly trend?'"""
    if not last_metric_col:
        return question
    pattern = re.compile(r"\b(it|its|that)\b", re.IGNORECASE)
    if pattern.search(question):
        return pattern.sub(last_metric_col.replace("_", " "), question)
    return question


# ----------------------------------------------------------------------
# Planning: question -> validated QueryPlan
# ----------------------------------------------------------------------
def build_plan(question: str, df: pd.DataFrame, last_metric_col: str | None = None) -> QueryPlan:
    if not question or not question.strip():
        raise QueryError("Please type a question.")

    original_question = question
    question = resolve_pronoun(question, last_metric_col)
    note = "" if question == original_question else f"(read 'it/that' as '{last_metric_col}')"

    q = question.lower().strip()
    numeric_cols = _numeric_columns(df)
    cat_cols = _categorical_columns(df)
    date_cols = _date_columns(df)

    metric_col = _find_column(q, numeric_cols)
    group_col = _find_column(q, cat_cols)
    date_col = _find_column(q, date_cols) or (date_cols[0] if date_cols else None)

    # --- correlation --------------------------------------------------
    if any(h in q for h in CORR_HINTS):
        found = [c for c in numeric_cols if c.replace("_", " ") in q or c in q]
        if len(found) >= 2:
            return QueryPlan(operation="correlation", metric_col=found[0],
                              group_col=found[1], raw_question=original_question, resolved_note=note)
        raise QueryError("I need two numeric columns to compute a correlation — "
                          f"try naming two of: {', '.join(numeric_cols)}.")

    # --- trend over time ------------------------------------------------
    if any(h in q for h in TREND_HINTS) and date_col:
        if not metric_col:
            if not numeric_cols:
                raise QueryError("There's no numeric column to trend.")
            metric_col = numeric_cols[0]
        freq = "ME"
        if "week" in q:
            freq = "W"
        elif "day" in q or "daily" in q:
            freq = "D"
        elif "year" in q:
            freq = "YE"
        return QueryPlan(operation="trend", metric_col=metric_col, date_col=date_col,
                          freq=freq, agg_func=_detect_agg(q), raw_question=original_question,
                          resolved_note=note)

    # --- "top N" ranking -------------------------------------------------
    m = re.search(r"top\s+(\d+)", q)
    if m and group_col:
        if not metric_col:
            if not numeric_cols:
                raise QueryError("There's no numeric column to rank by.")
            metric_col = numeric_cols[0]
        return QueryPlan(operation="topn", metric_col=metric_col, group_col=group_col,
                          n=int(m.group(1)), agg_func=_detect_agg(q),
                          raw_question=original_question, resolved_note=note)

    # --- group-by breakdown ----------------------------------------------
    if group_col and (metric_col or numeric_cols):
        metric_col = metric_col or numeric_cols[0]
        return QueryPlan(operation="groupby", metric_col=metric_col, group_col=group_col,
                          agg_func=_detect_agg(q), raw_question=original_question, resolved_note=note)

    # --- plain aggregate ("what is total revenue") -----------------------
    if metric_col:
        return QueryPlan(operation="aggregate", metric_col=metric_col, agg_func=_detect_agg(q),
                          raw_question=original_question, resolved_note=note)

    # --- fallback: describe the dataset -----------------------------------
    if "describe" in q or "summary" in q or "overview" in q:
        return QueryPlan(operation="describe", raw_question=original_question, resolved_note=note)

    raise QueryError(
        "I couldn't match that to a column in your dataset. Try mentioning a specific "
        f"column, e.g.: {', '.join((numeric_cols + cat_cols)[:6])}."
    )


# ----------------------------------------------------------------------
# Execution: validated plan -> real Pandas computation
# ----------------------------------------------------------------------
def execute_plan(plan: QueryPlan, df: pd.DataFrame) -> QueryResult:
    # Defense in depth: re-validate every column reference against the
    # live DataFrame right before executing, even though build_plan()
    # already restricted itself to columns that exist.
    for col in (plan.metric_col, plan.group_col, plan.date_col, plan.filter_col):
        if col is not None and col not in df.columns:
            raise QueryError(f"Column '{col}' is not present in the current dataset.")
    if plan.agg_func not in {"sum", "mean", "max", "min", "count", "median", "std", "nunique"}:
        raise QueryError(f"Unsupported aggregation '{plan.agg_func}'.")

    if plan.operation == "aggregate":
        series = df[plan.metric_col].dropna()
        value = getattr(series, plan.agg_func)()
        return QueryResult(plan, pd.DataFrame({plan.metric_col: [value]}), float(value), "kpi",
                            {"metric": plan.metric_col, "agg": plan.agg_func, "value": float(value),
                             "n_rows": len(series)})

    if plan.operation == "groupby":
        grouped = (df.groupby(plan.group_col)[plan.metric_col]
                   .agg(plan.agg_func).sort_values(ascending=False).reset_index())
        top_row = grouped.iloc[0] if not grouped.empty else None
        return QueryResult(plan, grouped, None, "bar", {
            "metric": plan.metric_col, "group": plan.group_col, "agg": plan.agg_func,
            "top_category": top_row[plan.group_col] if top_row is not None else None,
            "top_value": float(top_row[plan.metric_col]) if top_row is not None else None,
            "n_groups": len(grouped),
        })

    if plan.operation == "topn":
        grouped = (df.groupby(plan.group_col)[plan.metric_col]
                   .agg(plan.agg_func).sort_values(ascending=False).head(plan.n).reset_index())
        return QueryResult(plan, grouped, None, "bar", {
            "metric": plan.metric_col, "group": plan.group_col, "agg": plan.agg_func, "n": plan.n,
        })

    if plan.operation == "trend":
        s = df[[plan.date_col, plan.metric_col]].dropna()
        s = s.set_index(plan.date_col).resample(plan.freq)[plan.metric_col].agg(plan.agg_func).reset_index()
        pct_change = None
        if len(s) >= 2 and s[plan.metric_col].iloc[0] not in (0, None):
            pct_change = float(100 * (s[plan.metric_col].iloc[-1] - s[plan.metric_col].iloc[0])
                                / abs(s[plan.metric_col].iloc[0]))
        return QueryResult(plan, s, None, "line", {
            "metric": plan.metric_col, "freq": plan.freq, "periods": len(s),
            "pct_change": pct_change,
            "first": float(s[plan.metric_col].iloc[0]) if len(s) else None,
            "last": float(s[plan.metric_col].iloc[-1]) if len(s) else None,
        })

    if plan.operation == "correlation":
        sub = df[[plan.metric_col, plan.group_col]].dropna()
        corr = float(sub[plan.metric_col].corr(sub[plan.group_col])) if len(sub) > 1 else float("nan")
        return QueryResult(plan, pd.DataFrame({"correlation": [corr]}), corr, "kpi", {
            "col_a": plan.metric_col, "col_b": plan.group_col, "correlation": corr,
        })

    if plan.operation == "describe":
        desc = df.describe(include="all").T.reset_index().rename(columns={"index": "column"})
        return QueryResult(plan, desc, None, "table", {"n_rows": len(df), "n_cols": df.shape[1]})

    raise QueryError(f"Unknown operation '{plan.operation}'.")


def answer_question(question: str, df: pd.DataFrame, last_metric_col: str | None = None) -> QueryResult:
    plan = build_plan(question, df, last_metric_col)
    return execute_plan(plan, df)
