# 项目进度（每个会话开工先读这里，收尾必须更新）

> 规则：**"下一步"永远只写一条**（下一个会话直接照做）；"已知坑"只增不删（删要写原因）。

## 当前状态

- **里程碑**：**M8 主数据前端页完成**（六类主数据 CRUD + 权限置灰；`make verify` 绿且 **0 skip**）。
- **更新时间**：2026-09-19

## 已完成

- [x] 项目骨架（backend / frontend / ml / deploy / docs / scripts）
- [x] `AGENTS.md` 工作约定 + `make verify` 质量门禁（后端已转真检查）
- [x] ADR-0001 技术栈选型
- [x] GitHub 远程仓库接入（`origin`，AGENTS 第七节）
- [x] **M1-a/M1-b 数据库设计**：`docs/db-schema.md`，全库 **41 张表** + §14 对账 SQL
- [x] **M1-c 后端骨架 + 组织与权限/登录**：统一响应/错误码/trace_id、JWT 登录、`require_perm` RBAC、用户 CRUD、迁移 `0001_init_org_auth`（6 表）、`scripts/seed.py`
- [x] **M1-d 主数据模块**：§3 六张表 ORM + 迁移 `0002_master_data` + CRUD API + 测试
  （`material-categories` 树形分类含 level/path、`units`、`materials`、`warehouses`、`locations`、`suppliers`；统一用 `material:view/material:manage` 鉴权；软删；编码冲突 409、外键校验 400）
