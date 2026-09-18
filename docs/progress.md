# 项目进度（每个会话开工先读这里，收尾必须更新）

> 规则：**"下一步"永远只写一条**（下一个会话直接照做）；"已知坑"只增不删（删要写原因）。

## 当前状态

- **里程碑**：M1 系统设计完成（全库数据库设计 **41 张表** 已产出，待评审确认；下一步进入后端骨架与主数据/权限实现）
- **更新时间**：2026-09-18

## 已完成

- [x] 项目骨架（backend / frontend / ml / deploy / docs / scripts）
- [x] `AGENTS.md` 工作约定（已验证会被 DSH 自动加载）
- [x] `make verify` 质量门禁（当前全绿，模块落地后自动变严）
- [x] ADR-0001 技术栈选型
- [x] git 仓库初始化 + 首次提交
- [x] **M1-a 数据库设计（业务三组 21 张）**：`docs/db-schema.md` 主数据 6 + 采购 6 + 库存作业 9
- [x] **M1-b 数据库设计（其余四组 20 张）**：组织与权限 6 + 台账与统计 5 + 预测与决策 6 + 系统 3；补 `inventory`/`inventory_transaction` 字段与 §14 对账 SQL 口径；**全库 41 张**
- [x] GitHub 远程仓库接入（`origin` = https://github.com/ex-max/smart-material-management-system，SSH Deploy Key；规则见 `AGENTS.md` 第七节）

## 进行中

- [ ] 无

## 下一步（只做这一条）

**M1-c：后端骨架 + 主数据/权限/登录** —— 在 `backend/` 按约定分层（api→service→repository→model）
搭起 FastAPI 工程与 Alembic，落地 `docs/db-schema.md` 的 **§10 组织与权限 + §3 主数据**
（users/roles/permissions/RBAC、material_category/material/unit/warehouse/location/supplier）；
`make verify` 从"跳过"转为真正检查（ruff + pytest + `alembic upgrade head --sql`）。

## 已知坑 / 未决问题

| 项 | 说明 | 状态 |
|---|---|---|
| 库存余额一致性 | `inventory` = 物资×仓库汇总、`inventory_batch` = 批次明细、`inventory_transaction` 为唯一真值源；SUM(批次)==SUM(流水)==inventory。见 `docs/db-schema.md` §11/§14 | 设计已冻结，M2 实现并跑对账 |
| 单据状态机 | 全局 6 态 + 仅请购单审批（单级），迁移集中 `core/state_machine.py`。见 §1.6 | 设计已冻结，M2 实现 |
| 表数口径 | 全库 **41 张**已落地（§2）。方案写"约 36"，差异来自示例口径 + 到货/调拨头行拆分。页码吃紧优先砍系统组 | 已确认（采纳建议） |
| 非批次物资默认批次 | `batch_no='__DEFAULT__'` + `is_default`，batch_id 非空 | 已确认（Q2，采纳建议） |
| users 表命名 | 用 `users` 而非 `user`（PostgreSQL 保留字） | 已确认（Q1，采纳建议） |
| 部门主数据 | 方案无 dept 表，暂用 `dept_name` 文本 | 已确认（Q3，采纳建议） |
| M1-b 开放问题 | M1B-Q1–Q7（数据范围权限 / 服务水平口径 CSL vs Fill Rate / 价格历史 / 快照保留期 / 附件存储 / 日志归档 / dict 边界）见 `docs/db-schema.md` §15，均附建议 | 待评审 |
| 预测与业务的边界 | ML 只读业务库、只写 `forecast_*` 与建议表 | 已写入 AGENTS.md |
| 数据生成器参数 | Bernoulli–Gamma / 对数正态提前期等参数待冻结 | M3 前定稿 |
| 服务水平定义 | CSL 还是 Fill Rate？**全程必须一致** | M5 前定稿（表中已用 `service_level_type` 承载） |

## 对账状态（库存相关改动必填）

| 日期 | 对账项 | 结果 |
|---|---|---|
| 2026-09-18 | M1-a 库存表设计口径：批次结存 = 物资×仓库×批次（`inventory_batch`）；汇总结存 = 物资×仓库（`inventory`） | 设计已冻结；库存模块未实现，无可跑数据 |
| 2026-09-18 | M1-b 对账 SQL 口径：`docs/db-schema.md` §14 四条检查（批次汇总==inventory、流水汇总==inventory、流水==批次、禁止负结存） | 设计已冻结；M2 实现过账后执行 |
