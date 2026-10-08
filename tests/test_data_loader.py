from modules.data_loader import _clean_column_names, _infer_dtypes
import pandas as pd


def test_sample_dataset_loads(sample_df):
    assert len(sample_df) > 0
    assert "revenue" in sample_df.columns
    assert pd.api.types.is_datetime64_any_dtype(sample_df["order_date"])


def test_clean_column_names_dedupes():
    df = pd.DataFrame({"Revenue $": [1], "revenue_": [2], "revenue": [3]})
    out = _clean_column_names(df)
    assert len(set(out.columns)) == 3


def test_infer_dtypes_numeric_coercion():
    df = pd.DataFrame({"amount": ["1", "2", "3", "x"]})
    out = _infer_dtypes(df)
    # Not >=90% numeric with one bad value out of 4 -> stays text (object, or
    # pandas' newer StringDtype depending on version — either is "not coerced").
    assert out["amount"].dtype == object or pd.api.types.is_string_dtype(out["amount"])
