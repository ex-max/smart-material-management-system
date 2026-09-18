"""生成器与评估的冻结参数（M3）。

参数在 M3 开工时冻结并写入 ``ml/README.md``；每次实验的 ``config.json``
都会原样记录这里的数值，保证结果可复现。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

DEMAND_CLASSES = ("SMOOTH", "ERRATIC", "INTERMITTENT", "LUMPY")


@dataclass(frozen=True)
class GeneratorConfig:
    # --- 规模 ---
    seed: int = 1
    skus: int = 800
    warehouses: int = 1
    years: int = 3
    start_date: str = "2023-01-01"

    # --- 四象限目标占比（仅用于挑选参数；最终以实测 ADI/CV² 分类为准）---
    mix_smooth: float = 0.40
    mix_erratic: float = 0.25
    mix_intermittent: float = 0.25
    mix_lumpy: float = 0.10

    # --- Bernoulli–Gamma：出现概率 p + 需求量 Gamma 形状 k（CV² = 1/k）---
    intermittent_p: float = 0.45
    lumpy_p: float = 0.30
    shape_smooth: float = 30.0
    shape_erratic: float = 1.5
    shape_intermittent: float = 8.0
    shape_lumpy: float = 1.0

    # --- 基线需求（对数正态）与季节 / 周内 ---
    base_mean_log_sigma: float = 0.90
    seasonal_amplitude: float = 0.15
    weekday_amplitude: float = 0.45

    # --- 事件冲击（项目性突发）---
    event_prob: float = 0.25
    event_max_per_sku: int = 6
    event_multiplier: float = 2.5
    event_days: int = 7

    # --- 提前期（对数正态）---
    lt_mean_min: float = 3.0
    lt_mean_max: float = 15.0
    lt_log_sigma: float = 0.35
    lt_samples_per_year: int = 4

    # --- 价格与批次 ---
    price_log_mu: float = 0.0
    price_log_sigma: float = 1.0
    batch_managed_ratio: float = 0.30

    @property
    def n_days(self) -> int:
        return self.years * 365

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeneratorConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> "GeneratorConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class BacktestConfig:
    horizons: tuple[int, ...] = (7, 14, 30)
    initial_train_days: int = 180
    step_days: int = 7
    season_length: int = 7
    models: tuple[str, ...] = ("naive", "seasonal_naive", "ma7", "ma28", "ets")
    max_series: int = 200
    n_jobs: int = 4

    @property
    def max_horizon(self) -> int:
        return max(self.horizons)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["horizons"] = list(self.horizons)
        data["models"] = list(self.models)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BacktestConfig":
        data = dict(data)
        if "horizons" in data:
            data["horizons"] = tuple(data["horizons"])
        if "models" in data:
            data["models"] = tuple(data["models"])
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
