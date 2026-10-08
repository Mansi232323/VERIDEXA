import pytest

from modules import anomaly_detection, segmentation


def test_detect_anomalies_flags_extremes(sample_df):
    found = anomaly_detection.detect_anomalies(sample_df, "revenue")
    assert "risk_level" in found.columns
    assert set(found["risk_level"].unique()) <= {"High", "Medium"}


def test_detect_anomalies_rejects_non_numeric(sample_df):
    with pytest.raises(ValueError):
        anomaly_detection.detect_anomalies(sample_df, "region")


def test_rfm_segments(sample_df):
    rfm = segmentation.compute_rfm(sample_df, "customer_id", "order_date", "revenue")
    assert {"recency", "frequency", "monetary", "segment"} <= set(rfm.columns)
    assert rfm["segment"].notna().all()


def test_rfm_missing_column_raises(sample_df):
    with pytest.raises(segmentation.SegmentationError):
        segmentation.compute_rfm(sample_df, "not_a_col", "order_date", "revenue")


def test_kmeans_segment(sample_df):
    clustered = segmentation.kmeans_segment(sample_df, ["revenue", "profit"], n_clusters=3)
    assert clustered["cluster"].nunique() <= 3