- [x] **M2-a 采购单据 + 状态机**：`core/state_machine.py`（全局 6 态 + 7 类单据迁移边 + 权限码，仅请购单审批）、采购 6 表 ORM + 迁移 `0003_procurement`、单据号 `PR/PO/RCV-YYYYMMDD-####`、请购单 CRUD+提交+审批（`purchase:approve`）+作废+转采购订单、采购订单 CRUD+确认+作废、到货单 CRUD+提交+作废（到货累计校验、批次/保质期校验）、`scripts/check_invariants.py` 与 26 条测试
- [x] **M2-b 到货验收 → 入库 → 库存流水**：`inventory`/`inventory_batch`/`inventory_transaction` + `inbound_order`/`inbound_item` ORM 与迁移 `0004_inventory_inbound`；到货验收（`PENDING→APPROVED`，生成入库单）、入库过账（`DRAFT→IN_PROGRESS`：`SELECT ... FOR UPDATE` 锁结存 → 写流水 → 更新 `inventory`/`inventory_batch` → 回写 `po_item.received_qty`/采购订单状态）、完成；库存查询 + `GET /inventory/reconcile` 对账接口；非批次物资默认批次 `__DEFAULT__`；34 条测试（SQLite + PostgreSQL 双跑）
- [x] **M2-c 出库 / 调拨 / 盘点 + 红冲**：`outbound_order`/`outbound_item`、`transfer_order`/`transfer_item`、`stocktake_order`/`stocktake_item` ORM + 迁移 `0005_inventory_ops`（并给 `inbound_order` 补 `transfer_order_id`）；抽出 `service/stock_ledger.py` 作为唯一结存变更入口；出库锁结存校验可用量、调拨两仓各写 TRANSFER_OUT/IN 并生成出/入库单、盘点差异写 STOCKTAKE_GAIN/LOSS；`reverse` 红冲（REVERSAL 反向流水）；43 条测试（SQLite + PG 双跑）
- [x] **M2-d 库存预警 / 日结存快照 / 供货价**：`stock_alert`/`inventory_snapshot_daily`/`material_supplier_price` ORM + 迁移 `0006_ledger`；预警扫描（零库存/低库存/超储/临期/过期，未关闭去重）+ ack/resolve/ignore；日快照 upsert（物资×仓库×日，含在途）；供货价 CRUD + 优先供应商唯一；50 条测试（SQLite + PG 双跑）
- [x] **M3 模拟数据生成 + 需求预测基线（ml/）**：冻结 `GeneratorConfig`（seed/skus/years、Bernoulli–Gamma、对数正态提前期）；新增 `ml/erp_ml`（config/catalog/demand/series/metrics/models/backtest/artifacts/generate/baseline）与项目内隔离 `ml/.venv`；`make gen-data` 生成 800 SKU×3 年（1095 天、876,000 行）日需求 → `data/seed_1/`（parquet/csv/json，不进 git）；实测 ADI/CV² 四象限 43.2%/24.4%/23.8%/8.6%（平滑/波动/间歇/块状）；`make baseline` 用 Naive/季节 Naive/MA7/MA28/ETS 做 3 seed × 每 seed 分层 100 序列 × horizon 7/14/30 的 expanding-window rolling-origin 回测 → `ml/results/runs/20260919-0031_m3-baseline/`；`make verify` 第 7 项（ml ruff + 14 条测试）转为真检查
- [x] **M4 特征工程 + LightGBM（并补 ARIMA/Croston 分层映射）**：新增 `ml/erp_ml/features.py`（滞后 1/2/3/7/14/28 + 滑动 7/14/28 的 mean/std/nonzero + 截断 days_since_nonzero + 日历 7 维 + 序列静态 4 维 = **27 维**，严格因果）、`gbm.py`（LightGBM 面板全局模型，每 origin 重训 + 递归多步）、`models.py` 增 ARIMA(0,1,1)(Hannan–Rissanen)/Croston/TSB 与 `model_mapping()`、`backtest.py` 增 `backtest_global`、`experiment.py` + `make forecast`，新增 3 个测试文件（ml 27 passed）。`make forecast`（seeds 1–3 × 每 seed 分层 100 序列 × horizon 7/14/30）→ `ml/results/runs/20260919-1051_m4-forecast/`（含 `model_mapping.csv`）。horizon=7 总体 MASE：ma28 0.870 / croston 0.874 / tsb 0.883 / arima 0.895 / lightgbm 0.901 / naive 1.059；分象限 MASE：Croston 间歇 0.914、块状 0.932 优于 naive（1.051/1.044），LightGBM 波动 0.779、平滑 0.895 与 ma28/arima 接近。分层映射：平滑/波动 → LightGBM（对比 ARIMA）；间歇/块状 → Croston（对比 TSB）。
- [x] **M5 动态 SS/ROP + 可解释补货建议 + A/B 库存仿真**：新增 `ml/erp_ml/service_level.py`（**CSL 口径定稿**，见 ADR-0002：`z=Φ⁻¹(CSL)`、`SS=z·√(LT·σD²+D̂²·σLT²)`、`ROP=D̂·LT+SS`；Fill Rate 仅作输出指标）、`inventory.py`（固定/动态 `(s,S)` 最小-最大 + 日度 backorder 仿真 + 成本）、`forecast_layer.py`（复用 M4 象限映射：平滑/波动→LightGBM、间歇/块状→Croston，每 origin 重训）、`replenishment.py`（建议字段对齐 `db-schema.md` §12.6，含可用/ROP/S/SS/预测值/参数来源/reason）、`sim_experiment.py` + `make simulate`，新增 4 个测试文件（ml 58 passed）。`make simulate` 跑 **30 seed × 每 seed 分层 60 序列 × 130 origins**：A（固定 SS/ROP，用 180 天历史均值/σ）vs B（预测驱动动态 SS/ROP），同需求/同提前期随机流配对 → `ml/results/runs/20260919-1246_m5-simulation/`。**30 seed 配对 Wilcoxon**：总成本 B 比 A 低 **424.85**（p<1e-6）、缺货率低 **0.0038**（p<1e-6）、Fill Rate 高 **0.0051**（p=1.1e-4）、缺货损失低 **30.10**（p=6.5e-5）、订货次数少 **3.97**（p<1e-6）；平均库存/持有成本略升（+2.93 / +2.19，均显著），**CSL 差异不显著**（-9.7e-5，p=0.211）；分象限四象限总成本与 Fill Rate 均 B 更优。产出 `policy_metrics.csv`/`ab_summary.csv`/`policies.csv`/`replenishment_suggestions.csv`（1800 条、211 条 OPEN）/`cost_service_tradeoff.csv` + 3 张 300dpi 图。

