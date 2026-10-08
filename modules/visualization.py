"""
VERIDEXA visualization.
Centralized Plotly chart builders so every page gets a consistent
look. Charts only ever plot data that's already been computed
elsewhere (profiler / query_engine / forecasting / etc).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

TEMPLATE = "plotly_dark"
ACCENT = "#6C5CE7"
ACCENT2 = "#34D6C4"
PALETTE = ["#6C5CE7", "#34D6C4", "#FF7EB3", "#FFC048", "#54A0FF", "#1DD1A1", "#FF6B6B", "#A29BFE"]


def _base_layout(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(
        template=TEMPLATE,
        title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="sans-serif", size=13),
        margin=dict(l=40, r=20, t=50 if title else 20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str = "", horizontal: bool = False) -> go.Figure:
    if horizontal:
        fig = px.bar(df, x=y, y=x, orientation="h", color_discrete_sequence=[ACCENT])
        fig.update_yaxes(categoryorder="total ascending")
    else:
        fig = px.bar(df, x=x, y=y, color_discrete_sequence=[ACCENT])
    return _base_layout(fig, title)


def line_chart(df: pd.DataFrame, x: str, y: str, title: str = "", color: str | None = None) -> go.Figure:
    fig = px.line(df, x=x, y=y, color=color, markers=True,
                   color_discrete_sequence=PALETTE)
    return _base_layout(fig, title)


def forecast_chart(history: pd.DataFrame, forecast: pd.DataFrame, date_col: str, title: str = "") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history[date_col], y=history["value"], mode="lines+markers",
                              name="Actual", line=dict(color=ACCENT, width=2)))
    fig.add_trace(go.Scatter(x=forecast[date_col], y=forecast["value"], mode="lines+markers",
                              name="Forecast", line=dict(color=ACCENT2, width=2, dash="dash")))
    fig.add_trace(go.Scatter(
        x=pd.concat([forecast[date_col], forecast[date_col][::-1]]),
        y=pd.concat([forecast["upper"], forecast["lower"][::-1]]),
        fill="toself", fillcolor="rgba(52,214,196,0.15)",
        line=dict(color="rgba(0,0,0,0)"), name="Confidence band", showlegend=True,
    ))
    return _base_layout(fig, title)


def scatter_chart(df: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = "") -> go.Figure:
    fig = px.scatter(df, x=x, y=y, color=color, color_discrete_sequence=PALETTE, opacity=0.75)
    return _base_layout(fig, title)


def seasonal_decomposition_chart(table: pd.DataFrame, date_col: str, title: str = "") -> go.Figure:
    """Stacked observed/trend/seasonal/residual subplots from
    forecasting.decompose_seasonal()'s output table."""
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                         subplot_titles=("Observed", "Trend", "Seasonal", "Residual"),
                         vertical_spacing=0.06)
    components = [("observed", ACCENT), ("trend", ACCENT2), ("seasonal", PALETTE[2] if len(PALETTE) > 2 else ACCENT),
                  ("residual", PALETTE[3] if len(PALETTE) > 3 else ACCENT2)]
    for i, (col, color) in enumerate(components, start=1):
        fig.add_trace(
            go.Scatter(x=table[date_col], y=table[col], mode="lines", name=col.title(),
                       line=dict(color=color, width=2), showlegend=False),
            row=i, col=1,
        )
    fig.update_layout(height=650)
    return _base_layout(fig, title)


def pie_chart(df: pd.DataFrame, names: str, values: str, title: str = "") -> go.Figure:
    fig = px.pie(df, names=names, values=values, color_discrete_sequence=PALETTE, hole=0.45)
    return _base_layout(fig, title)


def heatmap(corr: pd.DataFrame, title: str = "Correlation Matrix") -> go.Figure:
    fig = px.imshow(corr, text_auto=True, color_continuous_scale="Purples", aspect="auto")
    return _base_layout(fig, title)


def histogram(df: pd.DataFrame, col: str, title: str = "") -> go.Figure:
    fig = px.histogram(df, x=col, color_discrete_sequence=[ACCENT], nbins=30)
    return _base_layout(fig, title)


def kpi_card(label: str, value: str, delta: str | None = None):
    """Returns markdown for a styled KPI card (used with st.markdown)."""
    delta_html = f'<div style="font-size:0.8rem;color:#34D6C4;">{delta}</div>' if delta else ""
    return f"""
    <div style="background:#171A23;border:1px solid #262A38;border-radius:14px;
                padding:1rem 1.2rem;">
        <div style="color:#A7A9BC;font-size:0.82rem;">{label}</div>
        <div style="font-size:1.6rem;font-weight:700;color:#E8E8F0;">{value}</div>
        {delta_html}
    </div>
    """


