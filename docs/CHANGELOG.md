# 变更日志

格式：`## YYYY-MM-DD · <模块>` + 改动 / 原因 / 验证 / 回滚
（每个工作会话收尾时追加一条）

## 2026-09-18 · 数据库设计（M1-a）

- **改动**：新增 `docs/db-schema.md` —— 主数据(6) + 采购(6) + 库存作业(9) 共 **21 张表**的字段/类型/约束/索引/关系、通用约定（主键/审计/类型/状态机/单号/追溯）、E-R 图、领域不变量落点与接口契约；同步更新 `docs/progress.md`（已完成/进行中/下一步/已知坑/对账状态）。
- **原因**：`docs/progress.md` 的"下一步" M1-a —— 按方案先把主数据 + 采购 + 库存作业三组设计出来，供评审后再补其余四组。本会话评审决策：分类多级树、仅基本单位、仅请购单审批、批次可开关且结存到批次、到货分批并自动生成入库单、到货/调拨拆头行（三组由 19 → 21 张）、盘点差异走流水不新增调整单。
- **验证**：`make verify` 绿（结构/lint/测试/迁移 4 项因后端前端尚未落地而 skip）。
- **回滚**：`git revert <本次提交>`（仅涉及 `docs/`，无代码/迁移副作用）。

## 2026-09-18 · 项目规则 / 数据库设计评审结论

- **改动**：
  - `AGENTS.md`：收尾 DoD 增加第 5 步“`git push origin main`”，并新增第七节「远程仓库与同步」，写入 GitHub 地址 https://github.com/ex-max/smart-material-management-system。
  - `docs/db-schema.md`：§9 由“待确认 / 开放问题”改为“开放问题与已定结论”，Q1–Q8 全部采纳建议（users 命名、非批次默认批次 `__DEFAULT__`、部门用 `dept_name` 文本、单号计数+重试、bigint identity、库位可空、盘点整单过账、出库成本仅占位）。
  - `docs/progress.md`：已知坑状态改为“已确认（采纳建议）”；下一步移除“消化开放问题”。
- **原因**：用户评审指示——§9 开放问题全部采纳建议；并把 GitHub 仓库与“每次收尾同步”写入规则。
- **验证**：`make verify` 绿（跳过 4 项）。远程同步：`origin` 已指向 GitHub 仓库，推送结果见会话结论。
- **回滚**：`git revert <本次提交>`（仅文档与规则，无代码副作用）。

## 2026-09-18 · 数据库设计（M1-b：补全全库 41 张表）

- **改动**：`docs/db-schema.md` 追加第二部分 §10–§13 —— 组织与权限 6（users/roles/permissions/user_role/role_permission/operation_log）、台账与统计 5（inventory/inventory_transaction/stock_alert/inventory_snapshot_daily/material_supplier_price）、预测与决策 6（demand_series_meta/model_registry/forecast_run/forecast_result/replenishment_policy/replenishment_suggestion）、系统 3（dict/scheduled_task_log/attachment）；新增 §14 E-R 补充与四条库存对账 SQL、§15 M1-b 开放问题；同步修正 §0 范围、§2 总览（41 张）、§8 跨组契约（澄清 inventory 粒度：汇总表=物资×仓库、明细表=批次）。`docs/progress.md` 同步更新（M1-b 完成 / 下一步 M1-c / 已知坑 / 对账状态）。
- **原因**：`docs/progress.md` 的"下一步" M1-b —— 按 §8 接口契约补全其余四组，使全库设计闭环，供评审。
- **验证**：`make verify` 绿（结构/lint/测试/迁移 4 项仍 skip）；文档自检：§2 共 41 行、§10–§13 共 20 张表。
- **回滚**：`git revert <本次提交>`（仅 `docs/`，无代码/迁移副作用）。
- **备注**：按用户要求，本次提交**先不推送**，待评审通过后再 `git push origin main`。

## 2026-09-18 · 数据库设计评审结论（M1-b）

- **改动**：`docs/db-schema.md` §15 由"剩余开放问题"改为"已定结论"（M1B-Q1–Q7 全部采纳建议）；`docs/progress.md` 已知坑对应行状态改为"已确认（采纳建议）"。
- **原因**：用户评审通过并明确采纳建议。
- **验证**：`make verify` 绿（4 项 skip）；本次一并把 M1-b 提交推送到 `origin/main`。
- **回滚**：`git revert <本次提交>`，或撤回远程提交。

## 2026-09-18 · 后端骨架 + 组织与权限/登录（M1-c）