- [x] **M6 补货决策闭环后端化（后端切片）**：新增预测与决策六表 ORM（`app/model/forecast.py`/`replenishment.py`：`demand_series_meta`/`model_registry`/`forecast_run`/`forecast_result`/`replenishment_policy`/`replenishment_suggestion`）+ 迁移 `0007_forecast_replenishment`（CHECK、唯一与部分唯一索引、完整 downgrade，PG 上 `upgrade→downgrade -1→upgrade` 可逆、`jsonb`/`postgresql_where` 生效）；分层实现：预测批次/结果入库（幂等 upsert、`FR-YYYYMMDD-####`）、需求序列元数据 upsert、模型注册；补货策略 CRUD；**决策服务**读取 `forecast_result`（最新 SUCCESS/PARTIAL 批次均值 D̂）+ `demand_series_meta.std_daily`（σD），按 CSL 公式 `SS=z·√(LT·σD²+D̂²·σLT²)`、`ROP=D̂·LT+SS`、`S=ROP+D̂·复核周期` 生成可解释建议（IP=结存−锁定+在途 ≤ ROP 才落库，qty=S−IP 按 min_order_qty/pack_size 向上取整，EOQ 仅参考，reason 含公式/可用量/参数来源）；建议确认（OPEN→SUGGESTED，可改 final_qty）/驳回；**一键转请购单**（SUGGESTED→CONVERTED，生成 DRAFT 请购单并写 `converted_pr_id/converted_at`，走既有状态机）；新增权限码 `replenishment:view/manage/convert`；新增 `tests/test_forecast.py`/`tests/test_replenishment.py`（11 条）。

- [x] **M6 前端补货建议页（方案 M6 的"前端 + 一键转请购单"验收项）**：新增前端工程（Vue 3 + TS + Vite 5 + Element Plus + vue-router + axios）：`frontend/package.json`、`vite.config.ts`（`/api` 代理到 127.0.0.1:8000、dev 仅绑 127.0.0.1:5173）、`tsconfig.json`、`eslint.config.js`（ESLint 9 flat + eslint-plugin-vue + typescript-eslint）；`src/api/http.ts` 统一解包 `{code,message,data,trace_id}`、401 跳登录；`src/composables/useAuth.ts`、`src/router` 登录守卫、`src/layouts/MainLayout.vue`、`LoginView.vue` 与 `ReplenishmentView.vue`（策略 CRUD、建议列表/详情/确认/驳回、单条与批量一键转请购单，详情展示可用量/ROP/SS/预测/参数来源/reason）；接口类型由后端 OpenAPI 生成（`openapi.json` + `src/api/schema.d.ts`，脚本 `npm run gen:api`），为此给 M6/认证/主数据接口补 `response_model`（新增 `backend/app/schema/common.py` 的 `ApiResponse[T]`/`PageOut[T]`），**不手写重复类型**。

- [x] **M7 子切片 1：Docker/Nginx/Compose 一键部署 + 部署文档**：`deploy/` 新增 backend/frontend Dockerfile（非 root、精简、healthcheck）、`nginx/default.conf`（静态托管 + `/api` 反代 + SPA history fallback + `/healthz`）、`backend-entrypoint.sh`（等库 → `alembic upgrade head` → 幂等 seed → uvicorn）、`smoke.sh` 与 `.env.example`；`docker-compose.yml` 在原有 `db` 服务（定义不变）上新增 `api`（不暴露宿主端口）与 `web`（仅 `127.0.0.1:${ERP_WEB_PORT:-8080}`），沿用项目默认网络/独立卷；`make up/down/ps/logs` 与 `make seed`（改用 `python -m scripts.seed`，消除 `PYTHONPATH` 坑）；新增 ADR-0003 部署拓扑。实测 `make up` 起 3 容器、`erp-postgres` 未被重建、`smoke.sh` 5/5、迁移 head、seed 幂等、`server-health.sh` 46/0/0 PASS。

