#!/usr/bin/env python3
"""
Open Project 2026 — Agentic AI Dynamic Tariff Optimization Pipeline

Run: python main.py

Datasets:
  - UrbanEV (ST-EVCDP): demand prediction, utilization, off-peak uplift, wait proxy
  - ACN: revenue gain %, customer response, pricing efficiency
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import config
from src.preprocessing.acn_preprocess import load_and_preprocess_acn
from src.preprocessing.urbanev_preprocess import load_and_preprocess_urbanev
from src.models.demand_model import DemandPredictor
from src.agents.demand_tariff_agent import DemandTariffAgent
from src.agents.monitoring_agent import MonitoringAgent
from src.eda import run_eda


def main() -> None:
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Step 1: Preprocessing")
    print("=" * 60)
    pd = __import__("pandas")

    sessions_path = config.DATA_PROCESSED / "acn_sessions.csv"
    panel_path = config.DATA_PROCESSED / "urbanev_panel.csv"
    hourly_path = config.DATA_PROCESSED / "urbanev_hourly_grid.csv"

    if sessions_path.exists() and panel_path.exists() and hourly_path.exists():
        print("  Using cached processed data...")
        acn_sessions = pd.read_csv(sessions_path, parse_dates=["connectionTime", "disconnectTime", "doneChargingTime", "date"])
        urbanev_panel = pd.read_csv(panel_path, parse_dates=["datetime"], nrows=500_000)  # sample for EDA speed
        urbanev_hourly = pd.read_csv(hourly_path, parse_dates=["datetime"])
        acn_hourly = pd.read_csv(config.DATA_PROCESSED / "acn_hourly_demand.csv")
    else:
        acn_sessions = load_and_preprocess_acn()
        urbanev_panel = load_and_preprocess_urbanev()
        urbanev_hourly = pd.read_csv(hourly_path, parse_dates=["datetime"])
        acn_hourly = pd.read_csv(config.DATA_PROCESSED / "acn_hourly_demand.csv")
    print(f"  ACN sessions: {len(acn_sessions):,}")
    print(f"  UrbanEV 5-min rows: {len(urbanev_panel):,}")
    print(f"  UrbanEV hourly-grid rows: {len(urbanev_hourly):,}")

    print("\n" + "=" * 60)
    print("Step 2: Exploratory Data Analysis")
    print("=" * 60)
    run_eda(acn_sessions, urbanev_panel)
    print(f"  Figures saved to {config.FIGURES_DIR}")

    print("\n" + "=" * 60)
    print("Step 3: Demand Prediction (UrbanEV)")
    print("=" * 60)
    demand_model = DemandPredictor()
    metrics = demand_model.fit(urbanev_hourly)
    demand_model.save()
    from src.models.demand_model import TARGET_COL

    data = urbanev_hourly.dropna(subset=demand_model.feature_cols + [TARGET_COL])
    sample = data.sample(min(5000, len(data)), random_state=config.RANDOM_STATE)
    fi = demand_model.feature_importance(sample[demand_model.feature_cols], sample[TARGET_COL])
    fi.to_csv(config.OUTPUTS_DIR / "feature_importance.csv", index=False)
    print(f"  RMSE: {metrics.rmse:.4f}")
    print(f"  MAE:  {metrics.mae:.4f}")
    print(f"  R²:   {metrics.r2:.4f}")

    print("\n" + "=" * 60)
    print("Step 4: Demand + Tariff Agent")
    print("=" * 60)
    agent = DemandTariffAgent(demand_model=demand_model)

    # Price on test slice (last 20% chronologically) for realistic eval
    urbanev_hourly = urbanev_hourly.sort_values("datetime")
    split_idx = int(len(urbanev_hourly) * (1 - config.TEST_SIZE))
    eval_panel = urbanev_hourly.iloc[split_idx:].copy()

    priced = agent.predict_and_price(eval_panel)
    priced.to_csv(config.OUTPUTS_DIR / "tariff_recommendations.csv", index=False)

    acn_sim = agent.simulate_acn_revenue(acn_hourly)
    acn_sim.to_csv(config.OUTPUTS_DIR / "acn_revenue_simulation.csv", index=False)

    signal_counts = priced["pricing_signal"].value_counts()
    print(f"  Pricing signals: {signal_counts.to_dict()}")
    print(f"  Avg recommended tariff: ₹{priced['recommended_tariff_inr'].mean():.2f}/kWh")

    print("\n" + "=" * 60)
    print("Step 5: Monitoring & Learning Agent")
    print("=" * 60)
    monitor = MonitoringAgent()
    report = monitor.evaluate(
        priced,
        acn_sim,
        demand_metrics={"rmse": metrics.rmse, "mae": metrics.mae, "r2": metrics.r2},
    )
    feedback = monitor.learn(report)

    # Save all metrics
    metrics_df = __import__("pandas").DataFrame([report.to_dict()])
    metrics_df.to_csv(config.OUTPUTS_DIR / "evaluation_metrics.csv", index=False)

    with open(config.OUTPUTS_DIR / "monitoring_feedback.json", "w") as f:
        json.dump(feedback, f, indent=2)

    # Tariff timeline sample for presentation
    timeline = (
        priced.groupby(priced["datetime"].dt.floor("h"))
        .agg(
            avg_predicted_util=("predicted_utilization", "mean"),
            avg_tariff_inr=("recommended_tariff_inr", "mean"),
            avg_actual_util=("utilization_rate", "mean"),
        )
        .reset_index()
    )
    timeline.to_csv(config.OUTPUTS_DIR / "tariff_timeline_hourly.csv", index=False)

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Demand Prediction (UrbanEV)")
    print(f"    RMSE: {report.demand_rmse:.4f}  MAE: {report.demand_mae:.4f}  R²: {report.demand_r2:.4f}")
    print(f"  Tariff Pricing (ACN simulation)")
    print(f"    Revenue Gain %: {report.revenue_gain_pct:+.2f}%")
    print(f"    Customer Response Rate: {report.customer_response_rate_pct:+.2f}%")
    print(f"    Pricing Efficiency: {report.pricing_efficiency_baseline:.2f} → {report.pricing_efficiency_dynamic:.2f} INR/kWh")
    print(f"  Operations (UrbanEV)")
    print(f"    Utilization: {report.utilization_before:.3f} → {report.utilization_after:.3f}")
    print(f"    Off-Peak Uplift: {report.off_peak_uplift_pct:+.2f}%")
    print(f"    Avg Wait Reduction (proxy): {report.avg_wait_reduction_pct:+.2f}%")
    print(f"  Learning feedback: {feedback['action']}")
    from src.visualize_results import main as visualize_results

    visualize_results()
    print(f"\nOutputs written to {config.OUTPUTS_DIR}/")


if __name__ == "__main__":
    main()
