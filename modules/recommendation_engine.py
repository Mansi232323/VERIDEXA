"""
VERIDEXA recommendation engine.
Synthesizes a prioritized action list purely from analysis results
already computed and stored in session state during this visit — it
does not invent new analysis, just prioritizes what's been found.
"""
from __future__ import annotations


def build_recommendations(session: dict) -> list[dict]:
    """`session` is a plain dict snapshot of the relevant bits of
    st.session_state (EDA results, anomalies, forecast, RFM, etc.)."""
    recs: list[dict] = []

    eda = session.get("eda_report")
    if eda:
        if eda["overview"]["duplicate_rows"] > 0:
            recs.append({"priority": "High", "title": "Remove duplicate rows",
                         "detail": f"{eda['overview']['duplicate_rows']} duplicate rows are inflating totals.",
                         "source": "Data Quality"})
        if eda["overview"]["missing_pct"] > 5:
            recs.append({"priority": "High", "title": "Address missing data",
                         "detail": f"{eda['overview']['missing_pct']}% of cells are missing across the dataset.",
                         "source": "Data Quality"})
        for a, b, r in eda.get("strong_correlations", [])[:2]:
            recs.append({"priority": "Medium", "title": f"Investigate '{a}' ↔ '{b}' relationship",
                         "detail": f"Correlation r = {r} could indicate a lever or redundancy.",
                         "source": "EDA"})

    anomalies = session.get("anomaly_summary")
    if anomalies is not None and not anomalies.empty:
        top = anomalies.iloc[0]
        if top["anomalies_found"] > 0:
            recs.append({"priority": "Medium", "title": f"Review outliers in '{top['column']}'",
                         "detail": f"{int(top['anomalies_found'])} flagged records ({top['pct_of_data']}% of data).",
                         "source": "Anomaly Detection"})

    forecast = session.get("forecast_result")
    if forecast:
        direction = forecast.get("trend_direction")
        if direction == "downward":
            recs.append({"priority": "High", "title": "Plan for a declining trend",
                         "detail": "The forecast shows a downward trajectory consider intervention.",
                         "source": "Forecasting"})
        elif direction == "upward":
            recs.append({"priority": "Low", "title": "Capitalize on upward momentum",
                         "detail": "The forecast shows continued growth consider scaling what's working.",
                         "source": "Forecasting"})

    rfm = session.get("rfm_result")
    if rfm is not None and not rfm.empty:
        churn_risk = rfm[rfm["segment"].isin(["At-Risk High Value", "Lost / Churned", "At-Risk"])]
        if len(churn_risk):
            pct = round(100 * len(churn_risk) / len(rfm), 1)
            recs.append({"priority": "High", "title": "Launch a win-back campaign",
                         "detail": f"{len(churn_risk)} customers ({pct}%) fall into at-risk or churned segments.",
                         "source": "Segmentation"})

    if not recs:
        recs.append({"priority": "Low", "title": "Run more analysis",
                     "detail": "Visit the Data Explorer, Forecasting, Anomaly Detection, or Segmentation pages "
                                "to generate recommendations grounded in your data.",
                     "source": "Getting Started"})

    order = {"High": 0, "Medium": 1, "Low": 2}
    return sorted(recs, key=lambda r: order.get(r["priority"], 3))