- [x] **M7 子切片 2：系统测试 + Locust 性能测试**：新增 `backend/tests/test_system.py`（功能：请购→审批→转单→到货→验收→入库→结存对账；接口：统一响应 `{code,message,data,trace_id}`/`X-Trace-Id`/OpenAPI 可发现/错误包装；权限：匿名 401、只读 403、管理员放行）共 3 条；新增 `perf/`（`locustfile.py` 只读场景、`requirements.txt`、`README.md`）与 `make perf-venv`/`make perf`（Locust **headless**，不启 Web UI、不占 8089）。实测 20s/10 用户：**200 请求 / 0 失败**、聚合中位数 11ms、登录 ~587ms（bcrypt）。

- [x] **M7 子切片 3（余力）：LSTM 与 LightGBM 对比**：新增 `ml/erp_ml/lstm.py`（面板级 LSTM：`log1p`+逐序列标准化、均值/方差只用历史、每 origin 从零重训、递归多步、固定种子）与 `lstm_experiment.py`（**复用** `backtest_global` 的 rolling-origin 协议，输出 `comparison.csv` 配对差值与 Wilcoxon）、`ml/tests/test_lstm.py`（3 条）；torch 为 `ml` **可选依赖**（CPU 轮子，`make ml-lstm`）。`make lstm`（seeds 1–3 × 每 seed 分层 40 序列 × horizon 7/14/30）→ `ml/results/runs/20260919-1715_m7-lstm/`。horizon=7（配对 n=120）：**MASE LSTM 0.831 vs LightGBM 0.902（Δ=-0.071，p=1.8e-7）**、**MAE 3.65 vs 4.02（p=2.3e-10）**；分象限 LSTM 在波动/间歇/块状更优，**平滑象限 LightGBM 更优**；sMAPE 总体反向（109.2 vs 100.2），属零值多的 sMAPE 陷阱，以 MASE/MAE 为准。

- [x] **对外展示域名**：宿主 nginx 新增站点 `gra.sukicloud.top` → `127.0.0.1:8080`（复用 `*.sukicloud.top` 泛域名证书；仅新增 vhost、未改其他站点；`server-health` 46→47 PASS）；运维记录见 `/root/dsh/CHANGELOG-ops.md`。

- [x] **M8 主数据前端页（本会话垂直切片）**：新增 schema 驱动通用 CRUD 视图 `frontend/src/views/master/MasterDataView.vue` + 六类配置 `masterConfigs.ts`（物资分类/物资/单位/仓库/库位/供应商）：关键字与分类/仓库/状态筛选、分页、新增/编辑弹窗、删除（软删）、启停用；`src/api/master.ts` 六类 CRUD 封装，接口类型全部由 OpenAPI 生成；后端新增 `CurrentUserOut`，登录与 `/auth/me` 返回 `permissions`，前端 `useAuth.hasPerm` 按 `material:manage` 隐藏/禁用按钮；侧边栏新增「主数据」子菜单与路由（`/master/*`）；**未引入新依赖**。

## 进行中

- [ ] 无

## 下一步（只做这一条）

**采购前端页（请购单 / 采购订单 / 到货单）**：先给 `backend/app/api/v1/purchase.py` 的接口补 `ApiResponse[T]`/`PageOut[T]` 的 `response_model`（参考 `schema/common.py` 与 M6/M8 做法），重跑导出 OpenAPI + `npm run gen:api`；再做只读列表 + 关键动作（请购单提交/审批/转采购订单、采购订单确认、到货单提交）。

> 开工建议换新对话框，从 `AGENTS.md` → `docs/progress.md` 继续。

## 已知坑 / 未决问题