- **改动**：新增 `backend/` 可运行工程 —— FastAPI 分层骨架（api/service/repository/model/schema/core）、统一响应 `{code,message,data,trace_id}` 与业务错误码分段、全局异常处理、请求 trace_id 中间件；JWT 登录（`/api/v1/auth/login|me`）与 `require_perm` 接口级 RBAC；用户 CRUD + 角色/权限查询；ORM 六张表（users/roles/permissions/user_role/role_permission/operation_log）；Alembic 迁移 `0001_init_org_auth`；`scripts/seed.py` 幂等初始化 RBAC 与管理员；`backend/README.md` 与 `.env.example`；pytest 8 条（含权限拒绝路径）。
- **依赖**：ADR-0001 已选 FastAPI/SQLAlchemy/Alembic/Pydantic/JWT；本次引入具体实现库：`psycopg[binary]`（PG 驱动）、`pydantic-settings`（.env 配置）、`PyJWT`（签令牌）、`bcrypt`（口令哈希）、`pytest/httpx/ruff`（测试与 lint）。**未引入任何 ADR 之外的框架**。
- **验证**：`make verify` 绿 —— ruff 通过；`pytest 8 passed`；`alembic upgrade head --sql` 渲染 171 行（真检查，不再是 skip）。
- **回滚**：`git revert <本次提交>`（删除新增文件即可，无数据/迁移副作用）。
- **备注**：本机无 PostgreSQL，测试用 SQLite 内存库；PG 实例与 `jsonb`/`postgresql_where` 行为待 `deploy/` 起独立实例后验证（已记入 progress 已知坑）。

## 2026-09-18 · 主数据模块（M1-d）

- **改动**：新增主数据六张表的 ORM（`app/model/master.py`）与迁移 `0002_master_data`（unit/supplier/warehouse/material_category/location/material，含 CHECK、部分唯一索引、分类树 `COALESCE(parent_id,0)+code` 唯一）；新增 `app/repository/master.py`（通用 BaseRepo + 6 个子类）、`app/schema/master.py`（18 个 DTO）、`app/service/master.py`（CrudService + 6 个实体服务，含编码唯一校验与外键存在性校验、分类 level/path 自动维护）、`app/api/v1/master.py`（6 资源 × CRUD 的注册式路由，统一用 `material:view/material:manage` 鉴权）；新增 `tests/test_master_data.py`。
- **原因**：progress 的"下一步" M1-d —— 落地 `docs/db-schema.md` §3 主数据组，补齐 M1（物资/仓库/供应商/权限 + 登录）的后端验收。
- **验证**：`make verify` 绿 —— ruff 通过；`pytest 12 passed`（含树形分类、唯一冲突 409、外键校验 400、软删后 404、viewer 403）；`alembic upgrade head --sql` 渲染 352 行。
- **回滚**：`git revert <本次提交>`（无数据迁移；若已建表，alembic downgrade 到 `0001_init_org_auth`）。
- **备注**：分类树深拷贝约束（同父下 code 唯一）在服务层与库层双重保证；未实现分页筛选与操作日志写入。

## 2026-09-18 · 采购单据 + 状态机（M2-a）

- **改动**：
  - 新增 `backend/app/core/state_machine.py`：全局 6 态（DRAFT/PENDING/APPROVED/IN_PROGRESS/COMPLETED/CANCELLED）与 7 类单据的迁移边（动作/来源态/目标态/权限码/标签），仅请购单有审批边；`apply_transition()` 是唯一写 `status` 的入口。
  - 新增 `backend/app/core/errors.py` 采购段错误码：`E_PURCHASE_STATE=30001`、`E_PURCHASE_NOT_EDITABLE=30002` 及 `InvalidState`/`NotEditable`。
  - 新增采购 6 张表 ORM（`backend/app/model/purchase.py`）：`purchase_requisition`/`pr_item`、`purchase_order`/`po_item`、`supplier_delivery`/`supplier_delivery_item`；含 CHECK、唯一/外键索引、物资快照与来源链 `po_item.source_pr_item_id`。
  - 新增迁移 `0003_procurement`（含完整 downgrade）。
  - 新增 `repository`/`schema`/`service`/`api`：单号 PR/PO/RCV-YYYYMMDD-####（当天最大流水 +1）；请购单 CRUD + 提交/审批（`purchase:approve`）/作废/转采购订单；采购订单 CRUD + 确认/作废；到货单 CRUD + 提交/作废（按订单行累计到货校验，批次物资必填批次号、保质期物资必填到期日）。
  - 新增 `scripts/check_invariants.py`（`make verify` 第 6 项转为真检查）与 `tests/test_state_machine.py`、`tests/test_purchase.py`。
