"""
Monitoring & Learning Agent — evaluates pricing decisions and feeds back metrics.

Metrics by dataset (per problem mapping):
- Avg Waiting Time Reduction: UrbanEV congestion_proxy before/after (proxy)
- Customer Response Rate: ACN session volume shift from elasticity model
- Pricing Efficiency Score: ACN revenue per kWh delivered
- Charger Utilization Rate: UrbanEV utilization before/after
- Off-Peak Uplift: UrbanEV sessions in low-util slots after discounts
- Revenue Gain %: ACN dynamic vs baseline revenue
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json

import numpy as np
import pandas as pd

import config


@dataclass
class MonitoringReport:
    # Demand prediction (UrbanEV)
    demand_rmse: float
    demand_mae: float
    demand_r2: float

    # Tariff / operations
    revenue_gain_pct: float
    utilization_before: float
    utilization_after: float
    off_peak_uplift_pct: float
    avg_wait_reduction_pct: float
    customer_response_rate_pct: float
    pricing_efficiency_baseline: float
    pricing_efficiency_dynamic: float
    pricing_efficiency_improvement_pct: float

    def to_dict(self) -> dict:
        return asdict(self)


class MonitoringAgent:
    def __init__(self, learning_rate: float = 0.05):
        self.learning_rate = learning_rate
        self.history: list[MonitoringReport] = []
        # Adaptive threshold offsets learned from feedback
        self.surge_offset = 0.0
        self.discount_offset = 0.0

    def evaluate(
        self,
        urbanev_priced: pd.DataFrame,
        acn_simulated: pd.DataFrame,
        demand_metrics: dict,
    ) -> MonitoringReport:
        # Utilization: simulate demand shift from pricing on UrbanEV
        util_before = float(urbanev_priced["utilization_rate"].mean())

        price_ratio = (
            urbanev_priced["recommended_tariff_inr"] / config.BASELINE_TARIFF_INR
        )
        demand_mult = np.power(price_ratio, config.PRICE_ELASTICITY)
        util_after = float(
            (urbanev_priced["utilization_rate"] * demand_mult).clip(0, 1).mean()
        )

        # Off-peak uplift: low-util slots (<35%) session volume change
        off_peak_mask = urbanev_priced["utilization_rate"] < config.DISCOUNT_UTIL_THRESHOLD
        if off_peak_mask.any():
            base_vol = urbanev_priced.loc[off_peak_mask, "volume_kwh"].sum()
            new_vol = (
                urbanev_priced.loc[off_peak_mask, "volume_kwh"] * demand_mult[off_peak_mask]
            ).sum()
            off_peak_uplift = ((new_vol - base_vol) / base_vol * 100) if base_vol > 0 else 0.0
        else:
            off_peak_uplift = 0.0

        # Wait time proxy: congestion_proxy reduction in peak (util > 75%)
        peak_mask = urbanev_priced["utilization_rate"] >= config.SURGE_UTIL_THRESHOLD
        if peak_mask.any():
            wait_before = float(urbanev_priced.loc[peak_mask, "congestion_proxy"].mean())
            wait_after = float(
                (urbanev_priced.loc[peak_mask, "congestion_proxy"] * demand_mult[peak_mask]).mean()
            )
            wait_reduction = ((wait_before - wait_after) / wait_before * 100) if wait_before > 0 else 0.0
        else:
            wait_reduction = 0.0

        # ACN revenue & customer response
        base_rev = float(acn_simulated["revenue_baseline_inr"].sum())
        dyn_rev = float(acn_simulated["revenue_dynamic_inr"].sum())
        revenue_gain = ((dyn_rev - base_rev) / base_rev * 100) if base_rev > 0 else 0.0

        base_sessions = float(acn_simulated["sessions"].sum())
        dyn_sessions = float(acn_simulated["sessions_dynamic"].sum())
        customer_response = ((dyn_sessions - base_sessions) / base_sessions * 100) if base_sessions > 0 else 0.0

        base_kwh = float(acn_simulated["total_kwh"].sum())
        eff_baseline = base_rev / base_kwh if base_kwh > 0 else 0.0
        dyn_kwh = float(acn_simulated["kwh_dynamic"].sum())
        eff_dynamic = dyn_rev / dyn_kwh if dyn_kwh > 0 else 0.0
        eff_improvement = (
            ((eff_dynamic - eff_baseline) / eff_baseline * 100) if eff_baseline > 0 else 0.0
        )

        report = MonitoringReport(
            demand_rmse=demand_metrics["rmse"],
            demand_mae=demand_metrics["mae"],
            demand_r2=demand_metrics["r2"],
            revenue_gain_pct=float(revenue_gain),
            utilization_before=util_before,
            utilization_after=util_after,
            off_peak_uplift_pct=float(off_peak_uplift),
            avg_wait_reduction_pct=float(wait_reduction),
            customer_response_rate_pct=float(customer_response),
            pricing_efficiency_baseline=float(eff_baseline),
            pricing_efficiency_dynamic=float(eff_dynamic),
            pricing_efficiency_improvement_pct=float(eff_improvement),
        )
        self.history.append(report)
        return report

    def learn(self, report: MonitoringReport) -> dict:
        """
        Simple feedback: if revenue gain negative, loosen surge / deepen discount slightly.
        Returns updated threshold suggestions (not applied automatically in v1).
        """
        feedback = {}
        if report.revenue_gain_pct < 0:
            self.surge_offset += self.learning_rate * 0.05
            self.discount_offset -= self.learning_rate * 0.05
            feedback["action"] = "loosen_surge_deepen_discount"
        elif report.off_peak_uplift_pct < 5:
            self.discount_offset -= self.learning_rate * 0.02
            feedback["action"] = "increase_off_peak_discount"
        else:
            feedback["action"] = "hold"

        feedback["surge_threshold_suggestion"] = config.SURGE_UTIL_THRESHOLD + self.surge_offset
        feedback["discount_threshold_suggestion"] = config.DISCOUNT_UTIL_THRESHOLD + self.discount_offset
        return feedback
