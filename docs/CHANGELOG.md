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




