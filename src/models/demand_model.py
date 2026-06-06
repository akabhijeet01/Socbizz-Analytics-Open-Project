"""
Demand prediction model for UrbanEV utilization forecasting.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

import config

FEATURE_COLS = [
    "hour",
    "day_of_week",
    "is_weekend",
    "month",
    "count",
    "fast_ratio",
    "CBD",
    "area",
    "price_cny",
    "volume_kwh",
    "util_lag_24",
    "util_lag_168",
    "util_roll_12",
    "util_roll_288",
    "congestion_proxy",
]

TARGET_COL = "utilization_next_hr"  # forecast next hour (no same-hour leakage)


@dataclass
class DemandModelMetrics:
    rmse: float
    mae: float
    r2: float
    n_train: int
    n_test: int


class DemandPredictor:
    def __init__(self):
        self.model = HistGradientBoostingRegressor(
            max_iter=200,
            max_depth=6,
            learning_rate=0.08,
            random_state=config.RANDOM_STATE,
        )
        self.feature_cols = FEATURE_COLS.copy()
        self.metrics: DemandModelMetrics | None = None

    def fit(self, df: pd.DataFrame) -> DemandModelMetrics:
        data = df.dropna(subset=self.feature_cols + [TARGET_COL])
        X = data[self.feature_cols]
        y = data[TARGET_COL]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE, shuffle=False
        )

        self.model.fit(X_train, y_train)
        preds = self.model.predict(X_test)
        preds = np.clip(preds, 0, 1)

        self.metrics = DemandModelMetrics(
            rmse=float(np.sqrt(mean_squared_error(y_test, preds))),
            mae=float(mean_absolute_error(y_test, preds)),
            r2=float(r2_score(y_test, preds)),
            n_train=len(X_train),
            n_test=len(X_test),
        )
        return self.metrics

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self.feature_cols].fillna(0)
        return np.clip(self.model.predict(X), 0, 1)

    def save(self, path: str | None = None) -> None:
        config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        path = path or str(config.MODELS_DIR / "demand_model.joblib")
        joblib.dump({"model": self.model, "feature_cols": self.feature_cols}, path)

    def feature_importance(self, X_sample: pd.DataFrame, y_sample: pd.Series) -> pd.DataFrame:
        from sklearn.inspection import permutation_importance

        result = permutation_importance(
            self.model, X_sample, y_sample, n_repeats=5, random_state=config.RANDOM_STATE, n_jobs=-1
        )
        imp = pd.DataFrame(
            {"feature": self.feature_cols, "importance": result.importances_mean}
        )
        return imp.sort_values("importance", ascending=False)
