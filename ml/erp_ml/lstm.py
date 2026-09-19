"""LSTM 面板级全局模型（PyTorch CPU），与 LightGBM 共用 rolling-origin 协议。

设计对齐 erp_ml.gbm.LGBMForecaster 的接口，因此可以直接复用
erp_ml.backtest.backtest_global：

- fit(history, dates, origin)：只用 history[:origin] 构造滑动窗口，
  逐序列做 log1p + 标准化（均值/方差只用历史，杜绝未来信息），训练一个跨序列共享的小 LSTM；
- forecast(history, dates, origin, horizon)：递归多步（预测回填为下一期输入），
  预测值反标准化并 clip 到 >= 0；
- 确定性：固定 torch 手动种子 + 固定线程数，重复运行结果一致。

依赖：torch 仅作为 ml 的可选依赖（pip install -e ".[lstm]" 或 make ml-lstm，
用 CPU 轮子），未安装时给出明确提示。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# 固定超参（进入 config.json；答辩可解释；窗口上限用于控制每 origin 训练成本）
DEFAULT_LSTM_PARAMS: dict = {
    "lookback": 28,
    "hidden_size": 16,
    "num_layers": 1,
    "epochs": 8,
    "batch_size": 512,
    "learning_rate": 0.01,
    "weight_decay": 1e-4,
    "grad_clip": 1.0,
    "windows_per_series": 150,
    "num_threads": 2,
    "seed": 20240919,
}


@dataclass
class LSTMForecaster:
    """可复用的 LSTM 面板预测器；每个 origin 从零训练一次。"""

    lookback: int = 28
    hidden_size: int = 16
    num_layers: int = 1
    epochs: int = 8
    batch_size: int = 512
    learning_rate: float = 0.01
    weight_decay: float = 1e-4
    grad_clip: float = 1.0
    windows_per_series: int = 150
    num_threads: int = 2
    seed: int = 20240919

    def _require_torch(self):
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - 环境相关
            raise RuntimeError(
                "未安装 torch。LSTM 实验为可选依赖，请先运行 make ml-lstm（CPU 轮子）"
            ) from exc
        return torch

    def fit(self, history: np.ndarray, dates: pd.DatetimeIndex, origin: int) -> "LSTMForecaster":
        torch = self._require_torch()
        from torch import nn

        torch.manual_seed(self.seed)
        torch.set_num_threads(self.num_threads)

        hist = np.asarray(history, dtype=float)[:origin]
        log_hist = np.log1p(np.clip(hist, 0.0, None))
        mu = log_hist.mean(axis=0)
        sigma = log_hist.std(axis=0)
        sigma = np.where(sigma < 1e-6, 1.0, sigma)
        self.mu_ = mu
        self.sigma_ = sigma
        z = (log_hist - mu) / sigma

        lookback = self.lookback
        windows: list[np.ndarray] = []
        targets: list[np.ndarray] = []
        for j in range(z.shape[1]):
            series = z[:, j]
            if series.size <= lookback:
                continue
            sw = np.lib.stride_tricks.sliding_window_view(series, lookback)[: series.size - lookback]
            target = series[lookback:]
            if sw.shape[0] > self.windows_per_series:
                sw = sw[-self.windows_per_series :]
                target = target[-self.windows_per_series :]
            windows.append(sw)
            targets.append(target)
        if not windows:
            raise ValueError("可训练窗口为空：origin 太小或序列太短")

        x = np.concatenate(windows, axis=0)[:, :, None].astype(np.float32)
        y = np.concatenate(targets, axis=0).astype(np.float32)[:, None]
        x_t = torch.from_numpy(x)
        y_t = torch.from_numpy(y)

        model = nn.LSTM(input_size=1, hidden_size=self.hidden_size, num_layers=self.num_layers, batch_first=True)
        head = nn.Linear(self.hidden_size, 1)
        params = list(model.parameters()) + list(head.parameters())
        optimizer = torch.optim.Adam(params, lr=self.learning_rate, weight_decay=self.weight_decay)
        loss_fn = nn.MSELoss()
        generator = torch.Generator().manual_seed(self.seed)

        n = x_t.shape[0]
        for _ in range(self.epochs):
            permutation = torch.randperm(n, generator=generator)
            model.train()
            for start in range(0, n, self.batch_size):
                idx = permutation[start : start + self.batch_size]
                optimizer.zero_grad()
                out, _ = model(x_t[idx])
                prediction = head(out[:, -1, :])
                loss = loss_fn(prediction, y_t[idx])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(params, self.grad_clip)
                optimizer.step()

        self.model_ = model
        self.head_ = head
        return self

    def forecast(
        self,
        history: np.ndarray,
        dates: pd.DatetimeIndex,
        origin: int,
        horizon: int,
    ) -> np.ndarray:
        torch = self._require_torch()

        hist = np.asarray(history, dtype=float)[:origin]
        log_hist = np.log1p(np.clip(hist, 0.0, None))
        z = (log_hist - self.mu_) / self.sigma_
        z_window = z[-self.lookback :].T.copy()  # (n_series, lookback)
        n_series = z_window.shape[0]
        predictions = np.empty((horizon, n_series), dtype=float)

        self.model_.eval()
        with torch.no_grad():
            for step in range(horizon):
                x = torch.from_numpy(z_window[:, :, None].astype(np.float32))
                out, _ = self.model_(x)
                pred_z = self.head_(out[:, -1, :]).numpy().reshape(-1)
                raw = np.clip(pred_z * self.sigma_ + self.mu_, 0.0, 20.0)
                prediction = np.expm1(raw)
                predictions[step] = prediction
                z_window = np.concatenate([z_window[:, 1:], pred_z[:, None]], axis=1)
        return predictions
