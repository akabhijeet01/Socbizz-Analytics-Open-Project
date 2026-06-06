"""Post-pipeline result visualizations for presentation deck."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

import config

sns.set_theme(style="whitegrid")


def main() -> None:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    metrics = pd.read_csv(config.OUTPUTS_DIR / "evaluation_metrics.csv")
    timeline = pd.read_csv(config.OUTPUTS_DIR / "tariff_timeline_hourly.csv", parse_dates=["datetime"])
    fi = pd.read_csv(config.OUTPUTS_DIR / "feature_importance.csv")

    # Model metrics bar chart
    fig, ax = plt.subplots(figsize=(6, 4))
    m = metrics.iloc[0]
    vals = [m["demand_rmse"], m["demand_mae"], m["demand_r2"]]
    labels = ["RMSE", "MAE", "R²"]
    colors = ["#3498db", "#2ecc71", "#9b59b6"]
    ax.bar(labels, vals, color=colors)
    ax.set_title("Demand Prediction Metrics (UrbanEV)")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "demand_metrics.png", dpi=150)
    plt.close()

    # Tariff timeline
    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax1.plot(timeline["datetime"], timeline["avg_tariff_inr"], color="#e67e22", label="Tariff (INR/kWh)")
    ax1.axhline(config.BASELINE_TARIFF_INR, color="gray", ls="--", label="Baseline INR 15")
    ax1.set_ylabel("Tariff INR/kWh")
    ax2 = ax1.twinx()
    ax2.plot(timeline["datetime"], timeline["avg_predicted_util"], color="#2980b9", alpha=0.6, label="Pred. Util")
    ax1.set_title("Dynamic Tariff vs Predicted Utilization (Hourly)")
    ax1.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "tariff_timeline.png", dpi=150)
    plt.close()

    # Agent KPI dashboard
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    kpis = [
        ("Revenue Gain %", m["revenue_gain_pct"], "#27ae60"),
        ("Off-Peak Uplift %", m["off_peak_uplift_pct"], "#8e44ad"),
        ("Wait Reduction %", m["avg_wait_reduction_pct"], "#c0392b"),
        ("Customer Response %", m["customer_response_rate_pct"], "#16a085"),
        ("Util Before", m["utilization_before"], "#7f8c8d"),
        ("Util After", m["utilization_after"], "#2c3e50"),
    ]
    for ax, (title, val, color) in zip(axes.flat, kpis):
        ax.barh([title], [val], color=color)
        ax.set_xlim(min(0, val) - 1, max(val * 1.2, 1))
        ax.set_title(f"{title}: {val:.2f}")
    fig.suptitle("Monitoring Agent — Evaluation KPIs")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "monitoring_kpis.png", dpi=150)
    plt.close()

    # Feature importance
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=fi.head(10), y="feature", x="importance", ax=ax, palette="viridis")
    ax.set_title("Top Feature Importances (Permutation)")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "feature_importance.png", dpi=150)
    plt.close()

    print(f"Result figures saved to {config.FIGURES_DIR}")


if __name__ == "__main__":
    main()
