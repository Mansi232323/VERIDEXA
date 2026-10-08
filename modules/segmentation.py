"""
VERIDEXA - Customer Segmentation
--------------------------------

Customer segmentation using:

1. RFM Rule-Based Segmentation
   - Recency
   - Frequency
   - Monetary

2. K-Means Data-Driven Segmentation

Designed for Streamlit + Plotly.

Main UI problem fixed:
- No overlap between "Segment distribution" and legend
- Legend positioned above donut
- Proper chart height
- Proper spacing between chart and explanation panel
- Responsive layout
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px


# ============================================================
# ERROR CLASS
# ============================================================

class SegmentationError(Exception):
    """Custom exception for customer segmentation errors."""
    pass


# ============================================================
# RFM LABELS
# ============================================================

RFM_LABELS = {
    (3, 3): "Champions",
    (3, 2): "Loyal Customers",
    (2, 3): "Big Spenders",
    (2, 2): "Potential Loyalists",
    (3, 1): "Recent Customers",
    (1, 3): "At-Risk High Value",
    (1, 2): "At-Risk",
    (2, 1): "Needs Attention",
    (1, 1): "Lost / Churned",
}


# ============================================================
# SEGMENT DESCRIPTIONS
# ============================================================

SEGMENT_EXPLANATIONS = {
    "Champions":
        "Bought recently, buy often, and spend the most. "
        "Reward them because they are your strongest advocates.",

    "Loyal Customers":
        "Consistent and frequent buyers. "
        "Keep them engaged with loyalty perks and exclusive offers.",

    "Big Spenders":
        "High monetary value but lower frequency. "
        "Use personalized offers and upselling opportunities.",

    "Potential Loyalists":
        "Recent customers with decent frequency and spending. "
        "Nurture them toward Champion status.",

    "Recent Customers":
        "New or recently active customers with lower frequency or spending. "
        "Focus on onboarding and second-purchase conversion.",

    "At-Risk High Value":
        "Previously valuable customers who have not returned recently. "
        "Use targeted win-back campaigns before they churn.",

    "At-Risk":
        "Below-average recency suggests reduced engagement. "
        "Run a re-engagement campaign.",

    "Needs Attention":
        "Mid-range customers across the main RFM dimensions. "
        "Test targeted offers to understand what motivates them.",

    "Lost / Churned":
        "Low recency, frequency, and monetary value. "
        "Use low-cost win-back attempts only.",
}


# ============================================================
# SEGMENT ORDER
# ============================================================

SEGMENT_ORDER = [
    "Champions",
    "Loyal Customers",
    "Big Spenders",
    "Potential Loyalists",
    "Recent Customers",
    "At-Risk High Value",
    "At-Risk",
    "Needs Attention",
    "Lost / Churned",
]


# ============================================================
# RFM TERCILE SCORING
# ============================================================

def _tercile_score(
    series: pd.Series,
    reverse: bool = False
) -> pd.Series:
    """
    Convert a numerical series into scores 1, 2, 3.

    For Recency:
        lower is better
        therefore reverse=True

    For Frequency / Monetary:
        higher is better
        therefore reverse=False
    """

    series = pd.to_numeric(
        series,
        errors="coerce"
    )

    # If empty
    if len(series) == 0:
        return pd.Series(
            dtype=int,
            index=series.index
        )

    # Handle all-identical values
    if series.nunique(dropna=True) <= 1:
        return pd.Series(
            [2] * len(series),
            index=series.index,
            dtype=int
        )

    try:

        # rank(method="first") prevents qcut duplicate-edge problems
        ranked = series.rank(
            method="first"
        )

        scored = pd.qcut(
            ranked,
            q=3,
            labels=[1, 2, 3]
        )

        scored = scored.astype(int)

    except (ValueError, TypeError):

        # Fallback using percentile ranks
        percentile = series.rank(
            method="average",
            pct=True
        )

        scored = pd.Series(
            np.select(
                [
                    percentile <= 1 / 3,
                    percentile <= 2 / 3
                ],
                [
                    1,
                    2
                ],
                default=3
            ),
            index=series.index
        ).astype(int)

    if reverse:
        scored = 4 - scored

    return scored


# ============================================================
# COMBINE FREQUENCY + MONETARY
# ============================================================

def _combine_fm(
    f_score: int,
    m_score: int
) -> int:

    average_score = round(
        (f_score + m_score) / 2
    )

    return int(
        min(
            3,
            max(
                1,
                average_score
            )
        )
    )


# ============================================================
# COMPUTE RFM
# ============================================================

def compute_rfm(
    df: pd.DataFrame,
    customer_col: str,
    date_col: str,
    amount_col: str,
    snapshot_date=None
) -> pd.DataFrame:

    # --------------------------------------------------------
    # Validate dataframe
    # --------------------------------------------------------

    if df is None:
        raise SegmentationError(
            "Dataset is empty."
        )

    if df.empty:
        raise SegmentationError(
            "Dataset contains no rows."
        )

    # --------------------------------------------------------
    # Validate columns
    # --------------------------------------------------------

    required_columns = [
        customer_col,
        date_col,
        amount_col
    ]

    for column in required_columns:

        if column not in df.columns:

            raise SegmentationError(
                f"Column '{column}' not found in dataset."
            )

    # --------------------------------------------------------
    # Select required data
    # --------------------------------------------------------

    sub = df[
        [
            customer_col,
            date_col,
            amount_col
        ]
    ].copy()

    # --------------------------------------------------------
    # Convert data types
    # --------------------------------------------------------

    sub[date_col] = pd.to_datetime(
        sub[date_col],
        errors="coerce"
    )

    sub[amount_col] = pd.to_numeric(
        sub[amount_col],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Remove invalid rows
    # --------------------------------------------------------

    sub = sub.dropna(
        subset=[
            customer_col,
            date_col,
            amount_col
        ]
    )

    if sub.empty:

        raise SegmentationError(
            "No valid rows available for RFM. "
            "Check customer, date and amount columns."
        )

    # --------------------------------------------------------
    # Snapshot date
    # --------------------------------------------------------

    if snapshot_date is None:

        snapshot_date = (
            sub[date_col].max()
            + pd.Timedelta(days=1)
        )

    else:

        snapshot_date = pd.to_datetime(
            snapshot_date
        )

    # --------------------------------------------------------
    # RFM aggregation
    # --------------------------------------------------------

    rfm = (
        sub
        .groupby(customer_col)
        .agg(
            recency=(
                date_col,
                lambda x: (
                    snapshot_date - x.max()
                ).days
            ),

            frequency=(
                date_col,
                "count"
            ),

            monetary=(
                amount_col,
                "sum"
            )
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # Remove invalid RFM values
    # --------------------------------------------------------

    rfm = rfm[
        rfm["recency"].notna()
        & rfm["frequency"].notna()
        & rfm["monetary"].notna()
    ].copy()

    if rfm.empty:

        raise SegmentationError(
            "Unable to calculate RFM values."
        )

    # --------------------------------------------------------
    # RFM scores
    # --------------------------------------------------------

    # Lower recency = better
    rfm["r_score"] = _tercile_score(
        rfm["recency"],
        reverse=True
    )

    # Higher frequency = better
    rfm["f_score"] = _tercile_score(
        rfm["frequency"],
        reverse=False
    )

    # Higher monetary = better
    rfm["m_score"] = _tercile_score(
        rfm["monetary"],
        reverse=False
    )

    # --------------------------------------------------------
    # Segment assignment
    # --------------------------------------------------------

    def assign_segment(row):

        r_score = int(
            row["r_score"]
        )

        fm_score = _combine_fm(
            int(row["f_score"]),
            int(row["m_score"])
        )

        return RFM_LABELS.get(
            (
                r_score,
                fm_score
            ),
            "Needs Attention"
        )

    rfm["segment"] = rfm.apply(
        assign_segment,
        axis=1
    )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    rfm = (
        rfm
        .sort_values(
            "monetary",
            ascending=False
        )
        .reset_index(drop=True)
    )

    return rfm


# ============================================================
# SEGMENT EXPLANATIONS
# ============================================================

def segment_explanations():

    return SEGMENT_EXPLANATIONS.copy()


# ============================================================
# K-MEANS SEGMENTATION
# ============================================================

def kmeans_segment(
    df: pd.DataFrame,
    feature_cols: list[str],
    n_clusters: int = 4
) -> pd.DataFrame:

    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    # --------------------------------------------------------
    # Validate number of clusters
    # --------------------------------------------------------

    if n_clusters < 2:

        raise SegmentationError(
            "Number of clusters must be at least 2."
        )

    # --------------------------------------------------------
    # Validate columns
    # --------------------------------------------------------

    missing_columns = [
        col
        for col in feature_cols
        if col not in df.columns
    ]

    if missing_columns:

        raise SegmentationError(
            "Missing feature columns: "
            + ", ".join(missing_columns)
        )

    # --------------------------------------------------------
    # Prepare data
    # --------------------------------------------------------

    sub = df[
        feature_cols
    ].copy()

    for column in feature_cols:

        sub[column] = pd.to_numeric(
            sub[column],
            errors="coerce"
        )

    sub = sub.dropna()

    # --------------------------------------------------------
    # Validate rows
    # --------------------------------------------------------

    if len(sub) < n_clusters:

        raise SegmentationError(
            f"Need at least {n_clusters} "
            "complete rows to create clusters."
        )

    # --------------------------------------------------------
    # Scale features
    # --------------------------------------------------------

    scaler = StandardScaler()

    scaled = scaler.fit_transform(
        sub
    )

    # --------------------------------------------------------
    # K-Means
    # --------------------------------------------------------

    model = KMeans(
        n_clusters=n_clusters,
        n_init=10,
        random_state=42
    )

    labels = model.fit_predict(
        scaled
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    output = sub.copy()

    output["cluster"] = [
        f"Cluster {int(label) + 1}"
        for label in labels
    ]

    return output.reset_index(
        drop=True
    )


# ============================================================
# DONUT CHART
# ============================================================

def create_segment_donut(
    rfm: pd.DataFrame
):

    # --------------------------------------------------------
    # Count segments
    # --------------------------------------------------------

    segment_counts = (
        rfm["segment"]
        .value_counts()
        .reindex(
            SEGMENT_ORDER,
            fill_value=0
        )
        .reset_index()
    )

    segment_counts.columns = [
        "segment",
        "customers"
    ]

    # Remove zero segments
    segment_counts = segment_counts[
        segment_counts["customers"] > 0
    ].copy()

    if segment_counts.empty:

        raise SegmentationError(
            "No customer segments available."
        )

    # --------------------------------------------------------
    # Percentages
    # --------------------------------------------------------

    total_customers = (
        segment_counts["customers"]
        .sum()
    )

    segment_counts["percentage"] = (
        segment_counts["customers"]
        / total_customers
        * 100
    )

    # --------------------------------------------------------
    # Plotly donut
    # --------------------------------------------------------

    fig = px.pie(
        segment_counts,
        names="segment",
        values="customers",
        hole=0.52
    )

    # --------------------------------------------------------
    # Donut styling
    # --------------------------------------------------------

    fig.update_traces(

        textposition="inside",

        texttemplate=(
            "%{percent:.1%}"
        ),

        insidetextorientation="horizontal",

        hovertemplate=(
            "<b>%{label}</b><br>"
            "Customers: %{value}<br>"
            "Share: %{percent:.1%}"
            "<extra></extra>"
        ),

        marker=dict(
            line=dict(
                width=2
            )
        )
    )

    # --------------------------------------------------------
    # IMPORTANT LAYOUT FIX
    # --------------------------------------------------------

    fig.update_layout(

        height=500,

        margin=dict(
            l=10,
            r=10,
            t=85,
            b=20
        ),

        paper_bgcolor="rgba(0,0,0,0)",

        plot_bgcolor="rgba(0,0,0,0)",

        font=dict(
            size=12
        ),

        # ----------------------------------------------------
        # FIXED HORIZONTAL LEGEND
        # ----------------------------------------------------

        legend=dict(

            orientation="h",

            yanchor="bottom",

            y=1.02,

            xanchor="center",

            x=0.5,

            bgcolor="rgba(0,0,0,0)",

            borderwidth=0,

            font=dict(
                size=10
            ),

            itemwidth=90,

            tracegroupgap=2
        ),

        showlegend=True
    )

    return fig, segment_counts


# ============================================================
# SEGMENT EXPLANATION PANEL
# ============================================================

def render_segment_explanations():

    st.markdown(
        """
        <div style="
            font-size:20px;
            font-weight:700;
            margin-bottom:18px;
        ">
            Segment Insights
        </div>
        """,
        unsafe_allow_html=True
    )

    for segment in SEGMENT_ORDER:

        description = SEGMENT_EXPLANATIONS.get(
            segment,
            ""
        )

        st.markdown(
            f"""
            <div style="
                margin-bottom:20px;
                line-height:1.65;
                font-size:15px;
            ">

                <div style="
                    font-weight:700;
                    margin-bottom:3px;
                ">
                    {segment}
                </div>

                <div style="
                    opacity:0.88;
                ">
                    {description}
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# KPI CARDS
# ============================================================

