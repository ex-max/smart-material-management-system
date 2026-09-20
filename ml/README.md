# ml/ —— 数据生成、需求分层、预测与仿真

## 边界（AGENTS.md 不变量 4）

- **只读业务库，不写业务表**；业务库连接仅用于**可选地读取**主数据（`--catalog-source auto|db`），
  默认合成目录，业务库无数据/不可达时自动回退，实验可离线复现。
- 生成数据落 `data/seed_<seed>/`；实验结果落 `ml/results/`。两者都**不进 git**。
- ML 结果只写 `ml/results/`，**不写任何业务表**。

## 环境（项目内隔离）

依赖见 `pyproject.toml`（numpy / pandas / scipy / statsmodels / lightgbm / pyarrow / matplotlib / joblib / psycopg）。
本机系统 python3 缺 ensurepip，用 `--without-pip` 引导：

```bash
cd ml
python3 -m venv --without-pip .venv
curl -fsSL -o /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py
.venv/bin/python /tmp/get-pip.py
.venv/bin/pip install -e ".[dev]"
```

## 命令（根目录 `make`）

| 命令 | 作用 |
|---|---|
| `make gen-data` | 生成 seed=1、800 SKU×3 年日需求 → `data/seed_1/` |
| `make baseline` | 基线滚动回测（Naive / 季节 Naive / MA7 / MA28 / ETS）→ `ml/results/` |
| `make forecast` | M4 预测实验（滞后/滑动/日历特征 + LightGBM + Croston/TSB/ARIMA，按象限映射）→ `ml/results/` |
| `make simulate` | M5 动态 SS/ROP + 补货建议 + A/B 库存仿真（30 seed + Wilcoxon）→ `ml/results/` |
| `make sync-forecast` | S2：读业务库 26 物资 × 3 仓库分层预测 → 经 API 写 `forecast_*` 六表并生成补货建议（幂等；`BASE`/`SEED`/`HORIZON`/`ARGS` 可覆盖） |
| `make lstm` | M7 余力：LSTM 与 LightGBM 需求预测对比（torch 为可选依赖）→ `ml/results/` |
| `make ml-lstm` | 安装 LSTM 可选依赖 torch（CPU 轮子，项目内隔离） |
| `make ml-test` / `make ml-lint` | ML 单元测试 / lint |

也可直接运行：
```bash
cd ml
.venv/bin/python -m erp_ml.generate --seed 1 --skus 800 --years 3 --out ../data
.venv/bin/python -m erp_ml.baseline --seeds 1 2 3 --max-series 200 --tag m3-baseline
.venv/bin/python -m erp_ml.experiment --seeds 1 2 3 --max-series 100 --tag m4-forecast
```

## 冻结的生成器参数（M3）

| 维度 | 取值 | 依据 |
|---|---|---|
| 规模 | seed=1、skus=800、warehouses=1、years=3（1095 天） | 方案 §5「百万级流水」 |
| 四象限目标占比 | 平滑 40% / 波动 25% / 间歇 25% / 块状 10% | Syntetos–Boylan |
| 间歇/块状需求 | Bernoulli–Gamma：p=0.45 / 0.30；形状 k=8 / 1.0（CV²=1/k） | Croston 经典假设 |
| 平滑/波动需求 | 每日发生，Gamma k=30 / 1.5 | ADI<1.32 |
| 季节与周内 | 月季节因子振幅 0.15；工作日高、周末低（振幅 0.45） | 方案 §5 |
| 事件冲击 | 25% SKU 有 1–6 段、每段约 7 天、放大 ~2.5× | 项目性突发 |
| 提前期 | 对数正态，均值 3–15 天，log σ=0.35 | 正值且右偏 |
| 价格 / 批次 | 单价对数正态（log μ=0, σ=1.0）；30% 批次管理 | ABC / 批次 |

> 参数单一事实来源：`erp_ml/config.py::GeneratorConfig`。每次实验的
> `config.json` 会原样记录参数与 `data_sha256`，保证可复现。
> 需求形态**最终以实测 ADI/CV² 分类为准**（目标占比只用于挑选生成参数）。

## 分层口径（ADI / CV²，Syntetos–Boylan）

- `ADI = 观测天数 / 非零天数`
- `CV² = Var(非零需求量) / Mean(非零需求量)²`
- 阈值 `ADI0 = 1.32`、`CV²0 = 0.49`：

| 条件 | 象限 |
|---|---|
| ADI<1.32 且 CV²<0.49 | SMOOTH（平滑） |
| ADI≥1.32 且 CV²<0.49 | INTERMITTENT（间歇） |
| ADI<1.32 且 CV²≥0.49 | ERRATIC（波动） |
| 其余 | LUMPY（块状） |

实现：`erp_ml/series.py`；结果：`data/seed_<n>/demand_meta.csv` 与 `ml/results/segments.csv`。

## 生成产物（`data/seed_<seed>/`）