- **原因**：progress 的“下一步” M2-a —— 落地 `docs/db-schema.md` §4 采购组与 §1.6 状态机；到货→入库→`inventory_transaction` 联动按计划留 M2-b。
- **验证**：`make verify` 绿 —— ruff 通过；`pytest 26 passed`（状态流、权限拒绝 403、非法迁移 409/30001、非草稿不可改 409/30002、超量到货 400、批次校验、单号流水）；`alembic upgrade head --sql` 608 行；`downgrade 0003:0002 --sql` 可渲染；OpenAPI 34 paths。
- **回滚**：`git revert <本次提交>`；若已建表，`alembic downgrade 0002_master_data`。
- **备注**：本机无 PostgreSQL，迁移为人工编写（无法 autogenerate）并逐项核对 ORM；PG 专有行为待真库验证。

## 2026-09-18 · 到货 → 入库 → 库存流水（M2-b）+ 本地 PostgreSQL

- **改动**：
  - 新增 `backend/app/model/inventory.py`：`inventory`（物资×仓库汇总）、`inventory_batch`（批次；非批次物资用 `__DEFAULT__` 默认批次）、`inventory_transaction`（唯一真值源，只 INSERT）、`inbound_order`/`inbound_item`。
  - 新增迁移 `0004_inventory_inbound`（含完整 downgrade）。
  - 新增 `repository`/`schema`/`service`/`api`：到货验收（`POST /supplier-deliveries/{id}/accept`：记录验收结论并生成入库单）、入库过账（`POST /inbound-orders/{id}/post`：`SELECT ... FOR UPDATE` 锁结存 → 同事务写 `inventory_transaction` → 更新 `inventory`/`inventory_batch` → 回写 `po_item.received_qty` 与采购订单状态）、完成/作废；库存查询（`/inventory`、`/inventory/batches`、`/inventory/transactions`）与 `GET /inventory/reconcile`（§14 对账）。
  - `scripts/check_invariants.py` 扩展库存检查（只有 `service/inventory.py` 可改结存且必须写流水；流水表无 updated_at/deleted_at）；`scripts/verify.sh` 第 6 项改用 venv python。
  - 新增 `deploy/docker-compose.yml`：独立 PostgreSQL 16（仅 127.0.0.1:5433，独立卷）；重写 `deploy/README.md`。
  - 测试：新增 `tests/test_inventory.py`（8 条）；`conftest.py` 支持 `ERP_TEST_DATABASE_URL` 对 PG 跑。
- **原因**：progress 的“下一步” M2-b —— 落地 `docs/db-schema.md` §5.1/§5.2/§5.9 与 §11.1/§11.2，闭合“采购→到货→入库→流水→结存”链路；并按用户要求补齐缺失环境（PostgreSQL）。
- **验证**：`make verify` 绿（ruff 通过；`pytest 34 passed`；迁移链 816 行；不变量检查通过）。真库：PG16 上 `upgrade head`/`downgrade -1`/`upgrade head` 全通；`ERP_TEST_DATABASE_URL=postgresql+psycopg://erp:erp@127.0.0.1:5433/erp pytest` → 34 passed（覆盖 `FOR UPDATE`、部分唯一索引、CHECK）；`reconcile.ok=true`。
- **回滚**：`git revert <本次提交>`；若已建表，`alembic downgrade 0003_procurement`；数据库实例 `docker compose -f deploy/docker-compose.yml down`（保留卷）。
- **备注**：冻结状态机下已过账单据不可作废，故本期无 `REVERSAL` 红冲路径（随 M2-c 出库/盘点实现）。

## 2026-09-18 · 出库 / 调拨 / 盘点 + 红冲（M2-c）

- **改动**：
  - 新增 `backend/app/model/inventory_ops.py`：`outbound_order`/`outbound_item`、`transfer_order`/`transfer_item`、`stocktake_order`/`stocktake_item`；`inbound_order` 补 `transfer_order_id`。
  - 新增迁移 `0005_inventory_ops`（含完整 downgrade 与给 `inbound_order` 加列/索引）。
  - 抽出 `backend/app/service/stock_ledger.py`：唯一允许改结存的位置（锁行 + 同事务写流水）；入库过账改为调用它。
  - 新增 `repository`/`schema`/`service`/`api`：出库（建单/过账/完成/作废/红冲；过账校验可用量，批次物资必须指定批次）、调拨（过账生成源仓出库 + 目标仓入库并各写 TRANSFER_OUT/IN，红冲两仓回滚并红冲生成的单据）、盘点（`start` 快照 book_qty、`counts` 录实盘、`complete` 按差异写 STOCKTAKE_GAIN/LOSS、`reverse` 红冲）。
  - 状态机新增 `REVERSE`（红冲）动作：库存类单据 IN_PROGRESS/COMPLETED → CANCELLED；采购入库（delivery 来源）红冲被服务层拒绝。
  - 测试：新增 `tests/test_inventory_ops.py`（9 条）；`conftest` 增加每请求回滚以贴合生产。
