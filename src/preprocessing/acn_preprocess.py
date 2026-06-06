"""
ACN (Adaptive Charging Network) preprocessing.

Feature rationale:
- connectionTime / disconnectTime: define session window and duration; core for temporal demand.
- kWhDelivered: revenue and energy proxy; used for pricing efficiency.
- stationID / siteID: spatial heterogeneity in utilization.
- doneChargingTime: idle occupancy after charge completes (congestion proxy).
- minutesAvailable: user flexibility; longer windows imply lower urgency.
- clusterID: workplace cluster grouping for demand patterns.
We exclude sparse columns (_meta, userInputs, paymentRequired) with >90% missing.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

import config


def load_and_preprocess_acn(path: Path | None = None) -> pd.DataFrame:
    path = path or config.ACN_XLSX
    df = pd.read_excel(path)

    # Drop fully empty metadata columns
    drop_cols = [c for c in df.columns if df[c].isna().all()]
    df = df.drop(columns=drop_cols, errors="ignore")

    # Parse timestamps
    for col in ["connectionTime", "disconnectTime", "doneChargingTime"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    df = df.dropna(subset=["connectionTime", "disconnectTime", "kWhDelivered"])
    df = df[df["kWhDelivered"] > 0]

    # Session duration (hours)
    df["session_duration_hr"] = (
        (df["disconnectTime"] - df["connectionTime"]).dt.total_seconds() / 3600
    )
    df = df[(df["session_duration_hr"] > 0) & (df["session_duration_hr"] < 48)]

    # Charging vs idle time
    if "doneChargingTime" in df.columns:
        df["charging_duration_hr"] = (
            (df["doneChargingTime"] - df["connectionTime"]).dt.total_seconds() / 3600
        ).clip(lower=0)
        df["idle_duration_hr"] = (
            (df["disconnectTime"] - df["doneChargingTime"]).dt.total_seconds() / 3600
        ).clip(lower=0)
    else:
        df["charging_duration_hr"] = df["session_duration_hr"]
        df["idle_duration_hr"] = 0.0

    # Temporal features
    df["hour"] = df["connectionTime"].dt.hour
    df["day_of_week"] = df["connectionTime"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["month"] = df["connectionTime"].dt.month
    df["date"] = df["connectionTime"].dt.floor("D")

    # Revenue at baseline tariff
    df["revenue_baseline_inr"] = df["kWhDelivered"] * config.BASELINE_TARIFF_INR
    df["revenue_per_kwh"] = config.BASELINE_TARIFF_INR

    # Aggregate hourly demand by site for elasticity / tariff simulation
    hourly = (
        df.groupby(["siteID", "date", "hour"])
        .agg(
            sessions=("sessionID", "count"),
            total_kwh=("kWhDelivered", "sum"),
            avg_duration_hr=("session_duration_hr", "mean"),
            avg_idle_hr=("idle_duration_hr", "mean"),
            revenue_baseline=("revenue_baseline_inr", "sum"),
        )
        .reset_index()
    )
    hourly["utilization_proxy"] = (
        hourly["sessions"] / hourly["sessions"].groupby([hourly["siteID"], hourly["date"]]).transform("max").clip(lower=1)
    ).clip(0, 1)

    # Save session-level and hourly aggregates
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.DATA_PROCESSED / "acn_sessions.csv", index=False)
    hourly.to_csv(config.DATA_PROCESSED / "acn_hourly_demand.csv", index=False)

    return df
