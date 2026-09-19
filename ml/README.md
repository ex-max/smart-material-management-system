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

## 结果落盘（`ml/results/`）

```
ml/results/
├── runs/<YYYYMMDD-HHMM>_<tag>/
│   ├── config.json     # 冻结参数、backtest 配置、seed、data_sha256、commit
│   ├── metrics.csv     # 逐 seed × 序列 × horizon × 模型明细
│   ├── summary.csv     # 象限 × 模型 × horizon 汇总（均值±标准差）
│   ├── model_mapping.csv  # 逐象限：推荐/对比模型与最优模型 sMAPE
│   ├── segments.csv    # 分层结果（ADI/CV²/象限/ABC）
│   └── figures/*.png   # 300dpi 论文用图
├── segments.csv        # latest 分层快照
└── latest -> runs/<最新>/
```

> 论文每张表/图都能追到某个 `runs/<id>`；**禁止手改结果文件**。

## 已实现 / 待实现

- [x] M3：数据生成器 + 需求分层 + Naive/MA/ETS 基线滚动回测
- [x] M4：滞后/滑动/日历特征 + LightGBM 面板模型 + Croston/TSB/ARIMA 与 ADI/CV² 分层映射
- [ ] M5：动态 SS/ROP、补货建议、A/B 库存仿真（多种子 + Wilcoxon）