- **原因**：progress 的“下一步” M2-c —— 落地 `docs/db-schema.md` §5.3–§5.8 与红冲规则（§1.6 规则 3、erp-db-migration checklist）。
- **验证**：`make verify` 绿（ruff 通过；`pytest 43 passed`；迁移链 1052 行；不变量检查通过）。真库：PG16 双跑 43 passed，暴露并修复 `outbound_order.source_type varchar(16)` 放不下 `REQUISITION_ISSUE`(17)（改 32，同步 `docs/db-schema.md` §5.3）；对账 `reconcile.ok=true`。
- **回滚**：`git revert <本次提交>`；若已建表，`alembic downgrade 0004_inventory_inbound`。
- **备注**：采购入库红冲（需回滚 PO/到货）留后续；`stock_alert`/`inventory_snapshot_daily`/`material_supplier_price` 留 M2-d。

## 2026-09-18 · 库存预警 / 日结存快照 / 供货价（M2-d）

- **改动**：
  - 新增 `backend/app/model/ledger.py`：`stock_alert`（未关闭去重为 COALESCE 表达式部分唯一索引）、`inventory_snapshot_daily`、`material_supplier_price`（每物料至多一个优先供应商）；迁移 `0006_ledger`（含完整 downgrade）。
  - 新增 `repository`/`schema`/`service`/`api`：预警扫描（零库存/低库存/超储/临期/过期；OPEN/ACKED 去重）+ ack/resolve/ignore；日快照 upsert（物资×仓库×日，含 `in_transit_qty`）；供货价 CRUD + 优先供应商自动切换。
  - `scripts/check_invariants.py` 扩展：台账三表就位、快照表不软删；结存直改检查收窄到结存对象变量（避免快照 `row.quantity` 误报）。
  - **规则**：`AGENTS.md` 硬规则新增"服务器缺环境→自行安装"，并同步 `server-ops` 技能与 `/root/dsh/SERVER-OPS-RULES.md`（运维侧记录见 `/root/dsh/CHANGELOG-ops.md`）。
- **原因**：progress 的“下一步” M2-d —— 落地 `docs/db-schema.md` §11.3–§11.5，为 M3 预测提供日序列与预警/价格基础。
- **验证**：`make verify` 绿（ruff 通过；`pytest 50 passed`；迁移链可解析；不变量检查通过）。真库：PG16 双跑 50 passed；确认 `uq_stock_alert_open` 为 `COALESCE(...)` 表达式部分唯一索引。
- **回滚**：`git revert <本次提交>`；若已建表，`alembic downgrade 0005_inventory_ops`。
- **备注**：快照 `in_transit_qty` 暂取物料级在途（PO 无仓库维度），已记录口径；供货价暂为单条当前价（历史版本化见 `docs/db-schema.md` §15-Q3）。

## 2026-09-19 · 模拟数据生成 + 需求预测基线（M3）

- **改动**：
  - 新增 `ml/` 完整模块（独立 `ml/.venv`，项目内隔离）：`erp_ml/config.py`（冻结 `GeneratorConfig`/`BacktestConfig`）、`catalog.py`（合成目录 + 业务库**只读**主数据，空库自动回退）、`demand.py`（月季节 + 周内 + 事件冲击，Bernoulli–Gamma 四象限，对数正态提前期）、`series.py`（ADI/CV² Syntetos–Boylan 分层 + ABC）、`metrics.py`（MAE/RMSE/sMAPE/MASE）、`models.py`（Naive/季节 Naive/MA7/MA28/ETS）、`backtest.py`（expanding-window rolling-origin，joblib 并行）、`artifacts.py`、`generate.py`、`baseline.py` 与 `tests/`（14 条）。
  - `Makefile` 新增 `baseline`/`ml-venv`/`ml-test`/`ml-lint`，`gen-data` 改用 `ml/.venv`；`scripts/verify.sh` 新增第 7 项 ML lint + 测试（门禁随模块落地自动变严）。
  - 生成数据落 `data/seed_1/`（`demand_daily.parquet`、`lead_times.parquet`、`demand_meta.csv`、`catalog_*.csv`、`data_version.json`）；实验结果落 `ml/results/runs/20260919-0031_m3-baseline/`（`config.json`/`metrics.csv`/`summary.csv`/`segments.csv`/`figures/*.png`）。两者均不进 git。
