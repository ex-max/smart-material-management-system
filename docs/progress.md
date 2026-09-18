# 项目进度（每个会话开工先读这里，收尾必须更新）

> 规则：**"下一步"永远只写一条**（下一个会话直接照做）；"已知坑"只增不删（删要写原因）。

## 当前状态

- **里程碑**：M2 进行中 —— **M2-a 采购单据 + 状态机、M2-b 到货→入库→库存流水已完成**；下一步 M2-c 出库/调拨/盘点
- **更新时间**：2026-09-18

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

## 进行中

- [ ] 无

## 下一步（只做这一条）

**M2-c：出库 / 调拨 / 盘点单据 + 过账（后端）** —— 落地 `docs/db-schema.md` §5.3–§5.8：
新增 `outbound_order`/`outbound_item`、`transfer_order`/`transfer_item`、`stocktake_order`/`stocktake_item` ORM/迁移，
实现出库/调拨/盘点 `DRAFT→IN_PROGRESS→COMPLETED` 过账：出库锁结存并校验可用量（禁止超卖、可指定批次）、
调拨两仓各写 TRANSFER_OUT/TRANSFER_IN 流水、盘点按差异写 STOCKTAKE_GAIN/LOSS；作废已过账单据产生
`REVERSAL` 反向流水（不改/删历史流水）；补并发与对账测试，扩展 `scripts/check_invariants.py` 的库存检查。

## 已知坑 / 未决问题

| 项 | 说明 | 状态 |
|---|---|---|
| 运行库实例 | 已起独立 PG16 容器（`deploy/docker-compose.yml`，仅 127.0.0.1:5433）。真库验证：迁移 upgrade/downgrade 可逆、`jsonb`、`postgresql_where` 部分唯一索引、`COALESCE` 表达式唯一索引；测试支持 `ERP_TEST_DATABASE_URL` 对 PG 跑（34 passed） | 已解决（2026-09-18） |
| 本机 Python 环境 | 系统缺 `python3-venv`，venv 用 `--without-pip` + get-pip 引导 | 已解决（backend/README.md） |
| 单据状态机 | 已实现：`core/state_machine.py` 单一事实来源（全局 6 态 + 7 类单据迁移边 + 权限码；仅请购单审批）；`apply_transition` 为唯一写 status 入口 | M2-a 完成 |
| 到货→入库联动 | 已实现：验收通过生成入库单，过账写流水并回写 PO 到货数量/状态 | M2-b 完成 |
| 领域不变量脚本 | `scripts/check_invariants.py`：状态机结构 + 权限码 + service 不直改 status + 库存只由 `service/inventory.py` 过账且必须写流水（verify 用 venv python 跑） | M2-b 完成 |
| 操作日志写入 | `operation_log` 表已建，中间件写日志逻辑未实现 | 待后续切片 |
| 库存余额一致性 | `inventory` = 物资×仓库汇总、`inventory_batch` = 批次明细、`inventory_transaction` 为唯一真值源；已实现过账与 `GET /inventory/reconcile`（§14 三条+守卫），测试断言流水汇总 == 结存 | M2-b 已实现并跑通（SQLite+PG） |
| 已过账单据红冲 | 冻结的状态机规定入库/出库等仅未过账可作废，故 M2-b 无 `REVERSAL` 反向通道；红冲随出库/盘点一起实现 | M2-c 实现 |
| 表数口径 | 全库 **41 张**（§2），方案写"约 36" | 已确认（采纳建议） |
| users/部门/默认批次 | `users` 复数命名、`dept_name` 文本、非批次用 `__DEFAULT__` 批次 | 已确认（Q1–Q3 采纳建议） |
| M1-b 开放问题 | M1B-Q1–Q7 见 `docs/db-schema.md` §15 | 已确认（采纳建议） |
| 预测与业务的边界 | ML 只读业务库、只写 `forecast_*` 与建议表 | 已写入 AGENTS.md |
| 数据生成器参数 | Bernoulli–Gamma / 对数正态提前期等参数待冻结 | M3 前定稿 |
| 服务水平定义 | CSL 还是 Fill Rate？**全程必须一致** | M5 前定稿（`service_level_type` 承载） |

## 对账状态（库存相关改动必填）

| 日期 | 对账项 | 结果 |
|---|---|---|
| 2026-09-18 | M1-a 库存表设计口径：批次结存 = 物资×仓库×批次（`inventory_batch`）；汇总结存 = 物资×仓库（`inventory`） | 设计已冻结；库存模块未实现，无可跑数据 |
| 2026-09-18 | M1-b 对账 SQL 口径：`docs/db-schema.md` §14 四条检查 | 设计已冻结；M2 实现过账后执行 |
| 2026-09-18 | M2-a 采购单据（PR/PO/RCV）未写 `inventory` / `inventory_transaction`；到货→入库→流水联动在 M2-b | 不涉及库存过账，无对账数据；口径不变 |
| 2026-09-18 | M2-b 库存过账对账：①批次汇总 == 结存 ②流水汇总 == 结存 ③批次级流水 == 批次结存 ④无负结存/锁定超结存 | `reconcile.ok=true`；覆盖默认批次与批次物资；SQLite + PostgreSQL 双跑 34 passed |
