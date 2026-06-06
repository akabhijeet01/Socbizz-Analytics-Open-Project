"""
UrbanEV (ST-EVCDP) preprocessing — Shenzhen district-level 5-min data.

Feature rationale:
- occupancy / count → utilization rate (primary demand target).
- volume → energy throughput; correlates with revenue potential.
- price → existing market price signal (CNY/kWh proxy); anchor for elasticity.
- hour, day_of_week, is_weekend → strong intraday/weekly seasonality.
- fast_count, slow_count, CBD → station mix and land-use effects on demand.
- lag and rolling occupancy → short-term persistence for forecasting.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

import config


def _melt_wide(csv_path: Path, value_name: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    id_col = "timestamp"
    long = df.melt(id_vars=[id_col], var_name="grid", value_name=value_name)
    long["grid"] = long["grid"].astype(int)
    return long


def load_and_preprocess_urbanev(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or config.URBANEV_DIR

    time_df = pd.read_csv(data_dir / "time.csv")
    info_df = pd.read_csv(data_dir / "information.csv")

    occ = _melt_wide(data_dir / "occupancy.csv", "occupancy")
    vol = _melt_wide(data_dir / "volume.csv", "volume_kwh")
    price = _melt_wide(data_dir / "price.csv", "price_cny")

    time_df = time_df.reset_index(drop=True)
    time_df["timestamp"] = time_df.index + 1
    merged = (
        occ.merge(vol, on=["timestamp", "grid"])
        .merge(price, on=["timestamp", "grid"])
        .merge(time_df, on="timestamp")
    )

    merged = merged.merge(
        info_df[["grid", "count", "fast_count", "slow_count", "area", "CBD", "dynamic_pricing"]],
        on="grid",
        how="left",
    )

    merged["datetime"] = pd.to_datetime(
        dict(year=merged["year"], month=merged["month"], day=merged["day"],
             hour=merged["hour"], minute=merged["minute"])
    )

    merged["utilization_rate"] = (merged["occupancy"] / merged["count"].clip(lower=1)).clip(0, 1.5)
    merged["utilization_rate"] = merged["utilization_rate"].clip(0, 1)

    merged["day_of_week"] = merged["datetime"].dt.dayofweek
    merged["is_weekend"] = (merged["day_of_week"] >= 5).astype(int)
    merged["fast_ratio"] = merged["fast_count"] / merged["count"].clip(lower=1)

    # Queue / wait proxy: high occupancy relative to capacity
    merged["congestion_proxy"] = (merged["occupancy"] / merged["count"].clip(lower=1)).clip(0, 2)

    # Sort for lag features
    merged = merged.sort_values(["grid", "timestamp"]).reset_index(drop=True)

    for lag in [1, 12, 288]:  # 5min, 1hr, 24hr
        merged[f"util_lag_{lag}"] = merged.groupby("grid")["utilization_rate"].shift(lag)

    merged["util_roll_12"] = (
        merged.groupby("grid")["utilization_rate"]
        .transform(lambda s: s.rolling(12, min_periods=1).mean())
    )
    merged["util_roll_288"] = (
        merged.groupby("grid")["utilization_rate"]
        .transform(lambda s: s.rolling(288, min_periods=1).mean())
    )

    merged = merged.dropna(subset=["util_lag_288"])

    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    merged.to_csv(config.DATA_PROCESSED / "urbanev_panel.csv", index=False)

    # City-level hourly aggregate for EDA
    hourly_city = (
        merged.groupby(["datetime"])
        .agg(
            avg_utilization=("utilization_rate", "mean"),
            total_occupancy=("occupancy", "sum"),
            total_volume_kwh=("volume_kwh", "sum"),
            avg_price_cny=("price_cny", "mean"),
            n_grids=("grid", "nunique"),
        )
        .reset_index()
    )
    hourly_city.to_csv(config.DATA_PROCESSED / "urbanev_city_hourly.csv", index=False)

    # Hourly per-grid aggregate — primary modeling table for demand + tariff
    merged["hour_key"] = merged["datetime"].dt.floor("h")
    hourly_grid = (
        merged.groupby(["grid", "hour_key"])
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

    for lag in [1, 24, 168]:  # 1h, 24h, 7d
        hourly_grid[f"util_lag_{lag}"] = hourly_grid.groupby("grid")["utilization_rate"].shift(lag)
    hourly_grid["util_roll_12"] = (
        hourly_grid.groupby("grid")["utilization_rate"]
        .transform(lambda s: s.rolling(12, min_periods=1).mean())
    )
    hourly_grid["util_roll_288"] = (
        hourly_grid.groupby("grid")["utilization_rate"]
        .transform(lambda s: s.rolling(168, min_periods=1).mean())
    )
    hourly_grid["utilization_next_hr"] = hourly_grid.groupby("grid")["utilization_rate"].shift(-1)
    hourly_grid = hourly_grid.dropna(subset=["util_lag_168", "utilization_next_hr"])
    hourly_grid.to_csv(config.DATA_PROCESSED / "urbanev_hourly_grid.csv", index=False)

    return merged
