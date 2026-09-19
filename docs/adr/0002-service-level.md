# ADR-0002 服务水平口径：CSL（周期服务水平）

- 状态：已接受
- 日期：2026-09-19
- 关联：M5（动态 SS/ROP + 可解释补货建议 + A/B 库存仿真）

## 背景

安全库存/再订货点需要一个目标服务水平。CSL（周期服务水平）与 Fill Rate（满足率）
定义不同，若不先定稿会导致整条"预测→决策"链不自洽（方案 §7.2）。
数据库 `replenishment_policy.service_level_type` 的 CHECK 允许 `'CSL' | 'FILL_RATE'`。

## 决策

主口径固定为 **CSL**：

- `z = Φ⁻¹(CSL)`，`SS = z·√(LT·σD² + D̂²·σLT²)`，`ROP = D̂·LT + SS`（方案 §7.1）。
- 所有策略 `service_level_type='CSL'`，默认目标 CSL=0.95（z≈1.645），全程一致。
- Fill Rate 仅作为**仿真输出指标**报告与讨论，不作为目标口径。

## 理由

- SS 的解析式（需求 + 提前期双波动）正是以 CSL 为目标推导的，`z` 唯一确定。
- Fill Rate 依赖订货批量与缺货量，没有同样简洁的闭式 SS 解；作为目标会引入额外假设。
- M5 仿真的 CSL 只在评估窗口内的订货周期上统计，与 SS 的"周期"语义一致。

## 备选与否决

- **Fill Rate 作为主口径**：需额外假设订货批量/缺货分布，且与 SS 解析式不直接对应；否决，保留为输出指标。
- **两者并用作目标**：整条链会不自洽（方案明确要求挑一个并全程一致）；否决。

## 影响

- `replenishment_policy.service_level_type` 固定 `'CSL'`；每次实验 `config.json`
  记录 `service_level_type` 与 `z_value`（实现：`ml/erp_ml/service_level.py`）。
- 论文第 7 章以 CSL 为主口径、Fill Rate 作对比讨论。
