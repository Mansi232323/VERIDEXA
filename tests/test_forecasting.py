import pytest

from modules import forecasting


def test_forecast_linear_basic(sample_df):
    result = forecasting.forecast_linear(sample_df, "order_date", "revenue",
                                          periods_ahead=3, freq="ME")
    assert len(result["forecast"]) == 3
    assert result["trend_direction"] in ("upward", "downward", "flat")
    assert "disclaimer" in result and len(result["disclaimer"]) > 0
    # Confidence band should widen going further out
    band_widths = (result["forecast"]["upper"] - result["forecast"]["lower"]).tolist()
    assert band_widths[-1] >= band_widths[0]


def test_forecast_requires_enough_points():
    import pandas as pd
    tiny = pd.DataFrame({"d": pd.to_datetime(["2024-01-01", "2024-01-02"]), "v": [1, 2]})
    with pytest.raises(forecasting.ForecastError):
        forecasting.forecast_linear(tiny, "d", "v")
