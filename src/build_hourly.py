"""Rebuild hourly grid from existing 5-min panel (skip full re-melt)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import config

panel = pd.read_csv(config.DATA_PROCESSED / "urbanev_panel.csv", parse_dates=["datetime"])
panel["hour_key"] = panel["datetime"].dt.floor("h")
hourly_grid = (
    panel.groupby(["grid", "hour_key"])
    .agg(
        hour=("hour", "first"),
        day_of_week=("day_of_week", "first"),
        is_weekend=("is_weekend", "first"),
        month=("month", "first"),
        count=("count", "first"),
        fast_ratio=("fast_ratio", "first"),
        CBD=("CBD", "first"),
        area=("area", "first"),
        price_cny=("price_cny", "mean"),
        volume_kwh=("volume_kwh", "sum"),
        occupancy=("occupancy", "mean"),
        utilization_rate=("utilization_rate", "mean"),
        congestion_proxy=("congestion_proxy", "mean"),
    )
    .reset_index()
)
hourly_grid = hourly_grid.rename(columns={"hour_key": "datetime"})
hourly_grid = hourly_grid.sort_values(["grid", "datetime"]).reset_index(drop=True)
for lag in [1, 24, 168]:
    hourly_grid[f"util_lag_{lag}"] = hourly_grid.groupby("grid")["utilization_rate"].shift(lag)
hourly_grid["util_roll_12"] = hourly_grid.groupby("grid")["utilization_rate"].transform(
    lambda s: s.rolling(12, min_periods=1).mean()
)
hourly_grid["util_roll_288"] = hourly_grid.groupby("grid")["utilization_rate"].transform(
    lambda s: s.rolling(168, min_periods=1).mean()
)
hourly_grid["utilization_next_hr"] = hourly_grid.groupby("grid")["utilization_rate"].shift(-1)
hourly_grid = hourly_grid.dropna(subset=["util_lag_168", "utilization_next_hr"])
hourly_grid.to_csv(config.DATA_PROCESSED / "urbanev_hourly_grid.csv", index=False)
print(f"Saved {len(hourly_grid):,} rows")