# ----------------------------------------------------------------------
# 3D charts (real, draggable/zoomable Plotly 3D — not decorative)
# ----------------------------------------------------------------------
def scatter_3d(df: pd.DataFrame, x: str, y: str, z: str, color: str | None = None,
                title: str = "") -> go.Figure:
    """Interactive 3D scatter — drag to rotate, scroll to zoom, hover for values."""
    fig = px.scatter_3d(df, x=x, y=y, z=z, color=color, opacity=0.82,
                          color_discrete_sequence=PALETTE,
                          color_continuous_scale="Plasma")
    fig.update_traces(marker=dict(size=5, line=dict(width=0.5, color="rgba(255,255,255,0.25)")))
    fig.update_layout(
        template=TEMPLATE, title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        scene=dict(
            xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38", title=x),
            yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38", title=y),
            zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38", title=z),
        ),
        margin=dict(l=0, r=0, t=50 if title else 10, b=0),
        scene_camera=dict(eye=dict(x=1.5, y=1.5, z=1.1)),
    )
    return fig


def surface_3d_correlation(corr: pd.DataFrame, title: str = "Correlation Surface") -> go.Figure:
    """3D surface of a correlation matrix same data as the heatmap, viewed as terrain."""
    fig = go.Figure(data=[go.Surface(
        z=corr.values, x=corr.columns.tolist(), y=corr.index.tolist(),
        colorscale="Plasma", showscale=True,
        contours=dict(z=dict(show=True, usecolormap=True, project=dict(z=True))),
    )])
    fig.update_layout(
        template=TEMPLATE, title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        scene=dict(
            xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38"),
            yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38"),
            zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38", title="correlation"),
        ),
        margin=dict(l=0, r=0, t=50, b=0),
        scene_camera=dict(eye=dict(x=1.6, y=1.6, z=1.0)),
    )
    return fig


