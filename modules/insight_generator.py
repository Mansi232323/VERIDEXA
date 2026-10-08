"""
VERIDEXA insight generator.

Turns the *already-computed* facts inside a QueryResult (see
query_engine.py) into a four-part narrative: Finding / Explanation /
Business Impact / Recommendation. This module never invents a number
it only phrases numbers that query_engine.py already validated and
computed. Swap `narrate()` for a call into ai_analyzer.py if you want
an LLM to phrase these more fluently; the facts dict passed in is the
hard contract it must not deviate from.
"""
from __future__ import annotations

from modules.query_engine import QueryResult


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    try:
        if abs(value) >= 1_000_000:
            return f"{value/1_000_000:,.2f}M"
        if abs(value) >= 1_000:
            return f"{value:,.2f}"
        return f"{value:,.3f}" if isinstance(value, float) else f"{value:,}"
    except TypeError:
        return str(value)


def narrate(result: QueryResult) -> dict:
    facts = result.narration_facts
    op = result.plan.operation

    if op == "aggregate":
        metric = facts["metric"].replace("_", " ")
        agg = facts["agg"]
        val = facts["value"]
        finding = f"The {agg} of {metric} across {facts['n_rows']:,} records is {_fmt(val)}."
        explanation = (f"This was computed directly from the dataset with pandas "
                        f"({agg}() over the '{facts['metric']}' column) no estimation involved.")
        impact = ("Use this as your baseline figure when comparing performance across "
                   "time periods, segments, or against targets.")
        recommendation = ("Break this number down by a category (e.g. region or product) "
                           "to see where it's concentrated try asking "
                           f"\"{metric} by <category>\".")

    elif op == "groupby":
        metric = facts["metric"].replace("_", " ")
        group = facts["group"].replace("_", " ")
        top_cat = facts["top_category"]
        top_val = facts["top_value"]
        finding = (f"'{top_cat}' leads on {facts['agg']} {metric}, at {_fmt(top_val)}, "
                   f"across {facts['n_groups']} distinct {group} value(s).")
        explanation = (f"Grouped the dataset by '{facts['group']}' and applied "
                        f"{facts['agg']}() to '{facts['metric']}' for each group.")
        impact = (f"If '{top_cat}' is disproportionately large, it may represent concentration "
                   "risk (or a strong performer worth doubling down on) worth investigating why.")
        recommendation = (f"Compare the top and bottom {group} values to see the full spread, "
                           "or trend the leader over time to check whether it's growing or shrinking.")

    elif op == "topn":
        metric = facts["metric"].replace("_", " ")
        group = facts["group"].replace("_", " ")
        finding = f"Showing the top {facts['n']} {group} values ranked by {facts['agg']} {metric}."
        explanation = f"Grouped by '{facts['group']}', aggregated '{facts['metric']}' with {facts['agg']}(), sorted descending."
        impact = "These are your highest-leverage segments for this metric right now."
        recommendation = "Consider whether resources should be reallocated toward or away from these leaders."

    elif op == "trend":
        metric = facts["metric"].replace("_", " ")
        pct = facts["pct_change"]
        direction = "up" if (pct or 0) >= 0 else "down"
        pct_str = f"{abs(pct):.1f}%" if pct is not None else "an unmeasurable amount"
        finding = (f"{metric.title()} moved {direction} by {pct_str} from the first to the last "
                   f"period across {facts['periods']} periods (first: {_fmt(facts['first'])}, "
                   f"last: {_fmt(facts['last'])}).")
        explanation = (f"Resampled the date column by frequency '{facts['freq']}' and aggregated "
                        f"'{result.plan.metric_col}' per period.")
        impact = ("A sustained trend in either direction should feed directly into forecasting "
                   "and target-setting for next period.")
        recommendation = ("Open the Forecasting page to project this trend forward, or check "
                           "Anomaly Detection to see if any single period is skewing the trend.")

    elif op == "correlation":
        a = facts["col_a"].replace("_", " ")
        b = facts["col_b"].replace("_", " ")
        r = facts["correlation"]
        strength = _corr_strength(r)
        finding = f"The correlation between {a} and {b} is r = {r:.3f} ({strength})."
        explanation = "Computed with pandas' Pearson correlation on paired, non-null values from both columns."
        impact = ("A strong correlation doesn't prove causation, but it's a solid signal for "
                   "which levers move together and may be worth testing directly.")
        recommendation = "If this looks actionable, try the What-if / segmentation views to explore it further."

    elif op == "describe":
        finding = f"Dataset has {facts['n_rows']:,} rows and {facts['n_cols']} columns."
        explanation = "Full descriptive statistics computed via pandas describe(include='all')."
        impact = "Use this as your starting map before diving into specific questions."
        recommendation = "Try asking about a specific column by name, e.g. 'total revenue' or 'average profit by region'."

    else:  # pragma: no cover
        finding = "Computed a result."
        explanation = "See the table for details."
        impact = "N/A"
        recommendation = "Try a more specific question."

    return {
        "finding": finding,
        "explanation": explanation,
        "business_impact": impact,
        "recommendation": recommendation,
    }


def _corr_strength(r: float) -> str:
    if r != r:  # NaN check
        return "undefined"
    a = abs(r)
    if a >= 0.7:
        label = "strong"
    elif a >= 0.4:
        label = "moderate"
    elif a >= 0.2:
        label = "weak"
    else:
        label = "negligible"
    direction = "positive" if r >= 0 else "negative"
    return f"{label} {direction}"
