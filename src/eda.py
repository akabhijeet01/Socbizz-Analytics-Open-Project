"""Exploratory data analysis and insight-driven visualizations."""
from __future__ import annotations

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

import config

sns.set_theme(style="whitegrid", palette="muted")


def run_eda(acn_sessions: pd.DataFrame, urbanev_panel: pd.DataFrame) -> None:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. ACN hourly demand pattern
    hourly = acn_sessions.groupby("hour")["kWhDelivered"].sum().reset_index()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(hourly["hour"], hourly["kWhDelivered"], color="steelblue", alpha=0.85)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Total kWh Delivered")
    ax.set_title("ACN: Intraday Energy Demand (Workplace Charging)")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "acn_hourly_demand.png", dpi=150)
    plt.close()

    # 2. ACN weekday vs weekend
    wd = acn_sessions.groupby("is_weekend")["kWhDelivered"].mean()
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(["Weekday", "Weekend"], [wd.get(0, 0), wd.get(1, 0)], color=["#2ecc71", "#e74c3c"])
    ax.set_ylabel("Avg kWh per Session")
    ax.set_title("ACN: Session Energy by Day Type")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "acn_weekday_weekend.png", dpi=150)
    plt.close()

    # 3. UrbanEV city-level utilization heatmap by hour x day
    city = pd.read_csv(config.DATA_PROCESSED / "urbanev_city_hourly.csv", parse_dates=["datetime"])
    city["hour"] = city["datetime"].dt.hour
    city["dow"] = city["datetime"].dt.dayofweek
    pivot = city.pivot_table(values="avg_utilization", index="dow", columns="hour", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(14, 4))
    sns.heatmap(pivot, ax=ax, cmap="YlOrRd", vmin=0, vmax=0.8)
    ax.set_title("UrbanEV: Avg Utilization by Day-of-Week × Hour")
    ax.set_ylabel("Day of Week (0=Mon)")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "urbanev_util_heatmap.png", dpi=150)
    plt.close()

    # 4. Utilization distribution — informs threshold choice
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.histplot(urbanev_panel["utilization_rate"], bins=50, kde=True, ax=ax)
    ax.axvline(config.SURGE_UTIL_THRESHOLD, color="red", ls="--", label=f"Surge @ {config.SURGE_UTIL_THRESHOLD}")
    ax.axvline(config.DISCOUNT_UTIL_THRESHOLD, color="green", ls="--", label=f"Discount @ {config.DISCOUNT_UTIL_THRESHOLD}")
    ax.set_xlabel("Utilization Rate")
    ax.set_title("UrbanEV: Utilization Distribution & Pricing Thresholds")
    ax.legend()
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "urbanev_util_distribution.png", dpi=150)
    plt.close()

    # 5. Price vs utilization scatter (sample)
    sample = urbanev_panel.sample(min(5000, len(urbanev_panel)), random_state=42)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(sample["utilization_rate"], sample["price_cny"], alpha=0.3, s=8)
    ax.set_xlabel("Utilization Rate")
    ax.set_ylabel("Price (CNY/kWh)")
    ax.set_title("UrbanEV: Price vs Utilization (sample)")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "urbanev_price_vs_util.png", dpi=150)
    plt.close()

    # Summary stats CSV
    summary = pd.DataFrame(
        {
            "metric": [
                "acn_sessions",
                "acn_avg_kwh",
                "acn_avg_duration_hr",
                "urbanev_rows",
                "urbanev_avg_util",
                "urbanev_grids",
            ],
            "value": [
                len(acn_sessions),
                acn_sessions["kWhDelivered"].mean(),
                acn_sessions["session_duration_hr"].mean(),
                len(urbanev_panel),
                urbanev_panel["utilization_rate"].mean(),
                urbanev_panel["grid"].nunique(),
            ],
        }
    )
    summary.to_csv(config.OUTPUTS_DIR / "eda_summary.csv", index=False)