| 文件 | 内容 |
|---|---|
| `catalog_materials.csv` | SKU 目录（编码/名称/分类/单位/单价/提前期/批次） |
| `catalog_warehouses.csv` | 仓库目录 |
| `demand_daily.parquet` | 长表：date × material_id × warehouse_id × demand_qty |
| `lead_times.parquet` | 对数正态提前期样本 |
| `demand_meta.csv` | 序列元数据（ADI / CV² / 象限 / ABC / 均值 / 标准差） |
| `data_version.json` | 冻结参数 + 行数 + `demand_sha256` + 依赖版本 |

## 基线回测协议（forecast-experiment 技能）

- 序列口径：**SKU × 仓库** 日聚合。
- 切分：expanding-window **rolling-origin**，初始训练窗 **180 天**、步长 **7 天**、
  horizon **7/14/30**；**禁止**随机切分与未来信息。
- 模型：`naive`、`seasonal_naive`(m=7)、`ma7`、`ma28`、`ets`（加法季节、无趋势）。
- 指标：MAE、RMSE、sMAPE（零值安全）、MASE（分母=季节 Naive 样本内 MAE）。
- 多种子：生成器 seed 1..N 重复，`summary.csv` 报**均值 ± 标准差**。
- 分层报告：默认每 seed 按象限分层抽 `--max-series` 条，禁止只报总体均值。
- 本机沙箱下 `/dev/shm` 不可写，joblib 检测不到命名信号量会自动**退化串行**（多进程在本环境不可用）；
  代码仍按 joblib 并行编写，换到正常环境即并行执行。

## 特征工程（M4，erp_ml/features.py）

对目标时刻 t，只用 t 之前的观测构造特征（禁止未来信息）：

| 类别 | 特征 |
|---|---|
| 滞后 | lag_1/2/3/7/14/28 |
| 滑动 | 窗口 7/14/28 的 mean / std / nonzero，以及截断到 28 的 days_since_nonzero |
| 日历 | 周内 sin/cos、月 sin/cos、是否周末、年内日 sin/cos |
| 序列静态 | log1p(均值)、CV²、非零占比、ADI（只用训练窗计算） |

共 27 维。训练样本为「目标时刻 t x 序列 j」的面板；预测用递归多步（预测值回填滞后特征）。
未来区段一律置 NaN，ml/tests/test_features.py 断言改写未来不改变任何特征。

## 模型与分层映射（M4）

| 模型 | 说明 |
|---|---|
| naive / seasonal_naive / ma7 / ma28 / ets | M3 基线 |
| arima | ARIMA(0,1,1)，Hannan–Rissanen 快速估计（差分后 MA(1)，平滑/波动象限对比） |
| croston | Croston：非零需求量与需求间隔分别 SES（间歇/块状主用） |
| tsb | Teunter–Syntetos–Babai：每期更新发生概率（间歇/块状对比） |
| lightgbm | 面板级全局模型（erp_ml/gbm.py），每个 origin 重训，平滑/波动主用 |

make forecast 默认不跑 ETS（单序列慢，M3 基线已含，可用 --local-models 显式加回）；其余模型与 M3 同一份分层抽样。
映射（models.model_mapping()）：平滑/波动 → LightGBM（对比 ARIMA）；间歇/块状 → Croston（对比 TSB）。
回测口径与 M3 完全一致（rolling-origin、初始训练窗 180、步长 7、horizon 7/14/30，sMAPE/MASE）。

## LSTM 与 LightGBM 对比（M7 余力，erp_ml/lstm.py、lstm_experiment.py）

- **协议完全复用 M4**：同一批分层序列、同一 `BacktestConfig`（初始窗 180、步长 7、
  horizon 7/14/30）、同一 `backtest_global` 口径；LightGBM 与 LSTM 在同一次实验内各跑一遍。
- **LSTM 口径**：面板级全局模型（跨序列共享权重），输入为每序列最近 `lookback` 天的
  `log1p` 标准化窗口；每个 origin **从零重训**；递归多步预测（预测回填为下一期输入），
  预测值 `expm1` 反变换并 clip≥0；均值/方差只用 `history[:origin]`，无未来信息泄漏。
- **成本控制**：每序列只取最近 `windows_per_series` 个窗口，固定 `epochs`/`hidden_size`/
  线程数；全部超参写入 `config.json`。torch 为**可选依赖**（`make ml-lstm`，CPU 轮子），
  未安装时 LSTM 测试自动跳过、不影响 `make verify`。
- **产物**：`metrics.csv` / `summary.csv` / `comparison.csv`（总体+分象限配对差值、
  MAE/MASE/sMAPE 的 Wilcoxon p 值）/ `segments.csv` / `figures/`。
- **结论纪律**：只在 Wilcoxon p<0.05 时写"优于"，否则写"差异不显著"；按象限分层报告。

## 库存决策与 A/B 仿真（M5）

实现：`erp_ml/service_level.py`（口径）、`inventory.py`（SS/ROP/EOQ + 日度仿真）、
`forecast_layer.py`（复用 M4 象限映射的滚动预测）、`replenishment.py`（可解释建议）、
`sim_experiment.py`（CLI）。