| 项 | 说明 | 状态 |
|---|---|---|
| 运行库实例 | 已起独立 PG16 容器（`deploy/docker-compose.yml`，仅 127.0.0.1:5433）。真库验证：迁移 upgrade/downgrade 可逆、`jsonb`、`postgresql_where` 部分唯一索引、`COALESCE` 表达式唯一索引；测试支持 `ERP_TEST_DATABASE_URL` 对 PG 跑（M6 起 61 passed） | 已解决（2026-09-18） |
| 本机 Python 环境 | 系统缺 `python3-venv`，venv 用 `--without-pip` + get-pip 引导 | 已解决（backend/README.md） |
| 单据状态机 | 已实现：`core/state_machine.py` 单一事实来源（全局 6 态 + 7 类单据迁移边 + 权限码；仅请购单审批）；`apply_transition` 为唯一写 status 入口 | M2-a 完成 |
| 到货→入库联动 | 已实现：验收通过生成入库单，过账写流水并回写 PO 到货数量/状态 | M2-b 完成 |
| 领域不变量脚本 | `scripts/check_invariants.py`：状态机结构 + 权限码 + service 不直改 status + 库存只由 `service/stock_ledger.py` 过账且必须写流水 + 台账三表就位/快照不软删（verify 用 venv python 跑） | M2-b～M2-d 完成 |
| 操作日志写入 | `operation_log` 表已建，中间件写日志逻辑未实现 | 待后续切片 |
| 库存余额一致性 | `inventory` = 物资×仓库汇总、`inventory_batch` = 批次明细、`inventory_transaction` 为唯一真值源；已实现过账/红冲与 `GET /inventory/reconcile`（§14 三条+守卫），测试断言流水汇总 == 结存 | M2-b/M2-c 已实现并跑通（SQLite+PG 43 passed） |
| 已过账单据红冲 | 出库/调拨/盘点支持 `reverse`（IN_PROGRESS/COMPLETED→CANCELLED，写 REVERSAL 反向流水，不改/删历史流水）；调拨生成的出/入库单随调拨红冲；采购入库（delivery 来源）不允许直接红冲，需走采购/退货流程 | M2-c 完成（采购入库红冲待后续） |
| outbound_order.source_type 宽度 | §5.3 原 `varchar(16)` 放不下 `REQUISITION_ISSUE`(17)，PG 报 StringDataRightTruncation；已改 `varchar(32)` 并同步 `docs/db-schema.md` §5.3 | M2-c 修正（SQLite 不校验列宽，真库暴露） |
| 表数口径 | 全库 **41 张**（§2），方案写"约 36" | 已确认（采纳建议） |
| users/部门/默认批次 | `users` 复数命名、`dept_name` 文本、非批次用 `__DEFAULT__` 批次 | 已确认（Q1–Q3 采纳建议） |
| M1-b 开放问题 | M1B-Q1–Q7 见 `docs/db-schema.md` §15 | 已确认（采纳建议） |
| 预测与业务的边界 | ML 只读业务库、只写 `forecast_*` 与建议表 | 已写入 AGENTS.md |
| ML 运行环境 | `ml/.venv` 项目内隔离（Python 3.13，约 676MB）；沙箱下 `/dev/shm` 不可写 → joblib 自动退化串行（多进程不可用，代码为 joblib 并行就绪） | M3 记录 |
| 基线回测算力 | ETS（`estimated`+`optimized`）约 4.8s/序列；3 seed×100 序列全量约 25min；`make baseline` 固定 `--seeds 1 2 3 --max-series 100` | M3 记录 |
| 分层用全期观测 | ADI/CV² 用**全期**观测计算，仅用于分层报告/抽样，**不作预测特征**（避免未来信息泄漏） | M3 记录 |
| 数据生成器参数 | Bernoulli–Gamma / 对数正态提前期等参数已在 M3 冻结（`ml/erp_ml/config.py::GeneratorConfig`，见 `ml/README.md`） | 已冻结（2026-09-19） |
| 服务水平定义 | CSL 还是 Fill Rate？**全程必须一致** | **已定稿：CSL**（ADR-0002；`service_level_type='CSL'`，z=Φ⁻¹(CSL)，默认 0.95）；Fill Rate 仅作仿真输出对比（2026-09-19） |
| M4 特征维度 | 27 维 = 滞后 6 + 滑动 9 + days_since_nonzero 1 + 日历 7 + 静态 4；测试断言改写未来不改变特征 | M4 完成 |
| LightGBM 面板模型 | 跨序列全局模型，每个 origin 重训、递归多步；num_threads=2；沙箱 /dev/shm 不可写仍退化 joblib 串行（代码并行就绪）；全量约 10min | M4 记录 |
| ARIMA 估计 | 用 ARIMA(0,1,1) + Hannan–Rissanen（每 origin MLE 太慢）；差分后 MA(1)，与指数平滑同源 | M4 记录 |
| ETS 算力修正 | M3 记的"约 4.8s/序列"偏低；实测每 seed ETS 约 22–27min（seconds 1618/1331/1365s），故 M4 默认不含 ets，复用 M3 run | M4 修正 |
| 间歇/块状 sMAPE 陷阱 | 零值多时 sMAPE 奖励"全零"预测（naive 反而最低）；需看 MASE/MAE，Croston 明显更优 | M4 记录 |
| M5 EOQ 不适配间歇件 | EOQ 对低需求 SKU 会给出远超需求的订货量；M5 仿真改用 `(s,S)` 最小-最大（`S=ROP+D̂·复核周期`），EOQ 仅作参考量报告 | M5 记录 |
| M5 成本参数口径 | `order_cost` / `holding_cost_rate` / `stockout_penalty_rate` 为仿真实例设定（默认 100 / 0.20 / 0.5）；本合成数据单价小、订货成本主导总成本，故 `ab_summary.csv` 同时给持有/订货/缺货组件 | M5 记录 |
| M5 CSL 实收 vs 目标 | 正态近似 SS 在事件冲击/过度离散需求下，目标 CSL=0.95 的实收 CSL 偏低（需以仿真结果为准，论文只对**显著**差异写"优于"） | M5 记录 |
| M6 σLT 来源 | `replenishment_suggestion.sigma_lt` 库内暂无提前期波动数据，决策服务取 0（SS 公式第二项退化）；如需真实 σLT，应从历史提前期或供货价提前期估计 | M6 记录 |
| M6 service_level 量纲 | `replenishment_policy.service_level` 统一存小数（0<x<1，如 0.95），已同步修正 `db-schema.md §12.5`；z=Φ⁻¹(CSL) 用 Acklam 近似，未为此引入 scipy | M6 记录 |
| M6 在途口径 | 建议的 `in_transit_qty` 复用 `POItemRepo.in_transit_by_material()`（物料级、无仓库维度），与日快照口径一致 | M6 记录 |
| M6 下单量口径 | 按 M5 结论用 `(s,S)` 最小-最大（qty=S−IP），EOQ 仅作参考量；建议须人工确认（SUGGESTED）后才可转请购单 | M6 记录 |
| M6 提前期取值 | 决策服务提前期 = policy.lead_time_days > material.lead_time_days；暂未接入 §8 的供货价/供应商提前期优先级 | M6 记录 |
| M6 S（order_up_to）落点 | §12.6 无 `order_up_to` 列，S 写入 `reason` 文本；如需单独落库再加列 | M6 记录 |

