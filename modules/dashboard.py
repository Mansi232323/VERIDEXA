"""
VERIDEXA analytics dashboard.
Auto-adapting KPIs and trend/breakdown charts: gracefully skips
whatever columns a given dataset doesn't have, rather than erroring.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from modules import extra_features as extra
from modules import report_generator
from modules import visualization as viz
from utils.helpers import display_number


def _guess_metric_columns(df: pd.DataFrame) -> list[str]:
    numeric = df.select_dtypes(include=np.number).columns.tolist()
    priority = [c for c in ["revenue", "profit", "sales", "amount", "total", "cost", "quantity"]
                if c in numeric]
    rest = [c for c in numeric if c not in priority]
    return (priority + rest)[:4]


def render_dashboard(df: pd.DataFrame):
    if df.empty:
        st.info("No data to show after filtering.")
        return

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    date_cols = df.select_dtypes(include="datetime64[ns]").columns.tolist()
    cat_cols = [c for c in df.columns if c not in numeric_cols and c not in date_cols]

    compact = st.session_state.get("compact_numbers", True)

    # --- KPI row (animated count-up cards, with inline sparklines) -----
    metrics = _guess_metric_columns(df)
    icons = ["💰", "📦", "📈", "🎯"]
    if metrics:
        cols = st.columns(len(metrics))
        for i, (col, metric) in enumerate(zip(cols, metrics)):
            with col:
                total = float(df[metric].sum())
                avg = float(df[metric].mean())
                decimals = 0 if abs(total) >= 100 else 2
                # --- Feature 5: inline sparkline, when a date column exists
                spark = ""
                if date_cols:
                    trend = (df[[date_cols[0], metric]].dropna()
                             .set_index(date_cols[0]).resample("D")[metric].sum())
                    if len(trend) >= 3:
                        spark = f'<div style="margin-top:0.3rem;">{extra.sparkline_svg(trend.tolist())}</div>'
                html = viz.animated_kpi_html(
                    label=metric.replace("_", " ").title(),
                    target_value=total, decimals=decimals,
                    icon=icons[i % len(icons)],
                    delta=f"avg {display_number(avg, compact)} / row",
                )
                # inject the sparkline just before the closing card div
                html = html.replace("</div>\n    </div>\n    <script>",
                                     spark + "</div>\n    </div>\n    <script>", 1)
                components.html(html, height=140 if spark else 118)
    else:
        st.info("No numeric columns found to build KPIs from.")

    # --- Feature 7: period-over-period comparison card -------------------
    if date_cols and metrics:
        pop_metric = metrics[0]
        pop = extra.period_over_period(df, date_cols[0], pop_metric, freq="ME")
        if pop:
            direction = "▲" if (pop["pct_change"] or 0) >= 0 else "▼"
            color = "#1DD1A1" if (pop["pct_change"] or 0) >= 0 else "#FF6B6B"
            st.markdown(
                f"""<div style="background:#171A23; border:1px solid #262A38; border-radius:14px;
                            padding:0.9rem 1.2rem; margin-top:0.6rem;">
                      <span style="color:#A7A9BC; font-size:0.82rem;">📐 {pop_metric.replace('_',' ').title()},
                      last period vs previous:</span>
                      <span style="font-weight:800; color:{color}; margin-left:0.4rem;">
                        {direction} {abs(pop['pct_change']) if pop['pct_change'] is not None else '—'}%
                      </span>
                      <span style="color:#6B6E82; font-size:0.78rem; margin-left:0.6rem;">
                        ({display_number(pop['previous_value'], compact)} → {display_number(pop['current_value'], compact)})
                      </span>
                    </div>""",
                unsafe_allow_html=True,
            )

    st.write("")

    # --- Trend chart --------------------------------------------------
    if date_cols and metrics:
        c1, c2 = st.columns([3, 1])
        with c2:
            metric = st.selectbox("Metric", metrics, key="dash_trend_metric")
            date_col = st.selectbox("Date column", date_cols, key="dash_trend_date")
            freq_label = st.radio("Granularity", ["Daily", "Weekly", "Monthly"], index=2,
                                   key="dash_trend_freq")
            freq = {"Daily": "D", "Weekly": "W", "Monthly": "ME"}[freq_label]
            animate_trend = st.checkbox("🎬 Animate (draw-in)", key="dash_trend_animate")
        with c1:
            ts = (df[[date_col, metric]].dropna()
                  .set_index(date_col).resample(freq)[metric].sum().reset_index())
            title = f"{metric.replace('_',' ').title()} over time"
            if animate_trend and len(ts) >= 3:
                fig = viz.animated_line_reveal(ts, date_col, metric, title=title)
            else:
                fig = viz.line_chart(ts, date_col, metric, title=title)
            st.plotly_chart(fig, use_container_width=True)
            # --- Feature 16 & 17: download chart as HTML / underlying data
            dc1, dc2 = st.columns(2)
            with dc1:
                st.download_button("💾 Download chart as HTML", fig.to_html(include_plotlyjs="cdn"),
                                    file_name=f"{metric}_trend.html", mime="text/html", key="dash_trend_html")
            with dc2:
                st.download_button("📤 Download chart data as CSV", report_generator.to_csv_bytes(ts),
                                    file_name=f"{metric}_trend.csv", mime="text/csv", key="dash_trend_csv")

    st.write("")

    # --- Breakdown charts ----------------------------------------------
    if cat_cols and metrics:
        c1, c2 = st.columns(2)
        with c1:
            group_col = st.selectbox("Break down by", cat_cols, key="dash_group_col")
        with c2:
            metric2 = st.selectbox("By metric", metrics, key="dash_group_metric")

        grouped = (df.groupby(group_col)[metric2].sum()
                   .sort_values(ascending=False).head(12).reset_index())

        cc1, cc2 = st.columns(2)
        with cc1:
            fig_bar = viz.bar_chart(grouped, group_col, metric2, horizontal=True,
                                     title=f"{metric2.replace('_',' ').title()} by {group_col.replace('_',' ').title()}")
            st.plotly_chart(fig_bar, use_container_width=True)
        with cc2:
            if grouped[group_col].nunique() <= 8:
                fig_pie = viz.pie_chart(grouped, group_col, metric2,
                                         title=f"Share of {metric2.replace('_',' ').title()}")
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.dataframe(grouped, use_container_width=True, hide_index=True)

        # Animated bar-race across time, when a date column is available
        if date_cols:
            with st.expander("🏁 Animated bar race over time"):
                race_date = st.selectbox("Time column", date_cols, key="dash_race_date")
                race_freq_label = st.radio("Granularity", ["Monthly", "Weekly"], horizontal=True,
                                            key="dash_race_freq")
                race_freq = {"Monthly": "ME", "Weekly": "W"}[race_freq_label]
                race_df = df[[race_date, group_col, metric2]].dropna().copy()
                race_df[race_date] = race_df[race_date].dt.to_period(
                    "M" if race_freq == "ME" else "W").astype(str)
                fig_race = viz.animated_bar_race(race_df, group_col, metric2, race_date,
                                                   title=f"{metric2.replace('_',' ').title()} by "
                                                         f"{group_col.replace('_',' ').title()} : over time")
                st.plotly_chart(fig_race, use_container_width=True)
    elif not cat_cols:
        st.caption("No categorical columns available for a breakdown chart.")

    # --- Correlation: 2D heatmap or 3D surface --------------------------
    if len(numeric_cols) >= 2:
        with st.expander("📈 Correlation 2D heatmap or 3D surface", expanded=False):
            view_mode = st.radio("View as", ["2D Heatmap", "🧊 3D Surface"], horizontal=True,
                                  key="dash_corr_view")
            corr = df[numeric_cols].corr(numeric_only=True).round(2)
            if view_mode == "2D Heatmap":
                st.plotly_chart(viz.heatmap(corr), use_container_width=True)
            else:
                st.caption("Drag to rotate, scroll to zoom peaks show strong positive correlation.")
                st.plotly_chart(viz.surface_3d_correlation(corr), use_container_width=True)

    # --- 3D scatter explorer --------------------------------------------
    if len(numeric_cols) >= 3:
        with st.expander("🧊 3D scatter explorer", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                x3 = st.selectbox("X axis", numeric_cols, index=0, key="dash_3d_x")
            with c2:
                y3 = st.selectbox("Y axis", numeric_cols, index=min(1, len(numeric_cols)-1), key="dash_3d_y")
            with c3:
                z3 = st.selectbox("Z axis", numeric_cols, index=min(2, len(numeric_cols)-1), key="dash_3d_z")
            with c4:
                color3 = st.selectbox("Color by", ["(none)"] + cat_cols + numeric_cols, key="dash_3d_color")
            color_arg = None if color3 == "(none)" else color3
            sample = df if len(df) <= 3000 else df.sample(3000, random_state=42)
            st.plotly_chart(
                viz.scatter_3d(sample, x3, y3, z3, color=color_arg,
                                title=f"{x3} × {y3} × {z3}"),
                use_container_width=True,
            )