def render_rfm_kpis(
    rfm: pd.DataFrame
):

    total_customers = len(rfm)

    total_revenue = (
        rfm["monetary"].sum()
    )

    avg_customer_value = (
        rfm["monetary"].mean()
    )

    avg_frequency = (
        rfm["frequency"].mean()
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Customers",
            f"{total_customers:,}"
        )

    with col2:

        st.metric(
            "Customer Value",
            f"{total_revenue:,.0f}"
        )

    with col3:

        st.metric(
            "Avg. Spend",
            f"{avg_customer_value:,.0f}"
        )

    with col4:

        st.metric(
            "Avg. Frequency",
            f"{avg_frequency:.1f}"
        )


# ============================================================
# CUSTOMER TABLE
# ============================================================

def render_customer_table(
    rfm: pd.DataFrame,
    customer_col: str
):

    st.markdown(
        """
        <div style="
            font-size:19px;
            font-weight:700;
            margin-top:25px;
            margin-bottom:10px;
        ">
            Customer Segments
        </div>
        """,
        unsafe_allow_html=True
    )

    display_df = rfm.copy()

    display_df["monetary"] = (
        display_df["monetary"]
        .round(2)
    )

    display_df["recency"] = (
        display_df["recency"]
        .astype(int)
    )

    display_df["frequency"] = (
        display_df["frequency"]
        .astype(int)
    )

    display_df = display_df[
        [
            customer_col,
            "recency",
            "frequency",
            "monetary",
            "r_score",
            "f_score",
            "m_score",
            "segment"
        ]
    ]

    display_df.columns = [
        "Customer ID",
        "Recency",
        "Frequency",
        "Monetary",
        "R Score",
        "F Score",
        "M Score",
        "Segment"
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# MAIN RFM UI
# ============================================================

def render_customer_segmentation(
    df: pd.DataFrame
):

    # ========================================================
    # PAGE TITLE
    # ========================================================

    st.markdown(
        """
        <div style="
            display:flex;
            align-items:center;
            gap:14px;
            margin-bottom:10px;
        ">

            <div style="
                font-size:40px;
            ">
                👥
            </div>

            <div style="
                font-size:38px;
                font-weight:800;
            ">
                Customer Segmentation
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # ========================================================
    # VALIDATE DATASET
    # ========================================================

    if df is None or df.empty:

        st.warning(
            "Upload a dataset first to perform customer segmentation."
        )

        return

    # ========================================================
    # METHOD
    # ========================================================

    st.markdown(
        """
        <div style="
            font-size:16px;
            font-weight:600;
            margin-top:18px;
            margin-bottom:8px;
        ">
            Method
        </div>
        """,
        unsafe_allow_html=True
    )

    method = st.radio(
        "",
        [
            "RFM (rule-based)",
            "K-Means (data-driven)"
        ],
        horizontal=True,
        key="segmentation_method"
    )

    # ========================================================
    # RFM MODE
    # ========================================================

    if method == "RFM (rule-based)":

        render_rfm_mode(
            df
        )

    # ========================================================
    # K-MEANS MODE
    # ========================================================

    else:

        render_kmeans_mode(
            df
        )


# ============================================================
# RFM MODE
# ============================================================

def render_rfm_mode(
    df: pd.DataFrame
):

    # --------------------------------------------------------
    # Column selection
    # --------------------------------------------------------

    columns = list(
        df.columns
    )

    col1, col2, col3 = st.columns(
        3,
        gap="medium"
    )

    with col1:

        st.markdown(
            "Customer ID column"
        )

        customer_col = st.selectbox(
            "",
            columns,
            key="rfm_customer_col"
        )

    with col2:

        st.markdown(
            "Order date column"
        )

        date_col = st.selectbox(
            "",
            columns,
            key="rfm_date_col"
        )

    with col3:

        st.markdown(
            "Amount column"
        )

        amount_col = st.selectbox(
            "",
            columns,
            key="rfm_amount_col"
        )

    # --------------------------------------------------------
    # Compute button
    # --------------------------------------------------------

    compute = st.button(
        "Compute RFM segments",
        type="primary",
        use_container_width=False
    )

    # --------------------------------------------------------
    # Compute RFM
    # --------------------------------------------------------

    if compute:

        try:

            with st.spinner(
                "Computing customer segments..."
            ):

                rfm = compute_rfm(
                    df=df,
                    customer_col=customer_col,
                    date_col=date_col,
                    amount_col=amount_col
                )

                st.session_state[
                    "veridexa_rfm"
                ] = rfm

                st.session_state[
                    "veridexa_rfm_customer_col"
                ] = customer_col

            st.success(
                "Customer segmentation completed successfully."
            )

        except SegmentationError as error:

            st.error(
                str(error)
            )

        except Exception as error:

            st.error(
                f"Unexpected error: {error}"
            )

    # --------------------------------------------------------
    # Load previous result
    # --------------------------------------------------------

    rfm = st.session_state.get(
        "veridexa_rfm"
    )

    stored_customer_col = (
        st.session_state.get(
            "veridexa_rfm_customer_col"
        )
    )

    if rfm is None:

        return

    # ========================================================
    # KPI SECTION
    # ========================================================

    st.markdown(
        "<div style='height:18px'></div>",
        unsafe_allow_html=True
    )

    render_rfm_kpis(
        rfm
    )

    # ========================================================
    # CHART + EXPLANATION
    # ========================================================

    st.markdown(
        "<div style='height:20px'></div>",
        unsafe_allow_html=True
    )

    chart_col, explanation_col = st.columns(
        [1.05, 1.25],
        gap="large"
    )

    # ========================================================
    # LEFT - DONUT
    # ========================================================

    with chart_col:

        st.markdown(
            """
            <div style="
                font-size:20px;
                font-weight:700;
                margin-bottom:6px;
            ">
                Segment distribution
            </div>
            """,
            unsafe_allow_html=True
        )

        try:

            fig, segment_counts = (
                create_segment_donut(
                    rfm
                )
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                    "responsive": True
                }
            )

        except SegmentationError as error:

            st.error(
                str(error)
            )

    # ========================================================
    # RIGHT - EXPLANATIONS
    # ========================================================

    with explanation_col:

        render_segment_explanations()

    # ========================================================
    # SEGMENT SUMMARY
    # ========================================================

    st.markdown(
        "<div style='height:10px'></div>",
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div style="
            font-size:20px;
            font-weight:700;
            margin-top:20px;
            margin-bottom:12px;
        ">
            Segment Summary
        </div>
        """,
        unsafe_allow_html=True
    )

    summary = (
        rfm
        .groupby("segment")
        .agg(
            Customers=(
                "segment",
                "count"
            ),
            Revenue=(
                "monetary",
                "sum"
            ),
            Avg_Recency=(
                "recency",
                "mean"
            ),
            Avg_Frequency=(
                "frequency",
                "mean"
            )
        )
        .reset_index()
    )

    summary["Revenue"] = (
        summary["Revenue"]
        .round(2)
    )

    summary["Avg_Recency"] = (
        summary["Avg_Recency"]
        .round(1)
    )

    summary["Avg_Frequency"] = (
        summary["Avg_Frequency"]
        .round(1)
    )

    summary = summary.rename(
        columns={
            "segment": "Segment"
        }
    )

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # CUSTOMER TABLE
    # ========================================================

    if stored_customer_col:

        render_customer_table(
            rfm,
            stored_customer_col
        )


# ============================================================
# K-MEANS MODE
# ============================================================

def render_kmeans_mode(
    df: pd.DataFrame
):

    st.markdown(
        """
        <div style="
            margin-top:15px;
            margin-bottom:15px;
            opacity:0.85;
        ">
            K-Means automatically groups customers based on
            numerical behavioral features.
        </div>
        """,
        unsafe_allow_html=True
    )

    numeric_columns = list(
        df.select_dtypes(
            include=np.number
        ).columns
    )

    if len(numeric_columns) < 2:

        st.warning(
            "At least two numerical columns are required "
            "for K-Means clustering."
        )

        return

    # --------------------------------------------------------
    # Feature selection
    # --------------------------------------------------------

    feature_cols = st.multiselect(
        "Select features for clustering",
        numeric_columns,
        default=numeric_columns[
            :min(3, len(numeric_columns))
        ],
        key="kmeans_features"
    )

    # --------------------------------------------------------
    # Number of clusters
    # --------------------------------------------------------

    n_clusters = st.slider(
        "Number of clusters",
        min_value=2,
        max_value=10,
        value=4,
        step=1,
        key="kmeans_clusters"
    )

    # --------------------------------------------------------
    # Run K-Means
    # --------------------------------------------------------

    if st.button(
        "Run K-Means clustering",
        type="primary"
    ):

        if len(feature_cols) < 2:

            st.error(
                "Select at least two features."
            )

            return

        try:

            with st.spinner(
                "Running K-Means..."
            ):

                result = kmeans_segment(
                    df,
                    feature_cols,
                    n_clusters
                )

                st.session_state[
                    "veridexa_kmeans"
                ] = result

            st.success(
                "K-Means clustering completed."
            )

        except SegmentationError as error:

            st.error(
                str(error)
            )

        except Exception as error:

            st.error(
                f"Unexpected error: {error}"
            )

    # --------------------------------------------------------
    # Display results
    # --------------------------------------------------------

    result = st.session_state.get(
        "veridexa_kmeans"
    )

    if result is None:

        return

    # ========================================================
    # CLUSTER DISTRIBUTION
    # ========================================================

    cluster_counts = (
        result["cluster"]
        .value_counts()
        .reset_index()
    )

    cluster_counts.columns = [
        "cluster",
        "customers"
    ]

    fig = px.pie(
        cluster_counts,
        names="cluster",
        values="customers",
        hole=0.52
    )

    fig.update_traces(
        textposition="inside",
        texttemplate="%{percent:.1%}",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Customers: %{value}<br>"
            "Share: %{percent:.1%}"
            "<extra></extra>"
        )
    )

    fig.update_layout(

        height=450,

        margin=dict(
            l=10,
            r=10,
            t=70,
            b=20
        ),

        paper_bgcolor="rgba(0,0,0,0)",

        plot_bgcolor="rgba(0,0,0,0)",

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(
                size=11
            ),
            bgcolor="rgba(0,0,0,0)"
        )
    )

    chart_col, table_col = st.columns(
        [1, 1],
        gap="large"
    )

    with chart_col:

        st.markdown(
            """
            <div style="
                font-size:20px;
                font-weight:700;
                margin-bottom:5px;
            ">
                Cluster distribution
            </div>
            """,
            unsafe_allow_html=True
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": False,
                "responsive": True
            }
        )

    with table_col:

        st.markdown(
            """
            <div style="
                font-size:20px;
                font-weight:700;
                margin-bottom:12px;
            ">
                Cluster Results
            </div>
            """,
            unsafe_allow_html=True
        )

        st.dataframe(
            result,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# OPTIONAL SIMPLE ENTRY POINT
# ============================================================

def customer_segmentation_page(
    df: pd.DataFrame
):
    """
    Use this function from the VERIDEXA main application.

    Example:

        from customer_segmentation import (
            customer_segmentation_page
        )

        customer_segmentation_page(df)
    """

    render_customer_segmentation(
        df
    )