| M6 前端工程 | 前端此前为空占位；本切片新增 Vue3+TS+Vite5+Element Plus 脚手架。依赖在 `frontend/node_modules`（项目内隔离、不入库）；接口类型由 `npm run gen:api` 从后端 OpenAPI 生成 | M6 完成 |
| M6 API 类型化 | 为让 OpenAPI 产出可用类型，给 M6/认证/主数据接口加了 `response_model`（`ApiResponse[T]`/`PageOut[T]`）；接口变更后需重跑 `npm run gen:api` 同步 `src/api/schema.d.ts` | M6 记录 |
| M6 前端未覆盖权限置灰 | 前端未按权限码隐藏按钮（`UserOut` 不含 permissions），越权时由后端 403 + 全局提示兜底 | M6 记录 |
| M6 dev 代理 | Vite dev 仅 `127.0.0.1:5173`，`/api` 代理到 `127.0.0.1:8000`；生产部署（nginx/静态托管）留 M7 | M6 记录 |
| M7 一键部署镜像源 | 本机 Docker Hub 不可达、已配置镜像 `docker.1ms.run` 极慢：构建前用 `docker.m.daocloud.io` 预拉 `python:3.12-slim`/`node:20-slim`/`nginx:1.27-alpine` 并 retag；Dockerfile 支持 `PIP_INDEX_URL`/`NPM_REGISTRY` 构建参数（默认官方源，`deploy/.env` 可覆盖） | M7 记录 |
| M7 `make down` 语义 | `make down` = `docker compose down`，会停止/移除本项目三个容器（含 `erp-postgres`，**卷保留**），`make up` 重建。仅限本项目栈，不影响其他服务 | M7 记录 |
| M7 访问方式 | 一键部署默认 `http://127.0.0.1:8080`（`deploy/.env` 的 `ERP_WEB_PORT` 可改）；**仅回环**，未做对外域名反代（需用户确认后再加） | M7 记录（待确认） |
| M7 alembic 日志 | `alembic current/upgrade` 会先打印两行格式模板字面量（`%(levelname)...`），为 `alembic.ini` 既有现象，迁移功能正常 | 既有 |
| M7 部署边界 | 容器只跑 `alembic upgrade head` + 幂等 seed；api 不对宿主暴露；web 容器内 nginx 与宿主 nginx 无关 | M7 记录 |
| M7 对外访问 | 宿主 nginx 站点 `gra.sukicloud.top` 反代到 `127.0.0.1:8080`（复用泛域名证书）；容器仍只回环，按 `newapi.sukicloud.top.conf` 参数新增，未改其他站点。回滚见 CHANGELOG-ops | M7 完成 |
| M7 性能测试端口 | Locust 用 `--headless`，不启动 Web UI（不占 8089），只对 `HOST`（默认 `127.0.0.1:8000`）发请求；场景全为只读 GET + 登录，不写业务表 | M7 记录 |
| M7 LSTM 依赖/成本 | torch 为 `ml` 可选依赖（CPU 轮子；装后 venv 约 1.6GB）；LSTM 每 origin 从零重训，本机 3 seed×40 序列约 20min（2 线程），已用 `windows_per_series`/`epochs` 控制成本 | M7 记录 |
| M7 LSTM vs GBM 结论 | MASE/MAE 上 LSTM 总体显著更优（波动/间歇/块状），但**平滑象限 LightGBM 更优**、sMAPE 总体反向；结论必须分象限、以 MASE/MAE 为准，禁止只报总体 sMAPE | M7 记录 |
| M8 当前用户权限 | 登录与 `/auth/me` 返回 `CurrentUserOut`（在 `UserOut` 上附带 `permissions`）；`/users` 未加 `response_model`，OpenAPI 不产出 `UserOut`，前端当前用户类型用 `CurrentUserOut` | M8 记录 |
| M8 主数据列表筛选 | 后端 `master` list 只支持 page/page_size；前端首版为「拉取前 200 条 + 内存筛选/分页」，超过 200 条需后续给后端加关键字/条件查询参数 | M8 记录 |
| M8 主数据编辑限制 | `MaterialCategoryUpdate` 无 `parent_id`、各 `*Update` 无 `code`、`LocationUpdate` 无 `warehouse_id`；前端这些字段编辑时禁用且不提交 | M8 记录 |
| M8 前端权限置灰 | 按钮按 `material:manage` 隐藏/禁用；后端 403 仍是最终兜底（不信任前端） | M8 记录 |