def surface_3d_density(df: pd.DataFrame, x: str, y: str, title: str = "") -> go.Figure:
    """3D histogram-surface (binned density) of two numeric columns a landscape view
    of where the data actually concentrates."""
    import numpy as np
    xs = df[x].dropna()
    ys = df[y].dropna()
    common = pd.concat([xs, ys], axis=1).dropna()
    if common.empty:
        return _base_layout(go.Figure(), title)
    hist, xedges, yedges = np.histogram2d(common[x], common[y], bins=22)
    xc = (xedges[:-1] + xedges[1:]) / 2
    yc = (yedges[:-1] + yedges[1:]) / 2
    fig = go.Figure(data=[go.Surface(z=hist.T, x=xc, y=yc, colorscale="Viridis", showscale=True)])
    fig.update_layout(
        template=TEMPLATE, title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        scene=dict(
            xaxis=dict(title=x, backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38"),
            yaxis=dict(title=y, backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38"),
            zaxis=dict(title="density", backgroundcolor="rgba(0,0,0,0)", gridcolor="#262A38"),
        ),
        margin=dict(l=0, r=0, t=50, b=0),
    )
    return fig


# ----------------------------------------------------------------------
# Animated (motion) charts
# ----------------------------------------------------------------------
def animated_bar_race(df: pd.DataFrame, category_col: str, value_col: str, frame_col: str,
                       title: str = "", top_n: int = 10) -> go.Figure:
    """A play/pause animated 'bar race' — value_col by category_col, one animation
    frame per distinct value of frame_col (e.g. month)."""
    work = df[[category_col, value_col, frame_col]].dropna().copy()
    work[frame_col] = work[frame_col].astype(str)
    top_categories = (work.groupby(category_col)[value_col].sum()
                       .sort_values(ascending=False).head(top_n).index)
    work = work[work[category_col].isin(top_categories)]
    grouped = work.groupby([frame_col, category_col], as_index=False)[value_col].sum()
    frame_order = sorted(grouped[frame_col].unique())
    grouped[frame_col] = pd.Categorical(grouped[frame_col], categories=frame_order, ordered=True)
    grouped = grouped.sort_values(frame_col)

    fig = px.bar(
        grouped, x=value_col, y=category_col, color=category_col, orientation="h",
        animation_frame=frame_col, range_x=[0, grouped[value_col].max() * 1.1],
        color_discrete_sequence=PALETTE, title=title,
    )
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_layout(
        template=TEMPLATE, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=50, b=40),
        transition=dict(duration=350, easing="cubic-in-out"),
    )
    if fig.layout.updatemenus:
        fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 500
        fig.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 350
    return fig


def animated_line_reveal(df: pd.DataFrame, x: str, y: str, title: str = "") -> go.Figure:
    """A line chart that draws itself in over time (play button), instead of
    appearing all at once same underlying data as line_chart()."""
    work = df[[x, y]].dropna().reset_index(drop=True)
    frames = []
    step = max(1, len(work) // 30)
    for i in range(2, len(work) + 1, step):
        frames.append(go.Frame(
            data=[go.Scatter(x=work[x][:i], y=work[y][:i], mode="lines+markers",
                              line=dict(color=ACCENT, width=3), marker=dict(size=5, color=ACCENT2))],
            name=str(i),
        ))
    if not frames or frames[-1].name != str(len(work)):
        frames.append(go.Frame(
            data=[go.Scatter(x=work[x], y=work[y], mode="lines+markers",
                              line=dict(color=ACCENT, width=3), marker=dict(size=5, color=ACCENT2))],
            name="final",
        ))

    fig = go.Figure(
        data=[go.Scatter(x=work[x][:2], y=work[y][:2], mode="lines+markers",
                          line=dict(color=ACCENT, width=3), marker=dict(size=5, color=ACCENT2))],
        frames=frames,
    )
    fig.update_layout(
        template=TEMPLATE, title=title,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(range=[work[x].min(), work[x].max()]),
        yaxis=dict(range=[work[y].min() * 0.95 if work[y].min() < 0 else 0, work[y].max() * 1.08]),
        updatemenus=[dict(
            type="buttons", showactive=False, y=1.12, x=0, xanchor="left",
            buttons=[dict(label="▶ Play", method="animate",
                          args=[None, dict(frame=dict(duration=45, redraw=True), fromcurrent=True,
                                            transition=dict(duration=0))]),
                     dict(label="⏸ Reset", method="animate",
                          args=[["0"], dict(frame=dict(duration=0, redraw=True), mode="immediate")])],
        )],
    )
    return fig


def animated_kpi_html(label: str, target_value: float, prefix: str = "", suffix: str = "",
                       decimals: int = 0, icon: str = "📊", delta: str | None = None,
                       accent: str = ACCENT) -> str:
    """Self-contained HTML/CSS/JS for a KPI card whose number counts up from 0 on load.
    Must be rendered with st.components.v1.html(..., height=118), NOT st.markdown
    (markdown strips <script> tags so the count-up JS would never run)."""
    import uuid
    el_id = f"kpi_{uuid.uuid4().hex[:8]}"
    delta_html = f'<div class="{el_id}-delta">{delta}</div>' if delta else ""
    return f"""
    <div style="font-family:sans-serif;">
    <style>
      .{el_id}-card {{
        background: linear-gradient(160deg, #171A23 0%, #1B1E2C 100%);
        border: 1px solid #262A38; border-radius: 14px;
        padding: 1rem 1.2rem; position: relative; overflow:hidden;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
      }}
      .{el_id}-card:hover {{
        transform: translateY(-3px) scale(1.015);
        box-shadow: 0 10px 26px rgba(108,92,231,0.25);
        border-color: {accent};
      }}
      .{el_id}-card::after {{
        content: ""; position:absolute; inset:0;
        background: radial-gradient(circle at 85% -10%, {accent}33, transparent 60%);
        pointer-events:none;
      }}
      .{el_id}-label {{ color:#A7A9BC; font-size:0.82rem; display:flex; align-items:center; gap:0.4rem; }}
      .{el_id}-value {{ font-size:1.7rem; font-weight:800; color:#E8E8F0; margin-top:0.15rem; }}
      .{el_id}-delta {{ font-size:0.78rem; color:#34D6C4; margin-top:0.1rem; }}
    </style>
    <div class="{el_id}-card">
      <div class="{el_id}-label">{icon} {label}</div>
      <div class="{el_id}-value"><span id="{el_id}">0</span></div>
      {delta_html}
    </div>
    <script>
      (function() {{
        const target = {target_value};
        const prefix = {prefix!r};
        const suffix = {suffix!r};
        const decimals = {decimals};
        const el = document.getElementById("{el_id}");
        const duration = 900;
        const start = performance.now();
        function step(now) {{
          const t = Math.min(1, (now - start) / duration);
          const eased = 1 - Math.pow(1 - t, 3);
          const val = target * eased;
          el.textContent = prefix + val.toLocaleString(undefined, {{
            minimumFractionDigits: decimals, maximumFractionDigits: decimals
          }}) + suffix;
          if (t < 1) requestAnimationFrame(step);
        }}
        requestAnimationFrame(step);
      }})();
    </script>
    </div>
    """
