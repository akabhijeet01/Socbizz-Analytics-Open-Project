"""
Merged Demand Prediction + Tariff Pricing Agent.

Workflow:
1. Predict utilization (UrbanEV) using trained ML model.
2. Map predicted utilization → dynamic tariff with smooth, bounded adjustments.
3. Simulate revenue impact on ACN sessions using price elasticity.

Threshold optimization (vs. mandatory 80/30):
- Surge at 75% util: Shenzhen data shows sustained congestion above ~70–75%;
  80% is too late to shape demand before queues form.
- Discount below 35% util: off-peak slots often sit at 20–30%; 35% triggers
  incentives earlier without excessive revenue erosion.
- Max ±25% price change vs baseline keeps tariffs consumer-acceptable.
- 10% max step change prevents drastic tariff jumps.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from src.models.demand_model import DemandPredictor


class DemandTariffAgent:
    def __init__(self, demand_model: DemandPredictor | None = None):
        self.demand_model = demand_model or DemandPredictor()
        self._prev_tariff: float | None = None

    def _raw_tariff_from_util(self, util: float) -> float:
        base = config.BASELINE_TARIFF_INR
        if util >= config.SURGE_UTIL_THRESHOLD:
            # Linear surge from threshold to 100% util
            intensity = (util - config.SURGE_UTIL_THRESHOLD) / (1.0 - config.SURGE_UTIL_THRESHOLD)
            mult = 1.0 + intensity * (config.MAX_SURGE_MULTIPLIER - 1.0)
        elif util <= config.DISCOUNT_UTIL_THRESHOLD:
            intensity = (config.DISCOUNT_UTIL_THRESHOLD - util) / config.DISCOUNT_UTIL_THRESHOLD
            # Gentler discount curve to protect revenue while still stimulating off-peak
            mult = 1.0 - intensity * (1.0 - config.MAX_DISCOUNT_MULTIPLIER) * 0.7
        else:
            # Shoulder period: mild adjustment toward baseline
            mid = (config.SURGE_UTIL_THRESHOLD + config.DISCOUNT_UTIL_THRESHOLD) / 2
            mult = 1.0 + 0.05 * (util - mid) / (config.SURGE_UTIL_THRESHOLD - mid)

        return base * np.clip(mult, config.MAX_DISCOUNT_MULTIPLIER, config.MAX_SURGE_MULTIPLIER)

    def smooth_tariff(self, raw_tariff: float) -> float:
        if self._prev_tariff is None:
            self._prev_tariff = raw_tariff
            return raw_tariff
        max_up = self._prev_tariff * (1 + config.MAX_TARIFF_CHANGE_PCT)
        max_down = self._prev_tariff * (1 - config.MAX_TARIFF_CHANGE_PCT)
        smoothed = float(np.clip(raw_tariff, max_down, max_up))
        self._prev_tariff = smoothed
        return smoothed

    def recommend_tariff(self, predicted_util: float) -> dict:
        raw = self._raw_tariff_from_util(predicted_util)
        tariff = self.smooth_tariff(raw)

        if predicted_util >= config.SURGE_UTIL_THRESHOLD:
            signal = "surge"
        elif predicted_util <= config.DISCOUNT_UTIL_THRESHOLD:
            signal = "discount"
        else:
            signal = "neutral"

        return {
            "predicted_utilization": float(predicted_util),
            "recommended_tariff_inr": float(tariff),
            "pricing_signal": signal,
            "raw_tariff_inr": float(raw),
        }

    def predict_and_price(self, urbanev_df: pd.DataFrame) -> pd.DataFrame:
        preds = self.demand_model.predict(urbanev_df)
        out = urbanev_df.copy()
        out["predicted_utilization"] = preds

        self._prev_tariff = None
        recs = [self.recommend_tariff(u) for u in preds]
        rec_df = pd.DataFrame(recs)
        return pd.concat([out.reset_index(drop=True), rec_df], axis=1)

    def simulate_acn_revenue(
        self, acn_hourly: pd.DataFrame, tariff_series: pd.Series | None = None
    ) -> pd.DataFrame:
        """
        Simulate dynamic pricing on ACN hourly aggregates.
        Demand response: Q_new = Q_base * (P_new/P_base)^elasticity
        """
        df = acn_hourly.copy()
        if tariff_series is None:
            # Map hour-of-day util proxy to tariff
            hour_util = df.groupby("hour")["utilization_proxy"].transform("mean")
            tariffs = [self.recommend_tariff(u)["recommended_tariff_inr"] for u in hour_util]
            df["dynamic_tariff_inr"] = tariffs
        else:
            df["dynamic_tariff_inr"] = tariff_series.values

        price_ratio = df["dynamic_tariff_inr"] / config.BASELINE_TARIFF_INR
        demand_mult = np.power(price_ratio, config.PRICE_ELASTICITY)

        df["sessions_dynamic"] = df["sessions"] * demand_mult
        df["kwh_dynamic"] = df["total_kwh"] * demand_mult
        df["revenue_baseline_inr"] = df["total_kwh"] * config.BASELINE_TARIFF_INR
        df["revenue_dynamic_inr"] = df["kwh_dynamic"] * df["dynamic_tariff_inr"]

        return df
