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
