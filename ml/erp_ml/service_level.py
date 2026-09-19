"""服务水平口径（M5 定稿，全程一致）。

**主口径：CSL（Cycle Service Level，周期服务水平）**

- 定义：一个订货周期内不发生缺货的概率；等价于以 `z = Φ⁻¹(CSL)` 的
  正态分位数推导安全库存。
- 安全库存（含需求与提前期双波动）：

      SS = z · sqrt( LT · σD² + D̂² · σLT² )

  其中 `LT` 为提前期均值、`σD` 为日需求标准差、`D̂` 为预测日均需求、
  `σLT` 为提前期标准差。
- 再订货点：`ROP = D̂ · LT + SS`。

**对比口径：Fill Rate（β 满足率）** = 需求被即时满足的比例。它取决于订货批量与
缺货量，不是上面 SS 闭式解的输入；因此本实验把 Fill Rate 作为**仿真输出指标**
报告与讨论，而不作为目标口径。

单一事实来源：数据库 `replenishment_policy.service_level_type ∈ {'CSL','FILL_RATE'}`；
M5 全部策略固定落 `'CSL'`，并写入每次实验的 `config.json`（字段名 `service_level_type`），
保证"论文里选一个并全程一致"。
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import norm

# 允许的 service_level_type 取值（与 db-schema §12.5 CHECK 约束一致）
CSL = "CSL"
FILL_RATE = "FILL_RATE"
SERVICE_LEVEL_TYPES = (CSL, FILL_RATE)

# M5 定稿：主口径固定为 CSL
SERVICE_LEVEL_TYPE = CSL
DEFAULT_SERVICE_LEVEL = 0.95


def z_for_csl(service_level: float) -> float:
    """目标 CSL -> 正态分位数 z（如 0.95 -> 1.6449）。"""
    level = float(service_level)
    if not 0.0 < level < 1.0:
        raise ValueError(f"CSL 服务水平必须在 (0, 1) 内，收到 {service_level}")
    return float(norm.ppf(level))


def z_for_fill_rate(fill_rate: float) -> float:
    """目标 Fill Rate -> z 的近似（讨论用，不进入主流程）。

    Fill Rate 与订货量、需求分布耦合，没有严格闭式解；这里采用常见的
    正态近似：用单位正态损失函数 `L(z) = φ(z) - z·(1-Φ(z))` 迭代求解
    `1 - FillRate ≈ σ·L(z) / Q` 需要 Q，因此本函数只在 Q=1 的归一化情形下
    给出 z，仅用于论文对比讨论，不用于本实验的 SS/ROP 计算。
    """
    target = float(fill_rate)
    if not 0.0 < target < 1.0:
        raise ValueError(f"Fill Rate 必须在 (0, 1) 内，收到 {fill_rate}")
    # 目标缺货比例越小，z 越大；在 Q=1 归一化下用二分法求 z
    lo, hi = -8.0, 8.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        loss = norm.pdf(mid) - mid * (1.0 - norm.cdf(mid))
        if loss > 1.0 - target:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


@dataclass(frozen=True)
class ServiceLevelSpec:
    """服务水平规格；M5 只用 CSL。"""

    level_type: str = SERVICE_LEVEL_TYPE
    level: float = DEFAULT_SERVICE_LEVEL

    def __post_init__(self) -> None:
        if self.level_type not in SERVICE_LEVEL_TYPES:
            raise ValueError(f"未知服务水平口径: {self.level_type}")

    @property
    def z_value(self) -> float:
        if self.level_type == CSL:
            return z_for_csl(self.level)
        return z_for_fill_rate(self.level)

    def to_dict(self) -> dict:
        return {
            "service_level_type": self.level_type,
            "service_level": float(self.level),
            "z_value": round(self.z_value, 4),
        }


def describe() -> str:
    return (
        "服务水平口径定稿：CSL（周期服务水平），SS = z·sqrt(LT·σD² + D̂²·σLT²)，"
        "z = Φ⁻¹(CSL)；Fill Rate 仅作为仿真输出指标对比讨论。"
    )
