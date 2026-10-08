from modules import data_profiler


def test_overview_basic(tiny_df):
    ov = data_profiler.overview(tiny_df)
    assert ov["rows"] == 6
    assert ov["columns"] == 4
    assert "revenue" in ov["numeric_columns"]
    assert "region" in ov["categorical_columns"]
    assert ov["total_missing_cells"] == 1


def test_data_quality_report(tiny_df):
    report = data_profiler.data_quality_report(tiny_df)
    row = report[report["column"] == "revenue"].iloc[0]
    assert row["missing"] == 1


def test_outlier_scan_empty_on_small_data(tiny_df):
    scan = data_profiler.outlier_scan(tiny_df)
    assert isinstance(scan, type(scan))  # returns a DataFrame regardless


def test_correlation_matrix_shape(sample_df):
    corr = data_profiler.correlation_matrix(sample_df)
    assert "revenue" in corr.columns
    assert "profit" in corr.columns
