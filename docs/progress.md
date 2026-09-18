# 项目进度（每个会话开工先读这里，收尾必须更新）

> 规则：**"下一步"永远只写一条**（下一个会话直接照做）；"已知坑"只增不删（删要写原因）。

## 当前状态

- **里程碑**：M1 完成（系统设计 + 后端骨架 + 权限/登录 + 主数据）。下一步进入 **M2 采购模块**
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

## 进行中

- [ ] 无

## 下一步（只做这一条）

**M2-a：采购单据 + 状态机（后端）** —— 实现 `docs/db-schema.md` §4 采购组：
新增 `core/state_machine.py`（全局 6 态 + 仅请购单单级审批，单一事实来源），
落地 `purchase_requisition`/`pr_item`、`purchase_order`/`po_item`/`supplier_delivery`(_item) 的 ORM/迁移/CRUD，
实现"请购单 → 提交 → 审批（`purchase:approve`）→ 转采购订单"、单据号生成（PR/PO-YYYYMMDD-####）、
状态迁移校验与权限拒绝测试。**到货验收 → 入库 → 写 `inventory_transaction` 的联动放 M2-b。**

## 已知坑 / 未决问题

| 项 | 说明 | 状态 |
|---|---|---|
| 运行库实例 | 本机**没有 PostgreSQL**；测试用 SQLite 内存库，目标库仍是 PG。PG 专有行为（jsonb、部分唯一索引 `postgresql_where`、`COALESCE` 表达式唯一索引）待真库验证 | 待办（deploy/ 起独立实例，建议 127.0.0.1:5433） |
| 本机 Python 环境 | 系统缺 `python3-venv`，venv 用 `--without-pip` + get-pip 引导 | 已解决（backend/README.md） |
| 单据状态机 | 设计已冻结（全局 6 态 + 仅请购单审批）；`core/state_machine.py` **尚未创建** | M2-a 实现 |
| 操作日志写入 | `operation_log` 表已建，中间件写日志逻辑未实现 | 待后续切片 |
| 库存余额一致性 | `inventory` = 物资×仓库汇总、`inventory_batch` = 批次明细、`inventory_transaction` 为唯一真值源 | 设计已冻结，M2 实现并跑对账 |
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
