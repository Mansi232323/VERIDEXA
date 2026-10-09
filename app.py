"""
VERIDEXA Intelligent Data Analyst Suite.
Streamlit entry point: session bootstrapping, auth gating, and
routing into every feature page. Run with:  streamlit run app.py
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config.settings import APP_NAME, SESSION_TIMEOUT_MINUTES
from modules import (
    anomaly_detection,
    data_cleaner,
    data_profiler,
    dataset_store,
    eda_generator,
    extra_features as extra,
    forecasting,
    joins,
    query_engine,
    recommendation_engine,
    report_generator,
    segmentation,
    ui_auth,
    visualization as viz,
)
from modules.auth import AuthError, change_password
from modules.dashboard import render_dashboard
from modules.data_loader import DataLoadError, load_uploaded_file
from modules.db import fetch_audit_log, init_db, record_audit
from modules.filters import render_filters
from modules.insight_generator import narrate
from utils.helpers import display_number, human_number

st.set_page_config(page_title=f"{APP_NAME} Intelligent Data Analyst Suite",
                    page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

# ----------------------------------------------------------------------
# Feature 1: Light / Dark theme toggle (applied on every rerun)
# ----------------------------------------------------------------------
def apply_theme_css():
    if st.session_state.get("theme_mode", "Dark") == "Light":
        st.markdown("""
        <style>
        .stApp { background-color: #F5F6FA !important; color: #1A1C24 !important; }
        section[data-testid="stSidebar"] { background-color: #ECEEF5 !important; }
        div[data-testid="stMetric"], .stDataFrame, .stMarkdown, p, span, label { color: #1A1C24 !important; }
        div[data-testid="stVerticalBlock"] div[style*="background:#171A23"] {
            background: #FFFFFF !important; border-color: #DADCE6 !important; color:#1A1C24 !important;
        }
        </style>
        """, unsafe_allow_html=True)


apply_theme_css()

init_db()

# ----------------------------------------------------------------------
# Session bootstrapping
# ----------------------------------------------------------------------
_DEFAULTS = {
    "authenticated": False,
    "auth_user": None,
    "auth_view": "login",
    "page": "landing",
    "login_time": None,
    "df": None,
    "df_original": None,
    "dataset_name": None,
    "datasets": {},          # name -> DataFrame, every table loaded this session
    "chat_history": [],
    "last_metric_col": None,
    "nav": "🏠 Home",
    "eda_report": None,
    "anomaly_summary": None,
    "forecast_result": None,
    "rfm_result": None,
    # --- new feature state ---
    "theme_mode": "Dark",
    "compact_numbers": True,
    "pinned_datasets": set(),
    "undo_stack": {},         # dataset_name -> previous DataFrame (single-level undo)
    "session_action_count": 0,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def log_action(user_id, action: str, detail: str = "", toast: str | None = None):
    """Wraps record_audit with a session action counter and an optional
    toast notification, so every meaningful action is both auditable
    and gives the user immediate visual feedback."""
    record_audit(user_id, action, detail)
    st.session_state.session_action_count += 1
    if toast:
        st.toast(toast, icon="✅")


def current_user() -> dict:
    return st.session_state.auth_user or {}


def logout(reason: str | None = None):
    user = current_user()
    record_audit(user.get("id"), "logout", reason or "")
    for k in ("authenticated", "auth_user", "login_time", "df", "df_original", "dataset_name",
              "datasets", "chat_history", "eda_report", "anomaly_summary", "forecast_result", "rfm_result"):
        st.session_state[k] = _DEFAULTS.get(k)
    st.session_state.page = "landing"
    st.session_state.auth_view = "login"
    if reason:
        st.session_state["_logout_notice"] = reason
    st.rerun()


# ----------------------------------------------------------------------
# Gate: show landing/login/signup until authenticated
# ----------------------------------------------------------------------
if not st.session_state.authenticated:
    notice = st.session_state.pop("_logout_notice", None)
    if notice:
        st.warning(notice)
    ui_auth.render_auth_page()
    st.stop()

# Enforce a session timeout so an unattended, signed-in browser tab
# doesn't stay authenticated forever — important once this is deployed
# for more than one person.
if st.session_state.login_time is not None:
    elapsed = datetime.utcnow() - st.session_state.login_time
    if elapsed > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        logout(reason=f"You were signed out after {SESSION_TIMEOUT_MINUTES} minutes. Please log back in.")


# ----------------------------------------------------------------------
# Authenticated app shell
# ----------------------------------------------------------------------
def sidebar_nav() -> str:
    user = current_user()
    with st.sidebar:
        st.markdown(f"### 🧠 {APP_NAME}")
        st.caption(f"Signed in as **{user.get('username','')}**")

        pages = [
            "🏠 Home", "📂 Upload & Clean", "🔍 Data Explorer", "📊 Analytics Dashboard",
            "🧊 3D Explorer", "🤖 AI Analyst", "📈 Automated EDA", "🔮 Forecasting",
            "⚠️ Anomaly Detection", "👥 Customer Segmentation", "💡 AI Recommendations",
            "📄 Reports", "🕒 Activity Log", "⚙️ Account",
        ]

        # --- Feature 2: command palette / quick jump ------------------
        jump_query = st.text_input("🔎 Jump to…", key="cmd_palette",
                                    placeholder="type a page name, e.g. 'forecast'")
        if jump_query:
            matches = [p for p in pages if jump_query.lower() in p.lower()]
            if matches:
                st.session_state.nav = matches[0]
            else:
                st.caption("No matching page.")

        choice = st.radio("Navigate", pages, index=pages.index(st.session_state.nav)
                           if st.session_state.nav in pages else 0, label_visibility="collapsed")
        st.session_state.nav = choice

        st.divider()

        # --- Feature 11: pin/favorite datasets -------------------------
        if st.session_state.df is not None:
            is_pinned = st.session_state.dataset_name in st.session_state.pinned_datasets
            c1, c2 = st.columns([4, 1])
            with c1:
                st.success(f"📁 {st.session_state.dataset_name}\n\n"
                           f"{st.session_state.df.shape[0]:,} rows × {st.session_state.df.shape[1]} cols")
            with c2:
                if st.button("⭐" if is_pinned else "☆", key="pin_toggle",
                              help="Pin this dataset"):
                    if is_pinned:
                        st.session_state.pinned_datasets.discard(st.session_state.dataset_name)
                    else:
                        st.session_state.pinned_datasets.add(st.session_state.dataset_name)
                    st.rerun()
            if len(st.session_state.datasets) > 1:
                st.caption(f"+{len(st.session_state.datasets) - 1} more table(s) loaded this session")
            if st.session_state.pinned_datasets:
                st.caption("⭐ Pinned: " + ", ".join(sorted(st.session_state.pinned_datasets)))
        else:
            st.info("No dataset loaded yet.")

        st.divider()

        # --- Feature 15: compact vs full number format ------------------
        st.toggle("🔢 Compact numbers (1.2M vs 1,200,000)", key="compact_numbers")

        # --- Feature 19: session summary widget --------------------------
        if st.session_state.login_time is not None:
            elapsed = datetime.utcnow() - st.session_state.login_time
            mins = int(elapsed.total_seconds() // 60)
            with st.expander("🧭 Session summary"):
                st.caption(f"Active for **{mins} min** · "
                           f"**{st.session_state.session_action_count}** action(s) logged this session · "
                           f"**{len(st.session_state.datasets)}** dataset(s) loaded")

        st.divider()
        if st.button("🚪 Log out", use_container_width=True):
            logout()
    return choice


def require_data() -> pd.DataFrame | None:
    if st.session_state.df is None:
        st.warning("Upload a dataset first on the **📂 Upload & Clean** page.")
        if st.button("Go to Upload & Clean"):
            st.session_state.nav = "📂 Upload & Clean"
            st.rerun()
        return None
    return st.session_state.df


def _unique_dataset_name(name: str) -> str:
    """Avoids clobbering an already-loaded table with the same name
    (e.g. re-uploading the same file, or two files that share a name)."""
    if name not in st.session_state.datasets:
        return name
    stem, _, ext = name.rpartition(".")
    stem, ext = (stem, ext) if stem else (name, "")
    i = 2
    while True:
        candidate = f"{stem} ({i}).{ext}" if ext else f"{name} ({i})"
        if candidate not in st.session_state.datasets:
            return candidate
        i += 1


def register_dataset(name: str, df: pd.DataFrame, activate: bool = True) -> str:
    """Adds `df` to the session's table of loaded datasets under `name`
    (de-duplicated), optionally making it the active one everywhere else
    in the app (Data Explorer, Dashboard, AI Analyst, etc.)."""
    name = _unique_dataset_name(name)
    st.session_state.datasets[name] = df
    if activate:
        activate_dataset(name)
    return name


def activate_dataset(name: str) -> None:
    df = st.session_state.datasets[name]
    st.session_state.df = df
    st.session_state.df_original = df.copy()
    st.session_state.dataset_name = name
    for k in ("eda_report", "anomaly_summary", "forecast_result", "rfm_result", "chat_history"):
        st.session_state[k] = _DEFAULTS[k]


# --------------------------- Home ---------------------------------------
def page_home():
    user = current_user()
    st.title(f"Welcome back, {user.get('username','')} 👋")
    st.caption("Here's a quick snapshot of your session.")

    if st.session_state.df is None:
        st.info("You haven't loaded a dataset yet.")
        if st.button("📂 Go upload a file", use_container_width=True, type="primary"):
            st.session_state.nav = "📂 Upload & Clean"
            st.rerun()
        return

    df = st.session_state.df
    ov = data_profiler.overview(df)
    if len(st.session_state.datasets) > 1:
        st.caption(f"Active table: **{st.session_state.dataset_name}** "
                   f"({len(st.session_state.datasets)} tables loaded this session "
                   "switch or join them on the Upload & Clean page).")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(viz.kpi_card("Rows", f"{ov['rows']:,}"), unsafe_allow_html=True)
    c2.markdown(viz.kpi_card("Columns", f"{ov['columns']}"), unsafe_allow_html=True)
    c3.markdown(viz.kpi_card("Missing data", f"{ov['missing_pct']}%"), unsafe_allow_html=True)
    c4.markdown(viz.kpi_card("Duplicate rows", f"{ov['duplicate_rows']}"), unsafe_allow_html=True)

    # --- Feature 3: Data Health Score --------------------------------
    hs = extra.health_score(df)
    color = extra.health_score_badge_color(hs["score"])
    st.markdown(
        f"""<div style="margin-top:0.8rem; background:#171A23; border:1px solid #262A38;
                    border-radius:14px; padding:1rem 1.2rem; display:flex; align-items:center; gap:1.2rem;">
              <div style="font-size:2rem; font-weight:800; color:{color};">{hs['score']}</div>
              <div>
                <div style="color:#E8E8F0; font-weight:700; font-size:0.95rem;">Data Health Score</div>
                <div style="color:#A7A9BC; font-size:0.8rem;">
                  Completeness {hs['completeness']}% · Uniqueness {hs['uniqueness']}% · Consistency {hs['consistency']}%
                </div>
              </div>
            </div>""",
        unsafe_allow_html=True,
    )

    st.write("")
    st.subheader("Where to next?")
    cols = st.columns(3)
    shortcuts = [
        ("🔍 Explore the data", "🔍 Data Explorer"),
        ("📊 View the dashboard", "📊 Analytics Dashboard"),
        ("🤖 Ask the AI Analyst", "🤖 AI Analyst"),
        ("🔮 Forecast a metric", "🔮 Forecasting"),
        ("⚠️ Check for anomalies", "⚠️ Anomaly Detection"),
        ("👥 Segment your customers", "👥 Customer Segmentation"),
    ]
    for i, (label, target) in enumerate(shortcuts):
        with cols[i % 3]:
            if st.button(label, use_container_width=True, key=f"home_go_{i}"):
                st.session_state.nav = target
                st.rerun()

    st.divider()
    st.subheader("Data preview")
    st.dataframe(df.head(20), use_container_width=True)


def _set_active_df(new_df: pd.DataFrame) -> None:
    """Use this (instead of assigning `st.session_state.df` directly)
    whenever the active dataset is edited in place e.g. by the
    cleaning actions below so the entry in `datasets` (and therefore
    anything joined against it later) stays in sync."""
    st.session_state.df = new_df
    if st.session_state.dataset_name:
        st.session_state.datasets[st.session_state.dataset_name] = new_df


# --------------------------- Upload & Clean ------------------------------
def page_upload():
    st.title("📂 Upload & Clean")
    user = current_user()

    tab_upload, tab_clean, tab_combine, tab_storage = st.tabs(
        ["Upload a file", "Clean current dataset", "🔗 Combine / Join", "💾 Persistent storage"]
    )

    with tab_upload:
        st.markdown("Upload a **CSV, Excel, JSON, or Parquet** file. Each file you load stays "
                    "available in this session, so you can upload several and join them below.")
        uploaded = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls", "json", "parquet"],  max_upload_size=5120)
        if uploaded is not None and st.button("Load this file", type="primary", use_container_width=True):
            try:
                df = load_uploaded_file(uploaded)
                name = register_dataset(uploaded.name, df, activate=True)
                log_action(user.get("id"), "upload_file", name, toast=f"Loaded '{name}'")
                st.success(f"Loaded {name} : {df.shape[0]:,} rows × {df.shape[1]} columns.")
            except DataLoadError as e:
                st.error(str(e))

        if st.session_state.datasets:
            st.write("")
            st.caption(f"{len(st.session_state.datasets)} table(s) loaded this session")
            for name, tdf in st.session_state.datasets.items():
                is_active = name == st.session_state.dataset_name
                c1, c2, c3 = st.columns([5, 1, 1])
                c1.markdown(f"{'⭐ ' if is_active else ''}**{name}** : {tdf.shape[0]:,} rows × {tdf.shape[1]} cols")
                if not is_active and c2.button("Use", key=f"use_{name}"):
                    activate_dataset(name)
                    st.rerun()
                # --- Feature 9: one-click dataset duplicate/clone -------
                if c3.button("⧉ Clone", key=f"clone_{name}", help="Duplicate this dataset"):
                    clone_name = register_dataset(f"{name} (copy)", tdf.copy(), activate=False)
                    st.toast(f"Cloned as '{clone_name}'", icon="⧉")
                    st.rerun()

            # --- Feature 8: dataset diff / schema compare tool ------------
            if len(st.session_state.datasets) >= 2:
                with st.expander("🆚 Compare two datasets"):
                    names_list = list(st.session_state.datasets.keys())
                    d1, d2 = st.columns(2)
                    with d1:
                        pick1 = st.selectbox("Dataset A", names_list, index=0, key="diff_a")
                    with d2:
                        pick2 = st.selectbox("Dataset B", names_list,
                                              index=min(1, len(names_list) - 1), key="diff_b")
                    if pick1 != pick2:
                        diff_table = extra.diff_datasets(
                            st.session_state.datasets[pick1], st.session_state.datasets[pick2], pick1, pick2)
                        st.dataframe(diff_table, use_container_width=True, hide_index=True)
                    else:
                        st.caption("Choose two different datasets to compare.")

        if st.session_state.df is not None:
            st.write("")
            st.caption(f"Preview {st.session_state.dataset_name}")
            st.dataframe(st.session_state.df.head(10), use_container_width=True)
            # --- Feature 12: CSV template download --------------------
            st.download_button(
                "📝 Download a blank CSV template (same columns)",
                extra.csv_template_bytes(st.session_state.df.columns.tolist()),
                file_name=f"{(st.session_state.dataset_name or 'template').split('.')[0]}_template.csv",
                mime="text/csv",
            )

    with tab_clean:
        df = st.session_state.df
        if df is None:
            st.info("Load a dataset in the Upload tab first.")
        else:
            st.markdown("#### Suggestions")
            for tip in data_cleaner.cleaning_suggestions(df):
                st.markdown(f"- {tip}")

            st.markdown("#### Actions")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🧹 Drop duplicate rows", use_container_width=True):
                    st.session_state.undo_stack[st.session_state.dataset_name] = df.copy()
                    new_df, n = data_cleaner.drop_duplicate_rows(df)
                    _set_active_df(new_df)
                    st.toast(f"Dropped {n} duplicate row(s)", icon="🧹")
                    st.success(f"Dropped {n} duplicate row(s).")
                    st.rerun()
            with c2:
                strategy = st.selectbox("Fill missing values with",
                                         ["mean", "median", "mode", "zero", "ffill", "bfill", "drop_rows"])
                if st.button("🩹 Apply fill strategy", use_container_width=True):
                    st.session_state.undo_stack[st.session_state.dataset_name] = df.copy()
                    new_df, n = data_cleaner.fill_missing(df, strategy)
                    _set_active_df(new_df)
                    st.toast(f"Filled/removed {n} value(s)", icon="🩹")
                    st.success(f"Filled/removed {n} missing value(s) using '{strategy}'.")
                    st.rerun()
            with c3:
                outlier_action = st.selectbox("Outlier handling", ["Cap (winsorize)", "Remove rows"])
                if st.button("📏 Apply to numeric outliers", use_container_width=True):
                    st.session_state.undo_stack[st.session_state.dataset_name] = df.copy()
                    if outlier_action.startswith("Cap"):
                        new_df, n = data_cleaner.cap_outliers_iqr(df)
                        msg = f"Capped {n} outlier value(s)."
                    else:
                        new_df, n = data_cleaner.remove_outliers_iqr(df)
                        msg = f"Removed {n} row(s) with outliers."
                    _set_active_df(new_df)
                    st.toast(msg, icon="📏")
                    st.success(msg)
                    st.rerun()

            st.write("")
            u1, u2 = st.columns(2)
            with u1:
                # --- Feature 10: undo last cleaning action -----------------
                has_undo = st.session_state.dataset_name in st.session_state.undo_stack
                if st.button("↩️ Undo last action", disabled=not has_undo, use_container_width=True):
                    prev = st.session_state.undo_stack.pop(st.session_state.dataset_name)
                    _set_active_df(prev)
                    st.toast("Last action undone", icon="↩️")
                    st.rerun()
            with u2:
                if st.button("⏮️ Reset to originally uploaded data", use_container_width=True):
                    st.session_state.undo_stack.pop(st.session_state.dataset_name, None)
                    _set_active_df(st.session_state.df_original.copy())
                    st.rerun()

            st.write("")
            st.markdown("#### Convert a column's type")
            c1, c2, c3 = st.columns(3)
            with c1:
                col = st.selectbox("Column", df.columns.tolist())
            with c2:
                target = st.selectbox("Convert to", ["numeric", "text", "datetime", "category"])
            with c3:
                st.write("")
                st.write("")
                if st.button("Convert", use_container_width=True):
                    _set_active_df(data_cleaner.convert_column_type(df, col, target))
                    st.success(f"Converted '{col}' to {target}.")
                    st.rerun()

    with tab_combine:
        st.markdown("Join two loaded tables into one e.g. `orders.csv` + `customers.xlsx` on a "
                    "shared `customer_id` column. The result is added as a new table you can "
                    "analyze, export, or join again.")
        names = list(st.session_state.datasets.keys())
        if len(names) < 2:
            st.info("Upload at least two files in the **Upload a file** tab to combine them.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                left_name = st.selectbox("Left table", names, index=0, key="join_left")
            with c2:
                right_options = [n for n in names if n != left_name] or names
                right_name = st.selectbox("Right table", right_options, index=0, key="join_right")

            left_df = st.session_state.datasets[left_name]
            right_df = st.session_state.datasets[right_name]
            suggested = joins.suggest_join_keys(left_df, right_df)

            c3, c4, c5 = st.columns(3)
            with c3:
                left_on = st.selectbox("Left key column", left_df.columns.tolist(),
                                        index=left_df.columns.get_loc(suggested[0]) if suggested else 0)
            with c4:
                right_on = st.selectbox("Right key column", right_df.columns.tolist(),
                                         index=right_df.columns.get_loc(suggested[0]) if suggested else 0)
            with c5:
                how_label = st.selectbox("Join type", list(joins.JOIN_TYPES.keys()))

            new_name = st.text_input("Name the combined table", value=f"{left_name} ⋈ {right_name}")

            if st.button("🔗 Join tables", type="primary"):
                try:
                    combined = joins.join_datasets(
                        left_df, right_df, left_on, right_on, joins.JOIN_TYPES[how_label]
                    )
                    name = register_dataset(new_name or f"{left_name}_joined", combined, activate=True)
                    record_audit(user.get("id"), "join_datasets",
                                 f"{left_name}+{right_name} on {left_on}={right_on} how={joins.JOIN_TYPES[how_label]}")
                    st.success(f"Joined into '{name}' — {combined.shape[0]:,} rows × {combined.shape[1]} columns. "
                               "It's now your active dataset.")
                    st.dataframe(combined.head(20), use_container_width=True)
                except joins.JoinError as e:
                    st.error(str(e))

    with tab_storage:
        st.markdown("Save a table to your account so it's still here next time you log in "
                    "from this browser or any other.")
        if st.session_state.df is None:
            st.info("Load a dataset first to save it.")
        else:
            c1, c2 = st.columns([3, 1])
            with c1:
                save_name = st.text_input("Save current dataset as", value=st.session_state.dataset_name or "my_dataset")
            with c2:
                st.write("")
                st.write("")
                if st.button("💾 Save", use_container_width=True):
                    try:
                        dataset_store.save_dataset(user["id"], save_name, st.session_state.df)
                        st.success(f"Saved '{save_name}' to your account.")
                    except dataset_store.DatasetStoreError as e:
                        st.error(str(e))

        st.divider()
        st.markdown("#### Your saved datasets")
        saved = dataset_store.list_saved_datasets(user["id"])
        if saved.empty:
            st.caption("Nothing saved yet.")
        else:
            for _, row in saved.iterrows():
                c1, c2, c3 = st.columns([4, 1, 1])
                c1.markdown(f"**{row['name']}** — {row['row_count']:,} rows × {row['col_count']} cols "
                            f"· {row['size_bytes']/1024:.0f} KB · saved {row['created_at']}")
                if c2.button("Load", key=f"load_saved_{row['name']}"):
                    try:
                        loaded = dataset_store.load_dataset(user["id"], row["name"])
                        register_dataset(row["name"], loaded, activate=True)
                        st.success(f"Loaded '{row['name']}' — now your active dataset.")
                        st.rerun()
                    except dataset_store.DatasetStoreError as e:
                        st.error(str(e))
                if c3.button("Delete", key=f"delete_saved_{row['name']}"):
                    dataset_store.delete_dataset(user["id"], row["name"])
                    st.rerun()


# --------------------------- Data Explorer ------------------------------
def page_explorer():
    st.title("🔍 Data Explorer")
    df = require_data()
    if df is None:
        return
    df_f = render_filters(df, key_prefix="explorer")

    tabs = st.tabs(["Overview", "Data Quality", "Numeric Stats", "Categorical Breakdown",
                     "☁️ Word Cloud", "Raw Data"])

    with tabs[0]:
        ov = data_profiler.overview(df_f)
        cols = st.columns(4)
        cols[0].markdown(viz.kpi_card("Rows", f"{ov['rows']:,}"), unsafe_allow_html=True)
        cols[1].markdown(viz.kpi_card("Columns", f"{ov['columns']}"), unsafe_allow_html=True)
        cols[2].markdown(viz.kpi_card("Memory", f"{ov['memory_mb']} MB"), unsafe_allow_html=True)
        cols[3].markdown(viz.kpi_card("Missing", f"{ov['missing_pct']}%"), unsafe_allow_html=True)
        st.write("")
        # --- Feature 3: Data Health Score, echoed here for convenience ---
        hs = extra.health_score(df_f)
        color = extra.health_score_badge_color(hs["score"])
        st.markdown(f"**Data Health Score:** <span style='color:{color}; font-weight:800;'>"
                    f"{hs['score']}/100</span>", unsafe_allow_html=True)
        st.write(f"**Numeric columns:** {', '.join(ov['numeric_columns']) or '—'}")
        st.write(f"**Categorical columns:** {', '.join(ov['categorical_columns']) or '—'}")
        st.write(f"**Datetime columns:** {', '.join(ov['datetime_columns']) or '—'}")

    with tabs[1]:
        st.dataframe(data_profiler.data_quality_report(df_f), use_container_width=True, hide_index=True)
        # --- Feature 4: per-column quality traffic lights -----------------
        st.markdown("#### 🚦 Per-column quality")
        st.dataframe(extra.quality_traffic_lights(df_f), use_container_width=True, hide_index=True)

    with tabs[2]:
        summary = data_profiler.numeric_summary(df_f)
        if summary.empty:
            st.info("No numeric columns.")
        else:
            st.dataframe(summary, use_container_width=True)
            numeric_cols = df_f.select_dtypes(include=np.number).columns.tolist()
            if numeric_cols:
                col = st.selectbox("Histogram for", numeric_cols)
                fig = viz.histogram(df_f, col, title=f"Distribution of {col}")
                st.plotly_chart(fig, use_container_width=True)
                # --- Feature 16 & 17: download chart as HTML / data as CSV
                dc1, dc2 = st.columns(2)
                with dc1:
                    st.download_button("💾 Download chart as HTML", fig.to_html(include_plotlyjs="cdn"),
                                        file_name=f"{col}_histogram.html", mime="text/html", key="hist_html")
                with dc2:
                    st.download_button("📤 Download chart data as CSV",
                                        report_generator.to_csv_bytes(df_f[[col]].dropna()),
                                        file_name=f"{col}_data.csv", mime="text/csv", key="hist_csv")

                # --- Feature 20: chart-type suggestion -----------------------
                with st.expander("🎯 Suggest the best chart for two columns"):
                    all_cols = df_f.columns.tolist()
                    sc1, sc2 = st.columns(2)
                    with sc1:
                        sug_a = st.selectbox("Column A", all_cols, key="suggest_a")
                    with sc2:
                        sug_b = st.selectbox("Column B (optional)", ["(none)"] + all_cols, key="suggest_b")
                    b_arg = None if sug_b == "(none)" else sug_b
                    suggestion = extra.suggest_chart(df_f, sug_a, b_arg)
                    st.info(f"**Recommended: {suggestion['chart']}** : {suggestion['reason']}")

    with tabs[3]:
        cat_summaries = data_profiler.categorical_summary(df_f)
        if not cat_summaries:
            st.info("No categorical columns.")
        for col, table in cat_summaries.items():
            with st.expander(f"'{col}' : top values"):
                st.dataframe(table, use_container_width=True, hide_index=True)

    with tabs[4]:
        # --- Feature 6: word cloud for text/categorical columns -------------
        text_cols = df_f.select_dtypes(include="object").columns.tolist()
        if not text_cols:
            st.info("No text/categorical columns to build a word cloud from.")
        else:
            wc_col = st.selectbox("Column", text_cols, key="wordcloud_col")
            st.plotly_chart(extra.wordcloud_figure(df_f, wc_col), use_container_width=True)

    with tabs[5]:
        # --- Feature 18: global full-text row search --------------------
        search_term = st.text_input("🔍 Search across all columns", key="explorer_search")
        view_df = df_f
        if search_term:
            mask = df_f.apply(lambda r: r.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
            view_df = df_f[mask]
            st.caption(f"{len(view_df):,} row(s) match '{search_term}'")
        st.dataframe(view_df, use_container_width=True)
        st.download_button("⬇️ Download filtered data as CSV",
                            report_generator.to_csv_bytes(view_df), "filtered_data.csv", "text/csv")


# --------------------------- Analytics Dashboard --------------------------
def page_dashboard():
    st.title("📊 Analytics Dashboard")
    df = require_data()
    if df is None:
        return
    df_f = render_filters(df, key_prefix="dash")
    render_dashboard(df_f)


# --------------------------- 3D Explorer ------------------------------
def page_3d_explorer():
    st.title("🧊 3D Data Explorer")
    st.caption("Real, draggable/zoomable 3D not a screenshot. Rotate with your mouse, "
               "scroll to zoom, hover any point or cell for its exact value.")
    df = require_data()
    if df is None:
        return

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = [c for c in df.columns if c not in numeric_cols]

    if len(numeric_cols) < 2:
        st.warning("Need at least 2 numeric columns for 3D exploration.")
        return

    tab_scatter, tab_surface, tab_density = st.tabs(
        ["🔵 3D Scatter", "🌐 Correlation Surface", "🏔️ Density Landscape"]
    )

    with tab_scatter:
        if len(numeric_cols) < 3:
            st.info("Add at least 3 numeric columns to plot a true X/Y/Z scatter. "
                     "Showing a flat scatter lifted onto a Z=0 plane instead.")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            x = st.selectbox("X axis", numeric_cols, index=0, key="p3d_x")
        with c2:
            y = st.selectbox("Y axis", numeric_cols,
                              index=min(1, len(numeric_cols) - 1), key="p3d_y")
        with c3:
            z_options = numeric_cols if len(numeric_cols) >= 3 else numeric_cols
            z = st.selectbox("Z axis", z_options,
                              index=min(2, len(z_options) - 1), key="p3d_z")
        with c4:
            color = st.selectbox("Color by", ["(none)"] + cat_cols + numeric_cols, key="p3d_color")
        color_arg = None if color == "(none)" else color
        sample = df if len(df) <= 4000 else df.sample(4000, random_state=42)
        st.plotly_chart(viz.scatter_3d(sample, x, y, z, color=color_arg, title=f"{x} × {y} × {z}"),
                         use_container_width=True)

    with tab_surface:
        if len(numeric_cols) < 2:
            st.info("Need at least 2 numeric columns.")
        else:
            corr = df[numeric_cols].corr(numeric_only=True).round(2)
            st.plotly_chart(viz.surface_3d_correlation(corr), use_container_width=True)

    with tab_density:
        c1, c2 = st.columns(2)
        with c1:
            dx = st.selectbox("X axis", numeric_cols, index=0, key="p3d_density_x")
        with c2:
            dy = st.selectbox("Y axis", numeric_cols,
                               index=min(1, len(numeric_cols) - 1), key="p3d_density_y")
        st.plotly_chart(viz.surface_3d_density(df, dx, dy, title=f"Where {dx} × {dy} concentrate"),
                         use_container_width=True)


# --------------------------- AI Analyst ------------------------------
def page_ai_analyst():
    st.title("🤖 AI Analyst")
    st.caption("Ask a question in plain English. Every number is computed live from your data never guessed.")
    df = require_data()
    if df is None:
        return

    with st.expander("💡 Example questions"):
        st.markdown(
            "- What is the total revenue?\n"
            "- Which product generated the highest revenue?\n"
            "- What is the monthly revenue trend?\n"
            "- Which region performs best?\n"
            "- Is there a correlation between quantity and profit?\n"
            "- Average profit for orders\n"
            "- Top 5 category by revenue"
        )

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("chart"):
                st.plotly_chart(msg["chart"], use_container_width=True)
            if msg.get("table") is not None:
                st.dataframe(msg["table"], use_container_width=True, hide_index=True)

    question = st.chat_input("Ask about your data…")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            try:
                result = query_engine.answer_question(question, df, st.session_state.last_metric_col)
                narration = narrate(result)
                if result.plan.metric_col:
                    st.session_state.last_metric_col = result.plan.metric_col

                answer_md = f"**Finding:** {narration['finding']}\n\n" \
                            f"**Explanation:** {narration['explanation']}\n\n" \
                            f"**Business Impact:** {narration['business_impact']}\n\n" \
                            f"**Recommendation:** {narration['recommendation']}"
                if result.plan.resolved_note:
                    answer_md = f"_{result.plan.resolved_note}_\n\n" + answer_md
                st.markdown(answer_md)

                chart = None
                if result.chart_hint == "bar" and not result.data.empty:
                    chart = viz.bar_chart(result.data, result.data.columns[0], result.data.columns[1],
                                           horizontal=True)
                    st.plotly_chart(chart, use_container_width=True)
                elif result.chart_hint == "line" and not result.data.empty:
                    chart = viz.line_chart(result.data, result.data.columns[0], result.data.columns[1])
                    st.plotly_chart(chart, use_container_width=True)
                elif result.chart_hint == "kpi" and result.scalar is not None:
                    st.markdown(viz.kpi_card(question, human_number(result.scalar)), unsafe_allow_html=True)

                table = result.data if result.chart_hint in ("bar", "table") and not result.data.empty else None
                if table is not None:
                    st.dataframe(table, use_container_width=True, hide_index=True)

                st.session_state.chat_history.append({
                    "role": "assistant", "content": answer_md, "chart": chart, "table": table,
                })
            except query_engine.QueryError as e:
                st.error(str(e))
                st.session_state.chat_history.append({"role": "assistant", "content": f"⚠️ {e}"})


# --------------------------- Automated EDA ------------------------------
def page_eda():
    st.title("📈 Automated EDA")
    df = require_data()
    if df is None:
        return

    if st.button("🚀 Generate EDA report", type="primary"):
        with st.spinner("Analyzing dataset…"):
            st.session_state.eda_report = eda_generator.generate_eda_report(df)

    report = st.session_state.eda_report
    if not report:
        st.info("Click the button above to generate a one-click exploratory report.")
        return

    st.subheader("Key Findings")
    for f in report["key_findings"]:
        st.markdown(f"- {f}")

    st.subheader("Recommendations")
    for r in report["recommendations"]:
        st.markdown(f"- {r}")

    if not report["correlation_matrix"].empty:
        st.subheader("Correlation Matrix")
        st.plotly_chart(viz.heatmap(report["correlation_matrix"]), use_container_width=True)

    if not report["outliers"].empty:
        st.subheader("Outlier Scan (IQR method)")
        st.dataframe(report["outliers"], use_container_width=True, hide_index=True)


# --------------------------- Forecasting ------------------------------
def page_forecasting():
    st.title("🔮 Forecasting")
    st.caption("Explainable trend projections not a guarantee of future results.")
    df = require_data()
    if df is None:
        return

    date_cols = df.select_dtypes(include="datetime64[ns]").columns.tolist()
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()

    if not date_cols or not numeric_cols:
        st.warning("Forecasting needs at least one date column and one numeric column.")
        return

    method_label = st.radio(
        "Method", ["Linear trend", "Seasonal (Holt-Winters)"], horizontal=True,
        help="Linear trend fits a straight line. Seasonal additionally models a repeating "
             "cycle (e.g. a December spike every year) it needs at least two full cycles "
             "of history to work.",
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        date_col = st.selectbox("Date column", date_cols)
    with c2:
        metric_col = st.selectbox("Metric to forecast", numeric_cols)
    with c3:
        freq_label = st.selectbox("Granularity", ["Monthly", "Weekly", "Daily"])
        freq = {"Monthly": "ME", "Weekly": "W", "Daily": "D"}[freq_label]
    with c4:
        periods = st.number_input("Periods ahead", min_value=1, max_value=52, value=6)

    if st.button("Run forecast", type="primary"):
        try:
            if method_label.startswith("Seasonal"):
                try:
                    result = forecasting.forecast_seasonal(df, date_col, metric_col, int(periods), freq)
                except forecasting.ForecastError as e:
                    st.warning(f"{e}\n\nFalling back to the Linear trend method for this run.")
                    result = forecasting.forecast_linear(df, date_col, metric_col, int(periods), freq)
            else:
                result = forecasting.forecast_linear(df, date_col, metric_col, int(periods), freq)
            st.session_state.forecast_result = result
        except forecasting.ForecastError as e:
            st.error(str(e))
            return

    result = st.session_state.forecast_result
    if result:
        st.info(result["disclaimer"])
        c1, c2, c3 = st.columns(3)
        c1.markdown(viz.kpi_card("Trend direction", result["trend_direction"].title()), unsafe_allow_html=True)
        c2.markdown(viz.kpi_card("Avg change / period", human_number(result["avg_period_change"])), unsafe_allow_html=True)
        c3.markdown(viz.kpi_card("Fit quality (R²)", f"{result['r_squared']:.2f}"), unsafe_allow_html=True)

        fig = viz.forecast_chart(result["history"], result["forecast"], date_col,
                                  title=f"{metric_col.replace('_',' ').title()} forecast "
                                        f"({result.get('method','linear').title()})")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(result["forecast"], use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download forecast as CSV",
                            report_generator.to_csv_bytes(result["forecast"]),
                            "forecast.csv", "text/csv")

        if result.get("method") == "seasonal":
            with st.expander("📉 See the seasonal decomposition (trend / seasonal / residual)"):
                try:
                    dec = forecasting.decompose_seasonal(df, date_col, metric_col, freq)
                    st.plotly_chart(
                        viz.seasonal_decomposition_chart(dec["table"], date_col,
                                                          title=f"Decomposition (period = {dec['period']})"),
                        use_container_width=True,
                    )
                except forecasting.ForecastError as e:
                    st.info(str(e))


# --------------------------- Anomaly Detection ------------------------------
def page_anomaly():
    st.title("⚠️ Anomaly Detection")
    st.caption("IQR-based statistical outlier flagging transparent, not a black box.")
    df = require_data()
    if df is None:
        return

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    if not numeric_cols:
        st.warning("No numeric columns to scan for anomalies.")
        return

    id_candidates = [c for c in df.columns if "id" in c.lower() or "name" in c.lower()][:2]

    if st.button("🚨 Scan all numeric columns", type="primary"):
        st.session_state.anomaly_summary = anomaly_detection.anomaly_summary(df, numeric_cols)

    if st.session_state.anomaly_summary is not None:
        st.subheader("Summary")
        st.dataframe(st.session_state.anomaly_summary, use_container_width=True, hide_index=True)

    st.subheader("Inspect a specific column")
    col = st.selectbox("Column", numeric_cols)
    try:
        detail = anomaly_detection.detect_anomalies(df, col, id_candidates)
    except ValueError as e:
        st.error(str(e))
        detail = pd.DataFrame()

    if detail.empty:
        st.success(f"No anomalies detected in '{col}'.")
    else:
        st.warning(f"{len(detail)} anomalies found in '{col}'.")
        st.dataframe(detail, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download anomalies as CSV",
                            report_generator.to_csv_bytes(detail), f"anomalies_{col}.csv", "text/csv")


# --------------------------- Customer Segmentation ------------------------------
def page_segmentation():
    st.title("👥 Customer Segmentation")
    df = require_data()
    if df is None:
        return

    method = st.radio("Method", ["RFM (rule-based)", "K-Means (data-driven)"], horizontal=True)
    date_cols = df.select_dtypes(include="datetime64[ns]").columns.tolist()
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = [c for c in df.columns if c not in numeric_cols and c not in date_cols]

    if method.startswith("RFM"):
        if not date_cols or not numeric_cols or not cat_cols:
            st.warning("RFM needs a customer/ID column, a date column, and a monetary (numeric) column.")
            return
        c1, c2, c3 = st.columns(3)
        with c1:
            customer_col = st.selectbox("Customer ID column", cat_cols)
        with c2:
            date_col = st.selectbox("Order date column", date_cols)
        with c3:
            amount_col = st.selectbox("Amount column", numeric_cols)

        if st.button("Compute RFM segments", type="primary"):
            try:
                rfm = segmentation.compute_rfm(df, customer_col, date_col, amount_col)
                st.session_state.rfm_result = rfm
            except segmentation.SegmentationError as e:
                st.error(str(e))
                return

        rfm = st.session_state.rfm_result
        if rfm is not None:
            explanations = segmentation.segment_explanations()
            seg_counts = rfm["segment"].value_counts().reset_index()
            seg_counts.columns = ["segment", "customers"]

            c1, c2 = st.columns([1, 1])
            with c1:
                st.plotly_chart(viz.pie_chart(seg_counts, "segment", "customers", "Segment distribution"),
                                 use_container_width=True)
            with c2:
                for seg in seg_counts["segment"]:
                    st.markdown(f"**{seg}** : {explanations.get(seg, '')}")

            st.dataframe(rfm, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Download RFM table as CSV",
                                report_generator.to_csv_bytes(rfm), "rfm_segments.csv", "text/csv")

    else:
        if len(numeric_cols) < 2:
            st.warning("K-Means needs at least 2 numeric columns.")
            return
        features = st.multiselect("Features to cluster on", numeric_cols, default=numeric_cols[:2])
        k = st.slider("Number of clusters", 2, 8, 4)
        if len(features) >= 2 and st.button("Run K-Means", type="primary"):
            try:
                clustered = segmentation.kmeans_segment(df, features, k)
                st.session_state.kmeans_result = clustered
            except segmentation.SegmentationError as e:
                st.error(str(e))
                return

        clustered = st.session_state.get("kmeans_result")
        if clustered is not None:
            if len(features) >= 3:
                view3d = st.checkbox("🧊 View clusters in 3D", value=True, key="seg_3d_toggle")
            else:
                view3d = False
            if view3d:
                z_feat = st.selectbox("Z axis", features[2:] or features, key="seg_3d_z")
                st.plotly_chart(
                    viz.scatter_3d(clustered, features[0], features[1], z_feat, color="cluster",
                                    title="Cluster scatter (3D)"),
                    use_container_width=True,
                )
            else:
                st.plotly_chart(
                    viz.scatter_chart(clustered, features[0], features[1], color="cluster",
                                       title="Cluster scatter"),
                    use_container_width=True,
                )
            st.dataframe(clustered, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Download clusters as CSV",
                                report_generator.to_csv_bytes(clustered), "kmeans_clusters.csv", "text/csv")


# --------------------------- AI Recommendations ------------------------------
def page_recommendations():
    st.title("💡 AI Recommendations")
    st.caption("A prioritized action list synthesized from every analysis you've already run this session.")
    df = require_data()
    if df is None:
        return

    session_snapshot = {
        "eda_report": st.session_state.eda_report,
        "anomaly_summary": st.session_state.anomaly_summary,
        "forecast_result": st.session_state.forecast_result,
        "rfm_result": st.session_state.rfm_result,
    }
    recs = recommendation_engine.build_recommendations(session_snapshot)

    color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
    for r in recs:
        with st.container():
            st.markdown(f"### {color.get(r['priority'],'⚪')} {r['title']}")
            st.markdown(f"{r['detail']}")
            st.caption(f"Priority: {r['priority']} · Source: {r['source']}")
            st.divider()


# --------------------------- Reports ------------------------------
def page_reports():
    st.title("📄 Reports")
    df = require_data()
    if df is None:
        return

    st.markdown("Export whatever you've analyzed this session.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Current dataset")
        st.download_button("⬇️ CSV", report_generator.to_csv_bytes(df), "dataset.csv", "text/csv")
        st.download_button("⬇️ Excel", report_generator.to_excel_bytes(df, "Data"),
                            "dataset.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with c2:
        st.subheader("Full session report")
        if st.button("🧾 Build combined report", type="primary"):
            sections = []
            ov = data_profiler.overview(df)
            sections.append({"heading": "Dataset Overview", "html": pd.DataFrame([ov]).to_html(index=False)})

            if st.session_state.eda_report:
                sections.append({"heading": "Key Findings",
                                  "html": "<ul>" + "".join(f"<li>{f}</li>" for f in st.session_state.eda_report["key_findings"]) + "</ul>"})
            if st.session_state.anomaly_summary is not None:
                sections.append({"heading": "Anomaly Summary",
                                  "html": st.session_state.anomaly_summary.to_html(index=False)})
            if st.session_state.forecast_result:
                sections.append({"heading": "Forecast",
                                  "html": st.session_state.forecast_result["forecast"].to_html(index=False)})
            if st.session_state.rfm_result is not None:
                sections.append({"heading": "Customer Segments",
                                  "html": st.session_state.rfm_result.head(50).to_html(index=False)})

            html = report_generator.build_html_report(
                st.session_state.dataset_name or "Report", sections, current_user().get("username", "")
            )
            st.session_state["_report_html"] = html
            st.success("Report built download it below.")

        html = st.session_state.get("_report_html")
        if html:
            d1, d2 = st.columns(2)
            with d1:
                st.download_button("⬇️ HTML (printable to PDF via browser)", html.encode("utf-8"),
                                    "veridexa_report.html", "text/html", use_container_width=True)
            with d2:
                try:
                    pdf_bytes = report_generator.to_pdf_bytes(html)
                    st.download_button("⬇️ PDF (native export)", pdf_bytes,
                                        "veridexa_report.pdf", "application/pdf", use_container_width=True)
                except report_generator.PdfExportError as e:
                    st.warning(str(e))


# --------------------------- Account ------------------------------
# --------------------------- Activity Log ------------------------------
def page_activity_log():
    st.title("🕒 Activity Log")
    st.caption("Feature every meaningful action you take is recorded here "
               "(and surfaces as a toast notification when it happens).")
    user = current_user()
    rows = fetch_audit_log(user.get("id"))
    if not rows:
        st.info("No activity recorded yet this account.")
        return
    log_df = pd.DataFrame(rows)
    log_df.columns = ["Action", "Detail", "When (UTC)"]
    st.dataframe(log_df, use_container_width=True, hide_index=True)


def page_account():
    st.title("⚙️ Account")
    user = current_user()
    st.write(f"**Username:** {user.get('username')}")
    st.write(f"**Email:** {user.get('email')}")
    if user.get("full_name"):
        st.write(f"**Full name:** {user.get('full_name')}")

    if st.session_state.login_time is not None:
        expires = st.session_state.login_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        st.caption(f"🔒 Signed in since {st.session_state.login_time.strftime('%Y-%m-%d %H:%M UTC')} "
                   f"session expires {expires.strftime('%H:%M UTC')} "
                   f"({SESSION_TIMEOUT_MINUTES}-minute limit) unless you log back in.")

    st.divider()
    st.subheader("Change password")
    with st.form("change_pw"):
        old = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Update password", type="primary"):
            try:
                change_password(user["id"], old, new, confirm)
                st.success("Password updated.")
            except AuthError as e:
                st.error(str(e))

    st.divider()
    st.subheader("Saved datasets")
    saved = dataset_store.list_saved_datasets(user["id"])
    if saved.empty:
        st.caption("Nothing saved yet you can save a dataset from the "
                   "**📂 Upload & Clean → 💾 Persistent storage** tab.")
    else:
        st.dataframe(saved, use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------
# Route
# ----------------------------------------------------------------------
choice = sidebar_nav()

ROUTES = {
    "🏠 Home": page_home,
    "📂 Upload & Clean": page_upload,
    "🔍 Data Explorer": page_explorer,
    "📊 Analytics Dashboard": page_dashboard,
    "🧊 3D Explorer": page_3d_explorer,
    "🤖 AI Analyst": page_ai_analyst,
    "📈 Automated EDA": page_eda,
    "🔮 Forecasting": page_forecasting,
    "⚠️ Anomaly Detection": page_anomaly,
    "👥 Customer Segmentation": page_segmentation,
    "💡 AI Recommendations": page_recommendations,
    "📄 Reports": page_reports,
    "🕒 Activity Log": page_activity_log,
    "⚙️ Account": page_account,
}
ROUTES.get(choice, page_home)()
