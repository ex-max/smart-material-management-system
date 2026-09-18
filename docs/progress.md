# 项目进度（每个会话开工先读这里，收尾必须更新）

> 规则：**"下一步"永远只写一条**（下一个会话直接照做）；"已知坑"只增不删（删要写原因）。

## 当前状态

- **里程碑**：M1 系统设计（数据库设计：主数据 + 采购 + 库存作业 已完成；余下四组待补）
- **更新时间**：2026-09-18

## 已完成

- [x] 项目骨架（backend / frontend / ml / deploy / docs / scripts）
- [x] `AGENTS.md` 工作约定（已验证会被 DSH 自动加载）
- [x] `make verify` 质量门禁（当前全绿，模块落地后自动变严）
- [x] ADR-0001 技术栈选型
- [x] git 仓库初始化 + 首次提交
- [x] **M1-a 数据库设计**：`docs/db-schema.md`（主数据 6 + 采购 6 + 库存作业 9 = **21 张表**；字段/类型/约束/索引/关系 + 状态机 + 单号规则 + E-R + 不变量落点）

## 进行中

- [ ] M1-b：补其余四组表设计（组织与权限 6、台账与统计 5、预测与决策 6、系统 3），并补 `inventory` / `inventory_transaction` 字段与对账口径

## 下一步（只做这一条）

**M1-b：补全数据库设计剩余四组** —— 在 `docs/db-schema.md` 追加
**组织与权限（6）+ 台账与统计（5）+ 预测与决策（6）+ 系统（3）= 20 张表**：
`inventory` / `inventory_transaction` 的字段与粒度（material×warehouse×batch_id）
必须与 `docs/db-schema.md` 第 8 节"接口契约"一致，并写明"流水汇总 == 结存"的对账 SQL 口径；
同时消化 §9 的开放问题（Q1 users 命名、Q2 非批次默认批次、Q3 部门主数据等）。

## 已知坑 / 未决问题

| 项 | 说明 | 状态 |
|---|---|---|
| 库存余额一致性 | 设计口径已定：结存粒度 = 物资×仓库×批次；非批次物资用系统默认批次；余额只由流水推导 + 同事务更新 + 对账任务。见 `docs/db-schema.md` §5.9 / §7 | 设计已冻结，M2 实现并跑对账 |
| 单据状态机 | 设计已定：全局 6 态（DRAFT/PENDING/APPROVED/IN_PROGRESS/COMPLETED/CANCELLED），仅请购单有审批（单级），迁移集中在 `core/state_machine.py`。见 `docs/db-schema.md` §1.6 | 设计已冻结，M2 实现 |
| 表数口径 | 方案写"约 36"，按其示例相加为 39；本次到货/调拨拆头行后全库预计 41。若页码预算吃紧，优先砍系统组而非业务表。见 `docs/db-schema.md` §0.3 | 待评审确认 |
| 非批次物资默认批次 | 建议 `batch_no='__DEFAULT__'` + `is_default`，使 batch_id 非空、唯一约束与对账口径统一；若改可空需 COALESCE 表达式索引 | 待评审确认（Q2） |
| users 表命名 | 组织与权限组建 `users` 而非 `user`（PostgreSQL 保留字 + 复数约定） | 待 M1-b 确认（Q1） |
| 部门主数据 | 方案无 dept 表，暂用 `dept_name` 文本字段 | 待定（Q3） |
| 预测与业务的边界 | ML 只读业务库、只写 `forecast_*` 与建议表 | 已写入 AGENTS.md |
| 数据生成器参数 | Bernoulli–Gamma / 对数正态提前期等参数待冻结 | M3 前定稿 |
| 服务水平定义 | CSL 还是 Fill Rate？**全程必须一致** | M5 前定稿 |

## 对账状态（库存相关改动必填）

| 日期 | 对账项 | 结果 |
|---|---|---|
| 2026-09-18 | M1-a 库存表设计口径：结存 = 物资×仓库×批次；`SUM(inventory_batch.quantity)` 按 (material, warehouse) 汇总须 == `inventory.quantity`；`inventory_batch` 汇总须 == `inventory_transaction` 汇总 | 设计已冻结；库存模块未实现，尚无可跑数据（M2 实现后跑对账） |