- **原因**：`docs/progress.md` 的“下一步” M3 —— 冻结生成器参数、实现 `ml/erp_ml/generate`（只读业务库、不写业务表）、构建需求序列与 ADI/CV² 分层、跑通 `make gen-data`，并给出 Naive/MA/ETS 等基线滚动回测表。
- **验证**：`make verify` 绿（后端 50 passed、ml ruff 通过、ml pytest 14 passed、迁移链 1155 行、不变量检查通过）。`make gen-data` → 800 SKU×3 年（876,000 行），实测四象限 43.2/24.4/23.8/8.6%。`make baseline`（seeds 1–3 × 每 seed 分层 100 序列 × horizon 7/14/30）—— horizon=7 sMAPE：ETS 对 SMOOTH 最优（19.81% vs 季节 Naive 23.96%），Naive 对间歇/块状最优（105.95%/79.77%），总体 MASE：MA28 0.870 / ETS 0.879 / Naive 1.059。
- **回滚**：`git revert <本次提交>`（删除新增 `ml/` 代码与 Makefile/verify 改动即可；`data/`、`ml/results/`、`ml/.venv` 均不入库）。
- **备注**：沙箱 `/dev/shm` 不可写 → joblib 检测不到命名信号量并退化串行（代码为 joblib 并行就绪）；ETS 单序列约 4.8s，故默认回测规模取 3 seed×100 序列。`config.json` 的 `code_commit` 记录运行时的基线提交 `af6a127`，结果对应 M3 工作区。




## 2026-09-19 · 特征工程 + LightGBM + ARIMA/Croston 分层映射（M4）

- **改动**：
  - 新增 `ml/erp_ml/features.py`：滞后(1/2/3/7/14/28) + 滑动(7/14/28 的 mean/std/nonzero + 截断 days_since_nonzero) + 日历(7) + 序列静态(4) = **27 维**因果特征；`build_panel_training` / `build_row_features` 保证只用目标时刻之前的数据。
  - 新增 `ml/erp_ml/gbm.py`：LightGBM 面板级全局模型（每个 origin 重训、递归多步；预测前把 origin 之后置 NaN 防泄漏）。
  - `ml/erp_ml/models.py`：新增 ARIMA(0,1,1)（Hannan–Rissanen 快速估计）、Croston、TSB，以及 `model_mapping()` / `recommend_model()`（平滑/波动→lightgbm、间歇/块状→croston）。
  - `ml/erp_ml/backtest.py`：新增 `backtest_global`（与 M3 同一 expanding-window rolling-origin 口径，输出同结构逐序列指标）。
  - 新增 `ml/erp_ml/experiment.py` 与 `make forecast`；`ml/pyproject.toml` 加 `lightgbm>=4.7,<4.8`；`ml/README.md` 补 M4 章节；`ml/erp_ml/artifacts.py` 跟踪 lightgbm 版本。
  - 新增测试 `ml/tests/test_features.py`、`test_models.py`、`test_gbm.py`（含“改写未来不影响特征”“预测忽略未来真实值”“LightGBM 可复现”）。
- **原因**：`docs/progress.md` 的“下一步” M4 —— 在 M3 回测框架上补特征工程与 LightGBM，并按 ADI/CV² 象限做模型映射（补 ARIMA/Croston）。
- **验证**：
  - `make verify` 绿：后端 ruff + pytest 50 passed；ml ruff + pytest 27 passed；迁移链 1155 行；不变量检查通过。
  - `make forecast`（seeds 1–3 × 每 seed 分层 100 序列 × horizon 7/14/30）→ `ml/results/runs/20260919-1051_m4-forecast/`（config / metrics / summary / segments / model_mapping / figures）。
  - horizon=7 总体 MASE：ma28 0.870 / croston 0.874 / tsb 0.883 / arima 0.895 / lightgbm 0.901 / naive 1.059；分象限 MASE：Croston 间歇 0.914、块状 0.932 优于 naive（1.051/1.044），LightGBM 波动 0.779 与 ma28（0.771）接近、平滑 0.895。
  - 依赖安装的健康检查前后一致（29 通过 / 0 警告 / 1 项既有 FAIL），见 `/root/dsh/CHANGELOG-ops.md`。
- **回滚**：`git revert <本次提交>`；如需移除依赖：`ml/.venv/bin/pip uninstall -y lightgbm`（`data/`、`ml/results/`、`ml/.venv` 均不入库）。
- **备注**：ETS 单序列实测每 seed 约 22–27min（M3 记录的 4.8s/序列偏低），故 M4 默认不含 ets，ETS 基线仍以 M3 run 为准；ARIMA 用 Hannan–Rissanen 以避免每 origin 的 MLE 开销。

## 2026-09-19 · 动态 SS/ROP + 可解释补货建议 + A/B 库存仿真（M5）

