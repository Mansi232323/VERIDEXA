"""
VERIDEXA interactive filters.
Builds a sidebar/expander filter UI from whatever columns exist in
the current dataset, and applies the selections back onto the
DataFrame. Gracefully skips filter types the dataset doesn't have.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st


def render_filters(df: pd.DataFrame, key_prefix: str = "flt") -> pd.DataFrame:
    date_cols = df.select_dtypes(include="datetime64[ns]").columns.tolist()
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = [c for c in df.columns if c not in date_cols and c not in numeric_cols]

    with st.expander("🔎 Filters", expanded=False):
        filtered = df

        if date_cols:
            date_col = st.selectbox("Date column", date_cols, key=f"{key_prefix}_datecol")
            min_d, max_d = df[date_col].min(), df[date_col].max()
            if pd.notna(min_d) and pd.notna(max_d):
                start, end = st.slider(
                    "Date range",
                    min_value=min_d.to_pydatetime(), max_value=max_d.to_pydatetime(),
                    value=(min_d.to_pydatetime(), max_d.to_pydatetime()),
                    key=f"{key_prefix}_daterange",
                )
                filtered = filtered[(filtered[date_col] >= start) & (filtered[date_col] <= end)]

        # Common business-y category filters, skipped automatically if absent.
        priority_cats = [c for c in ["region", "category", "product", "customer_segment",
                                       "payment_method", "segment"] if c in cat_cols]
        other_cats = [c for c in cat_cols if c not in priority_cats]
        show_cats = (priority_cats + other_cats)[:5]

        cols = st.columns(min(3, max(1, len(show_cats)))) if show_cats else []
        for i, col in enumerate(show_cats):
            options = sorted(filtered[col].dropna().unique().tolist())
            with cols[i % len(cols)]:
                selected = st.multiselect(col.replace("_", " ").title(), options,
                                           key=f"{key_prefix}_{col}")
            if selected:
                filtered = filtered[filtered[col].isin(selected)]

        if numeric_cols:
            num_col = st.selectbox("Numeric range filter (optional)",
                                    ["None"] + numeric_cols, key=f"{key_prefix}_numcol")
            if num_col != "None":
                lo, hi = float(df[num_col].min()), float(df[num_col].max())
                if lo < hi:
                    sel_lo, sel_hi = st.slider(f"{num_col} range", lo, hi, (lo, hi),
                                                key=f"{key_prefix}_numrange")
                    filtered = filtered[filtered[num_col].between(sel_lo, sel_hi)]

        st.caption(f"Showing {len(filtered):,} of {len(df):,} rows after filters.")
    return filtered
