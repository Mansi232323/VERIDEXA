"""VERIDEXA — small shared formatting helpers used across pages."""
from __future__ import annotations

import math


def human_number(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(v):
        return "—"
    if math.isinf(v):
        return "∞" if v > 0 else "-∞"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:,.2f}B"
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:,.2f}M"
    if v >= 1_000:
        return f"{sign}{v/1_000:,.1f}K"
    if v == int(v):
        return f"{sign}{int(v):,}"
    return f"{sign}{v:,.2f}"


def full_number(value) -> str:
    """Never-abbreviated formatting — the counterpart to human_number(),
    used when the user toggles 'full numbers' instead of compact K/M/B."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(v):
        return "—"
    if math.isinf(v):
        return "∞" if v > 0 else "-∞"
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:,.2f}"


def display_number(value, compact: bool = True) -> str:
    """Respects the app-wide compact/full number-format toggle."""
    return human_number(value) if compact else full_number(value)


def pct(value, decimals: int = 1) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(v):
        return "—"
    return f"{v:.{decimals}f}%"