- **改动**：
  - 服务水平口径定稿（新增 `docs/adr/0002-service-level.md`）：主口径 **CSL**，`z=Φ⁻¹(CSL)`、`SS=z·√(LT·σD²+D̂²·σLT²)`、`ROP=D̂·LT+SS`；Fill Rate 仅作仿真输出指标；`replenishment_policy.service_level_type` 固定 `'CSL'`。
  - 新增 `ml/erp_ml/service_level.py`：`z_for_csl`、`ServiceLevelSpec`（CSL 为主，Fill Rate 仅讨论）、`describe()`。
  - 新增 `ml/erp_ml/inventory.py`：SS/ROP/EOQ 公式、对数正态提前期 σLT、固定策略（历史均值/σ）与动态策略（预测 D̂ + 滚动 σD）、`(s,S)` 最小-最大下单、日度 backorder 仿真与成本（持有/订货/缺货/总成本）；CSL 只在评估窗口内的订货周期上统计。
  - 新增 `ml/erp_ml/forecast_layer.py`：复用 M4 分层映射产出每 origin 的滚动预测（平滑/波动→LightGBM，间歇/块状→Croston）。
  - 新增 `ml/erp_ml/replenishment.py`：可解释补货建议/策略参数，字段对齐 `docs/db-schema.md` §12.5/§12.6（可用量/ROP/S/SS/EOQ/预测值/参数来源/reason）。
  - 新增 `ml/erp_ml/sim_experiment.py` 与 `make simulate`；新增测试 `test_service_level.py`/`test_inventory.py`/`test_replenishment.py`/`test_forecast_layer.py`/`test_sim_summary.py`。
  - `Makefile` 加 `simulate`；`ml/README.md` 补 M5 章节；`docs/db-schema.md` §12.5/§15 标注 CSL 定稿。
- **原因**：`docs/progress.md` 的"下一步" M5 —— 把 M4 预测接入 `SS/ROP=f(需求波动, 提前期, 服务水平)`，生成可解释补货建议，并按 forecast-experiment 技能用多种子 A/B 仿真 + Wilcoxon 检验业务收益。
- **验证**：
  - `make verify` 绿：后端 ruff + pytest 50 passed；ml ruff + pytest 58 passed；迁移链 1155 行；不变量检查通过。
  - `make simulate`（30 seed × 每 seed 分层 60 序列 × 130 origins，A 固定 vs B 预测驱动，同需求/同提前期配对）→ `ml/results/runs/20260919-1246_m5-simulation/`（config / policy_metrics / summary=ab_summary / policies / replenishment_suggestions / cost_service_tradeoff / segments / figures）。
  - 30 seed 配对 Wilcoxon（n=1800）：总成本 B 比 A 改善 **424.85**（p<1e-6）、缺货率 **0.0038**（p<1e-6）、Fill Rate **0.0051**（p=1.1e-4）、缺货损失 **30.10**（p=6.5e-5）、订货次数 **3.97**（p<1e-6）；平均库存/持有成本分别变差 2.93/2.19（均显著），CSL 差异不显著（p=0.211）；四象限总成本与 Fill Rate 均 B 更优。
  - 可解释建议 1800 条（211 条 OPEN），字段与 §12.6 对齐；策略参数 3600 行（A/B × 30 seed × 60 序列）。
- **回滚**：`git revert <本次提交>`（仅新增 ML 模块/测试/文档，无迁移/数据副作用；`data/`、`ml/results/`、`ml/.venv` 不入库）。
- **备注**：EOQ 对间歇件会给出远超需求的订货量，仿真改用 `(s,S)` 最小-最大，EOQ 仅作参考量；成本参数为仿真实例设定（本合成数据订货成本主导总成本），`ab_summary.csv` 同时给持有/订货/缺货组件；沙箱 `/dev/shm` 不可写，joblib 仍退化串行。

## 2026-09-19 · 补货决策闭环后端化（M6）

- **改动**：
  - 新增预测与决策六表 ORM：`backend/app/model/forecast.py`（`demand_series_meta`/`model_registry`/`forecast_run`/`forecast_result`）与 `backend/app/model/replenishment.py`（`replenishment_policy`/`replenishment_suggestion`）；迁移 `0007_forecast_replenishment`（CHECK、唯一/部分唯一索引、`jsonb`、完整 downgrade）。
  - 新增 `repository`/`schema`/`service`/`api`：预测批次与结果入库（幂等 upsert、`FR-YYYYMMDD-####`、finish）、需求序列元数据 upsert、模型注册；补货策略 CRUD；建议生成/列表/详情/确认/驳回；一键转请购单（含批量）。
  - 决策口径（M6 定稿，按用户确认）：CSL 服务水平（小数 `0.95`，z=Φ⁻¹(CSL) 用 Acklam 近似，不引入 scipy）；`SS=z·√(LT·σD²+D̂²·σLT²)`、`ROP=D̂·LT+SS`、`S=ROP+D̂·复核周期`；IP=结存−锁定+在途 ≤ ROP 才落库；qty=S−IP 按 `min_order_qty`/`pack_size` 向上取整；EOQ 仅参考；建议须人工确认（OPEN→SUGGESTED）后才能转单，转单生成 DRAFT 请购单并写 `converted_pr_id/converted_at`（来源链）。
  - `app/service/purchase.py` 抽出 `PurchaseRequisitionService.build()`，使补货转单与请购单创建在同一事务内完成。
  - 新增权限码 `replenishment:view/manage/convert`（`core/permissions.py` + 种子）；`docs/db-schema.md` §12.5/§12.6 修正 `service_level` 为小数口径并补建议状态口径。
  - 新增 `tests/test_forecast.py`、`tests/test_replenishment.py`（11 条），`conftest.py` 增 `replenishment_users`。