## 对账状态（库存相关改动必填）

| 日期 | 对账项 | 结果 |
|---|---|---|
| 2026-09-18 | M1-a 库存表设计口径：批次结存 = 物资×仓库×批次（`inventory_batch`）；汇总结存 = 物资×仓库（`inventory`） | 设计已冻结；库存模块未实现，无可跑数据 |
| 2026-09-18 | M1-b 对账 SQL 口径：`docs/db-schema.md` §14 四条检查 | 设计已冻结；M2 实现过账后执行 |
| 2026-09-18 | M2-a 采购单据（PR/PO/RCV）未写 `inventory` / `inventory_transaction`；到货→入库→流水联动在 M2-b | 不涉及库存过账，无对账数据；口径不变 |
| 2026-09-18 | M2-b 库存过账对账：①批次汇总 == 结存 ②流水汇总 == 结存 ③批次级流水 == 批次结存 ④无负结存/锁定超结存 | `reconcile.ok=true`；覆盖默认批次与批次物资；SQLite + PostgreSQL 双跑 34 passed |
| 2026-09-18 | M2-c 库存作业对账：出库/调拨/盘点过账与红冲后 ①批次==结存 ②流水==结存 ③批次级==流水 | `reconcile.ok=true`；出库可用量拦截、调拨两仓净额 0、盘点差异、红冲回滚均有测试；SQLite + PG 43 passed |
| 2026-09-18 | M2-d 预警/快照只读结存，不写 `inventory`/`inventory_transaction` | 不涉及结存变更；日快照 upsert 与实际结存一致，预警扫描可重复执行不产生重复 |
| 2026-09-19 | M3 数据生成只写 `data/`，预测只读业务库且只写 `ml/results/`；未触及 `inventory`/`inventory_transaction`/`forecast_*` | 不涉及结存变更；业务表零写入 |
| 2026-09-19 | M4 特征/GBM 实验只读合成数据与 `ml/results/`；未连接/未写业务库表，未触及 `inventory`/`inventory_transaction`/`forecast_*` | 不涉及结存变更；业务表零写入 |
| 2026-09-19 | M5 库存仿真：只读合成需求（内存生成，不重写 `data/`）与 `ml/results/`；未连接业务库，未写 `inventory`/`inventory_transaction`/`forecast_*`/`replenishment_*`；补货建议/策略仅为 ML 结果表（字段对齐 §12.5/§12.6） | 不涉及结存变更；业务表零写入 |
| 2026-09-19 | M6 决策服务只读 `inventory`（结存/锁定）与在途汇总，生成 `replenishment_*` 建议；不写 `inventory`/`inventory_batch`/`inventory_transaction`，不改变结存 | 不涉及结存变更；`GET /inventory/reconcile` 口径不变；SQLite + PG 双跑 61 passed |
| 2026-09-19 | M6 前端补货建议页仅通过 `/replenishment-*` API 读写建议/策略，不直连数据库；确认/转单调用后端既有事务与状态机 | 不涉及结存变更；前端只读 API，`converted_pr_id` 来源链由后端保证 |
| 2026-09-19 | M7 一键部署：容器启动只跑 `alembic upgrade head` + 幂等 seed（RBAC/管理员）；api/web 只走业务 API，不触碰 `inventory`/`inventory_batch`/`inventory_transaction` | 不涉及结存变更；部署前后业务表零写入；`GET /inventory/reconcile` 口径不变 |
| 2026-09-19 | M7 系统测试 + Locust 性能：系统测试用测试库覆盖入库过账并断言对账；Locust 场景仅 GET + 登录 | 系统测试 `reconcile.ok=true`；性能测试不写业务表、不改结存 |
| 2026-09-19 | M7 LSTM 对比：只读合成需求（内存生成），只写 `ml/results/`；未连接/未写业务库表 | 不涉及结存变更；业务表零写入 |
| 2026-09-19 | M8 主数据前端：仅通过 `/material-categories`、`/materials`、`/units`、`/suppliers`、`/warehouses`、`/locations` API 读写档案，不触碰 `inventory`/`inventory_batch`/`inventory_transaction`；登录返回权限码为只读 | 不涉及结存变更；`GET /inventory/reconcile` 口径不变；SQLite 后端 66 passed |