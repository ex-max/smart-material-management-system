"""LightGBM 面板级全局模型（跨 SKU 共享，滞后/滑动/日历特征）。

与 models.forecast 的单序列模型不同：LightGBM 在所有所选序列的监督样本上
训练一个全局模型，按 expanding-window rolling-origin 在每个 origin 重新训练，
再用递归多步方式预测 horizon 步（预测值回填为下一期的滞后特征）。

严格性：forecast 会先把 origin 之后的真实值置为 NaN，确保预测只用过去；
特征构造见 erp_ml.features。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .features import FeatureSpec, build_panel_training, build_row_features

# 固定超参（进入 config.json；答辩可解释）
DEFAULT_LGB_PARAMS: dict = {
    "objective": "regression",
    "metric": "l2",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbosity": -1,
    "deterministic": True,
    "force_col_wise": True,
    "num_threads": 2,
    "seed": 20240919,
}


@dataclass
class LGBMForecaster:
    """可复用的 LightGBM 面板预测器；每个 origin 训练一次。"""

    spec: FeatureSpec = field(default_factory=FeatureSpec)
    params: dict = field(default_factory=lambda: dict(DEFAULT_LGB_PARAMS))
    num_boost_round: int = 300

    def fit(self, history: np.ndarray, dates: pd.DatetimeIndex, origin: int) -> "LGBMForecaster":
        import lightgbm as lgb

        X, y, _, _, static = build_panel_training(history, dates, origin, self.spec)
        self.static_ = static
        dataset = lgb.Dataset(X, label=y, feature_name=self.spec.feature_names(), free_raw_data=True)
        self.booster_ = lgb.train(self.params, dataset, num_boost_round=self.num_boost_round)
        return self

    def forecast(
        self,
        history: np.ndarray,
        dates: pd.DatetimeIndex,
        origin: int,
        horizon: int,
    ) -> np.ndarray:
        history = np.asarray(history, dtype=float)
        work = history.copy()
        work[origin:] = np.nan  # 防未来信息泄漏
        n_series = work.shape[1]
        predictions = np.empty((horizon, n_series), dtype=float)
        for step in range(horizon):
            target = origin + step
            X = build_row_features(work, dates, self.spec, self.static_, target)
            y_hat = np.clip(np.asarray(self.booster_.predict(X), dtype=float), 0.0, None)
            work[target] = y_hat
            predictions[step] = y_hat
        return predictions