- **原因**：`docs/progress.md` 的"下一步" M6 —— 把 M5 的动态 SS/ROP 与可解释建议落成业务库表与 API，打通"读取预测 → 生成建议 → 一键转请购单"闭环；ML 侧仍只读业务库、不写业务表。
- **验证**：`make verify` 绿（ruff 通过；`pytest 61 passed`；ml 58 passed；迁移链 1455 行；不变量检查通过）。真库：PG16 双跑 61 passed；迁移在全新库 `upgrade→downgrade -1→upgrade` 可逆；`params/metrics/feature_config` 为 `jsonb`；`uq_rs_open`/`uq_replenishment_policy_code` 为部分唯一索引。
- **回滚**：`git revert <本次提交>`；若已建表，`alembic downgrade 0006_ledger`。
- **备注**：σLT 库内暂无来源，暂取 0（公式第二项退化）；在途为物料级（复用 `in_transit_by_material`）；S 仅写入 `reason`（§12.6 无该列）。

## 2026-09-19 · M6 前端补货建议页 + API 类型化

- **改动**：
  - 新增前端工程（Vue 3 + TS + Vite 5 + Element Plus + vue-router + axios）：`frontend/package.json`、`vite.config.ts`（dev 仅 `127.0.0.1:5173`，`/api` 代理到 `127.0.0.1:8000`）、`tsconfig.json`、`eslint.config.js`（ESLint 9 flat + eslint-plugin-vue + typescript-eslint）。
  - 分层实现：`src/api/http.ts`（统一解包 `{code,message,data,trace_id}`、401 跳登录）、`src/api/auth.ts`/`master.ts`/`replenishment.ts`；`src/composables/useAuth.ts`；`src/router`（登录守卫）；`src/layouts/MainLayout.vue`；`src/views/LoginView.vue`、`ReplenishmentView.vue`（策略 CRUD、建议列表/详情、确认/驳回、单条与批量一键转请购单；详情展示可用量/ROP/SS/预测值/参数来源/reason）。
  - 接口类型由后端 OpenAPI 生成（`frontend/openapi.json` + `src/api/schema.d.ts`，脚本 `npm run gen:api`），不手写重复类型；为此给 M6/认证/主数据/分页接口补 `response_model`（新增 `backend/app/schema/common.py` 的 `ApiResponse[T]`/`PageOut[T]`）。
  - `frontend/README.md` 说明开发、生成类型与质量门禁。
- **原因**：`docs/progress.md` 的"下一步" M6 —— 补齐方案 M6 的"前端 + 一键转请购单"验收项，使补货决策闭环可在界面演示。
- **验证**：`make verify` 绿且 **0 skip**（前端 lint 由 skip 转真检查；后端 61 passed；ml 58 passed；迁移链 1455 行）。前端 `npm run lint` / `vue-tsc --noEmit` / `npm run build` 均通过；PG16 后端 61 passed。运行时冒烟：`npm run dev` + `make serve`，经 Vite 代理 `GET /api/health`、`POST /auth/login`(admin)、创建策略、`POST /replenishment-suggestions/generate`、建议列表均正常。
- **回滚**：`git revert <本次提交>`（删除 `frontend/` 新增文件即可；`node_modules/`/`dist/` 不入库；后端 `response_model` 改动随之回滚）。
- **备注**：前端依赖在 `frontend/node_modules`（项目内隔离、不入库）；`openapi.json`/`schema.d.ts` 为生成快照，接口变更后重跑 `npm run gen:api`；生产静态托管/nginx 留 M7。

## 2026-09-19 · 一键部署：Docker/Nginx/Compose + 部署文档（M7 子切片 1）