### 服务水平口径（定稿）

- **主口径 CSL（周期服务水平）**：`z = Φ⁻¹(CSL)`，
  `SS = z·√(LT·σD² + D̂²·σLT²)`，`ROP = D̂·LT + SS`。
- **Fill Rate（β 满足率）**取决于订货批量与缺货量，不是上面 SS 闭式解的输入，
  只作为**仿真输出指标**报告与讨论，不作目标口径。
- 口径由 `replenishment_policy.service_level_type = 'CSL'` 承载；
  每次实验 `config.json` 记录 `service_level_type` 与 `z_value`，保证全程一致。

### 策略与仿真协议

| 策略 | SS/ROP 来源 | 说明 |
|---|---|---|
| A 固定（对照） | 初始训练窗（180 天）均值/标准差一次性设定 | 规则驱动 |
| B 预测驱动（本文） | 每个 rolling origin 用分层模型预测的 D̂ + 近 56 天滚动 σD 重算 | 预测驱动 |

- 补货用 `(s,S)` 最小-最大：`S = ROP + D̂·复核周期`，库存位置 ≤ ROP 时抬到 S；
  EOQ 仅作参考量报告（间歇件 EOQ 常远大于需求，直接下单不现实）。
- 需求按 **backorder** 模式仿真，提前期用对数正态；
  A/B **同 seed、同需求实现、同提前期随机流**配对，评估窗口丢弃前 30 天预热。
- 指标：缺货率 / Fill Rate / CSL / 平均库存 / 周转天数 / 持有成本 / 订货次数与成本 /
  缺货成本 / 总成本，按 ADI/CV² 象限分层。

### 统计严谨性

- 多种子：`seed 1..30`，报**均值 ± 标准差**；每 seed 按象限分层抽 60 条序列。
- 配对检验：对每个 `(seed, SKU×仓库)` 的 A/B 差做 **Wilcoxon 符号秩检验**
  （two-sided），报 p 值；**只在 p<0.05 时写"优于"**，否则写"差异不显著"。
- 分层报告：总体 + 平滑/波动/间歇/块状，避免被少数大 SKU 主导。

### 可解释补货建议

`replenishment_suggestions.csv` 每条给出：当前结存 / 锁定 / 在途 / 欠交 / 可用、
预测日均 D̂、LT、σD、σLT、SS、ROP、S、EOQ、建议量、
`parameter_source`（策略 / 模型 / 象限 / 服务水平口径 / z）与自然语言 `reason`；
字段与 `docs/db-schema.md` §12.6 对齐（ML 侧只出结果表，不写业务表）。

## 结果落盘（`ml/results/`）

```
ml/results/
├── runs/<YYYYMMDD-HHMM>_<tag>/
│   ├── config.json     # 冻结参数、backtest 配置、seed、data_sha256、commit
│   ├── metrics.csv     # 逐 seed × 序列 × horizon × 模型明细
│   ├── summary.csv     # 象限 × 模型 × horizon 汇总（均值±标准差）
│   ├── model_mapping.csv  # 逐象限：推荐/对比模型与最优模型 sMAPE
│   ├── comparison.csv  # （仅 make lstm）LSTM vs LightGBM 分层配对对比 + Wilcoxon p
│   ├── segments.csv    # 分层结果（ADI/CV²/象限/ABC）
│   └── figures/*.png   # 300dpi 论文用图
├── segments.csv        # latest 分层快照
└── latest -> runs/<最新>/
```

`make simulate`（M5）额外产物（同一 `runs/<id>`）：

```
├── policy_metrics.csv            # 逐 seed × 序列 × 策略指标明细
├── ab_summary.csv                # 分层 A/B 汇总（均值±标准差 + Wilcoxon p）
├── policies.csv                  # 策略参数（A 固定 / B 预测）
├── replenishment_suggestions.csv # 可解释补货建议（对应 §12.6 字段）
├── cost_service_tradeoff.csv     # 策略 B 扫描目标 CSL 的成本-服务权衡
└── figures/inventory_trajectory.png / ab_metrics.png / cost_service_tradeoff.png
```

> 论文每张表/图都能追到某个 `runs/<id>`；**禁止手改结果文件**。

## 已实现 / 待实现

- [x] M3：数据生成器 + 需求分层 + Naive/MA/ETS 基线滚动回测
- [x] M4：滞后/滑动/日历特征 + LightGBM 面板模型 + Croston/TSB/ARIMA 与 ADI/CV² 分层映射
- [x] M5：动态 SS/ROP、补货建议、A/B 库存仿真（多种子 + Wilcoxon）—— 见上「库存决策与 A/B 仿真」
- [x] M6：预测/补货六表后端化 + 决策服务 + API + 前端补货建议页（后端见 `backend/`）
- [x] M7：Docker 一键部署 + 系统/性能测试 + **LSTM vs LightGBM 对比（余力）**