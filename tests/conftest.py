import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _generate_synthetic_orders(n: int = 600, seed: int = 42) -> pd.DataFrame:
    """Builds a synthetic orders DataFrame in memory, for tests only.

    Nothing here is written to disk or shipped with the app it exists
    purely so the test suite has a realistic, multi-column dataset to
    exercise forecasting, segmentation, and the query engine against.
    """
    rng = np.random.default_rng(seed)
    regions = ["North", "South", "East", "West", "Central"]

    dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 545, size=n), unit="D")
    region_arr = rng.choice(regions, size=n, p=[0.28, 0.22, 0.2, 0.18, 0.12])
    quantities = rng.integers(1, 12, size=n)

    unit_price = np.round(rng.uniform(8, 450, size=n), 2)
    discount_pct = rng.choice([0, 0, 0, 5, 10, 15, 20], size=n)
    revenue = np.round(unit_price * quantities * (1 - discount_pct / 100), 2)
    cost_ratio = rng.uniform(0.45, 0.75, size=n)

    month_arr = dates.month.to_numpy(dtype=float)
    revenue = revenue * (1 + 0.15 * np.sin(2 * np.pi * month_arr / 12))
    revenue = np.round(revenue, 2)
    profit = np.round(revenue * (1 - cost_ratio), 2)

    customer_ids = [f"CUST-{i:04d}" for i in rng.integers(1, 200, size=n)]

    df = pd.DataFrame({
        "order_date": dates,
        "customer_id": customer_ids,
        "region": region_arr,
        "quantity": quantities,
        "revenue": revenue,
        "profit": profit,
    })
    return df.sort_values("order_date").reset_index(drop=True)


@pytest.fixture
def sample_df():
    return _generate_synthetic_orders()


@pytest.fixture
def tiny_df():
    return pd.DataFrame({
        "region": ["North", "South", "North", "East", "South", "North"],
        "revenue": [100.0, 200.0, 150.0, None, 300.0, 120.0],
        "quantity": [1, 2, 1, 3, 2, 1],
        "order_date": pd.to_datetime(
            ["2024-01-01", "2024-01-05", "2024-02-01", "2024-02-15", "2024-03-01", "2024-03-10"]
        ),
    })