- **改动**：
  - 新增容器化文件：根 `.dockerignore`；`deploy/backend.Dockerfile`（python:3.12-slim + uvicorn，非 root uid 10001，容器内 healthcheck）、`deploy/frontend.Dockerfile`（node:20-slim 多阶段构建 → nginx:1.27-alpine 静态托管）、`deploy/nginx/default.conf`（静态 + `/api` 反代 + SPA history fallback + `/healthz`）、`deploy/backend-entrypoint.sh`（等库 → `alembic upgrade head` → 幂等 seed → uvicorn）、`deploy/smoke.sh`（5 项部署冒烟）。
  - `deploy/docker-compose.yml`：在原有 `db` 服务（**定义不变**）上新增 `api`（不对宿主暴露端口）与 `web`（仅 `127.0.0.1:${ERP_WEB_PORT:-8080}`），`depends_on` healthcheck 条件 + 各自 healthcheck；沿用项目默认网络 `erp_default` 与独立卷 `erp_erp-pgdata`。
  - 新增 `deploy/.env.example`（端口/JWT/管理员/镜像源）；重写 `deploy/README.md`（拓扑/端口/连接串/迁移/seed/回滚/影响/边界）；新增 `docs/adr/0003-deployment.md`。
  - `Makefile` 新增 `seed`（改用 `python -m scripts.seed`，消除 `PYTHONPATH` 坑）、`up`/`down`/`ps`/`logs` 一键入口；新增 `backend/scripts/__init__.py`；`backend/README.md` 同步 seed 命令。
- **原因**：`docs/progress.md` 的"下一步" M7 子切片 1 —— 把 backend/frontend/db 纳入 `deploy/` 一键部署，补启动/迁移/静态托管与部署文档；按 `server-ops` 项目内隔离、仅回环暴露。
- **验证**：`make verify` 绿且 0 skip（后端 61 passed、前端 lint、ml 58 passed、迁移链 1455 行、不变量通过）。`make up` 构建并起 3 容器：`erp-api`(healthy, uid 10001)、`erp-web`(healthy, 仅 `127.0.0.1:8080`)、`erp-postgres`(**原容器未重建**，ID/创建时间不变)。`deploy/smoke.sh` 5/5（web `/healthz`、`/api/health` 反代、SPA fallback、登录、鉴权）。容器内 `alembic current` = `0007_forecast_replenishment (head)`、二次 seed 幂等。`/root/dsh/server-health.sh` 改动前 44/0/0 PASS → 改动后 46/0/0 PASS（+2 为新增容器）。
- **回滚**：`git revert <本次提交>`；停止栈 `make down`（保留卷）；彻底移除 `cd deploy && docker compose down -v`（删数据，需确认）。
- **备注**：本切片不引入 Locust/Redis/Celery；性能测试与 LSTM 对比属 M7 后续子切片。本机 Docker Hub 不可达，构建用 `docker.m.daocloud.io` 预拉基础镜像并 retag；Dockerfile 提供可选 `PIP_INDEX_URL`/`NPM_REGISTRY` 构建参数（默认官方源，`deploy/.env` 可覆盖）。

## 2026-09-19 · 系统测试 + Locust 性能测试（M7 子切片 2）

- **改动**：
  - 新增 `backend/tests/test_system.py`：功能（登录→请购→提交→审批→转采购订单→到货→提交→验收→入库过账→结存/流水/对账）、接口（统一响应 `{code,message,data,trace_id}`、`X-Trace-Id`/`X-Process-Time-Ms`、OpenAPI 可发现、404/422 也走同一包装）、权限（匿名 401、只读 403/10403、管理员 200）各一条。
  - 新增 `perf/`（项目内隔离）：`locustfile.py`（登录一次 + 只读 GET，`name=` 归并，不写业务表）、`requirements.txt`（locust>=2.32,<3）、`README.md`（端口约定/运行方式/参考基线）。
  - `Makefile` 新增 `perf-venv`、`perf`（headless，默认 `127.0.0.1:8000`，`HOST/USERS/RATE/RUN_TIME` 可覆盖）。
- **依赖**：新增 **Locust**（仅性能场景；放独立 `perf/.venv`，不进后端运行/测试环境、不进 `make verify`）。理由：M7 方案指定 Locust；其 gevent/flask 等依赖不应污染后端 venv。
- **原因**：`docs/progress.md`"下一步" M7 子切片 —— 补系统测试与可复现性能测试。
- **验证**：`make verify` 绿且 0 skip（后端 **64 passed** = 原 61 + 系统测试 3；前端 lint；ml 58 passed；迁移链 1455 行；不变量通过）。`make perf HOST=http://127.0.0.1:8000 USERS=10 RATE=5 RUN_TIME=20s` → **200 请求 / 0 失败**，聚合中位数 11ms、P95 340ms；`POST /auth/login` avg 587ms（bcrypt 预期）。
- **回滚**：`git revert <本次提交>`；`rm -rf perf/.venv`。
- **备注**：性能场景为**只读相对基线**（回归对比用），非容量结论；Locust headless 不占端口。

