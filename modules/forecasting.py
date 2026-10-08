"""
VERIDEXA — forecasting.

Two methods are offered:

1. `forecast_linear` explainable linear-trend projection (ordinary
   least squares) with a widening confidence band. Deliberately simple
   and inspectable rather than a black box.
2. `forecast_seasonal` Holt-Winters exponential smoothing (via
   statsmodels), which additionally models a repeating seasonal
   pattern (e.g. a December spike every year). Falls back to the
   linear method automatically if there isn't enough history to
   estimate a seasonal cycle.

Both always ship with a clear disclaimer the point is a defensible,
explainable baseline, not state-of-the-art accuracy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class ForecastError(Exception):
    pass


# Roughly how many periods make up one seasonal cycle, by resample frequency.
_SEASONAL_PERIOD = {"D": 7, "W": 52, "ME": 12}


def _resample_series(df: pd.DataFrame, date_col: str, metric_col: str, freq: str) -> pd.DataFrame:
    sub = df[[date_col, metric_col]].dropna().copy()
    if len(sub) < 3:
        raise ForecastError("Need at least 3 data points with valid dates to forecast.")
    sub = sub.sort_values(date_col)
    series = sub.set_index(date_col)[metric_col].resample(freq).sum().reset_index()
    series = series.dropna()
    if len(series) < 3:
        raise ForecastError("Not enough periods after resampling to fit a trend.")
    return series


def forecast_linear(df: pd.DataFrame, date_col: str, metric_col: str,
                     periods_ahead: int = 6, freq: str = "ME") -> dict:
    series = _resample_series(df, date_col, metric_col, freq)

    x = np.arange(len(series))
    y = series[metric_col].values.astype(float)

    # Ordinary least squares: y = slope*x + intercept
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    residuals = y - fitted
    resid_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0

    future_x = np.arange(len(series), len(series) + periods_ahead)
    future_y = slope * future_x + intercept

    # Widening confidence band: grows with distance from the known data.
    steps_ahead = future_x - (len(series) - 1)
    band = resid_std * np.sqrt(1 + steps_ahead / max(len(series), 1)) * 1.96

    future_dates = pd.date_range(
        start=series[date_col].iloc[-1], periods=periods_ahead + 1, freq=freq
    )[1:]

    history = series.rename(columns={metric_col: "value"})
    history["type"] = "actual"

    forecast = pd.DataFrame({
        date_col: future_dates,
        "value": future_y,
        "lower": future_y - band,
        "upper": future_y + band,
        "type": "forecast",
    })

    r2 = 1 - (np.sum(residuals ** 2) / np.sum((y - y.mean()) ** 2)) if np.sum((y - y.mean()) ** 2) > 0 else 0.0

    return {
        "method": "linear",
        "history": history,
        "forecast": forecast,
        "slope": float(slope),
        "r_squared": float(r2),
        "trend_direction": "upward" if slope > 0 else ("downward" if slope < 0 else "flat"),
        "avg_period_change": float(slope),
        "disclaimer": ("This is a linear-trend projection based on historical data, NOT a "
                        "guarantee of future performance. Confidence widens the further out "
                        "you look treat far-future points as directional, not precise."),
    }


def forecast_seasonal(df: pd.DataFrame, date_col: str, metric_col: str,
                       periods_ahead: int = 6, freq: str = "ME") -> dict:
    """Holt-Winters (triple exponential smoothing) forecast that models
    trend AND a repeating seasonal cycle. Needs at least two full
    seasonal cycles of history (e.g. 24 months for monthly data)
    raises ForecastError with a clear explanation otherwise, so the
    caller can fall back to `forecast_linear`."""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
    except ImportError as e:
        raise ForecastError(
            "Seasonal forecasting needs the 'statsmodels' package. Install it with "
            "`pip install statsmodels`, or use the Linear trend method instead."
        ) from e

    series = _resample_series(df, date_col, metric_col, freq)
    period = _SEASONAL_PERIOD.get(freq, 12)

    if len(series) < 2 * period:
        raise ForecastError(
            f"Seasonal forecasting needs at least {2 * period} periods of history at this "
            f"granularity to detect a repeating cycle (found {len(series)}). Try the Linear "
            "trend method, pick a coarser granularity, or upload more history."
        )

    y = series[metric_col].astype(float)
    y_index = pd.Series(y.values, index=series[date_col])

    try:
        model = ExponentialSmoothing(
            y_index, trend="add", seasonal="add", seasonal_periods=period,
            initialization_method="estimated",
        ).fit(optimized=True)
    except Exception as e:  # noqa: BLE001
        raise ForecastError(f"Could not fit a seasonal model to this series ({e}).") from e

    fitted = model.fittedvalues.values
    residuals = y.values - fitted
    resid_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0

    future_y = model.forecast(periods_ahead).values
    steps_ahead = np.arange(1, periods_ahead + 1)
    band = resid_std * np.sqrt(steps_ahead) * 1.96

    future_dates = pd.date_range(
        start=series[date_col].iloc[-1], periods=periods_ahead + 1, freq=freq
    )[1:]

    history = series.rename(columns={metric_col: "value"})
    history["type"] = "actual"

    forecast = pd.DataFrame({
        date_col: future_dates,
        "value": future_y,
        "lower": future_y - band,
        "upper": future_y + band,
        "type": "forecast",
    })

    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y.values - y.values.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    recent_slope = float(future_y[-1] - y.values[-period]) / period if len(y) >= period else float(future_y[-1] - y.values[-1])

    return {
        "method": "seasonal",
        "history": history,
        "forecast": forecast,
        "seasonal_period": period,
        "r_squared": float(r2),
        "trend_direction": "upward" if recent_slope > 0 else ("downward" if recent_slope < 0 else "flat"),
        "avg_period_change": recent_slope,
        "disclaimer": ("This is a Holt-Winters (trend + seasonality) projection based on "
                        "historical data, NOT a guarantee of future performance. It assumes the "
                        "seasonal pattern seen in your history repeats treat far-future points "
                        "as directional, not precise."),
    }


def decompose_seasonal(df: pd.DataFrame, date_col: str, metric_col: str, freq: str = "ME") -> dict:
    """Classical additive decomposition into trend / seasonal / residual
    components, for visual inspection of *why* a series looks seasonal
    before running a seasonal forecast on it."""
    try:
        from statsmodels.tsa.seasonal import seasonal_decompose
    except ImportError as e:
        raise ForecastError(
            "Seasonal decomposition needs the 'statsmodels' package. Install it with "
            "`pip install statsmodels`."
        ) from e

    series = _resample_series(df, date_col, metric_col, freq)
    period = _SEASONAL_PERIOD.get(freq, 12)
    if len(series) < 2 * period:
        raise ForecastError(
            f"Decomposition needs at least {2 * period} periods of history at this "
            f"granularity (found {len(series)})."
        )

    y_index = pd.Series(series[metric_col].astype(float).values, index=series[date_col])
    result = seasonal_decompose(y_index, model="additive", period=period, extrapolate_trend="period")

    out = pd.DataFrame({
        date_col: series[date_col],
        "observed": result.observed.values,
        "trend": result.trend.values,
        "seasonal": result.seasonal.values,
        "residual": result.resid.values,
    })
    return {"table": out, "period": period}
