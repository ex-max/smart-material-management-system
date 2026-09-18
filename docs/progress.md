# 项目进度（每个会话开工先读这里，收尾必须更新）

> 规则：**"下一步"永远只写一条**（下一个会话直接照做）；"已知坑"只增不删（删要写原因）。

## 当前状态

- **里程碑**：M1 系统设计完成；**后端已起步**（M1-c：骨架 + 组织权限/登录）。下一步 M1-d 主数据模块
- **更新时间**：2026-09-18

## 已完成

- [x] 项目骨架（backend / frontend / ml / deploy / docs / scripts）
- [x] `AGENTS.md` 工作约定（已验证会被 DSH 自动加载）
- [x] `make verify` 质量门禁
- [x] ADR-0001 技术栈选型
- [x] git 仓库初始化 + 首次提交 + GitHub 远程（`origin`，见 AGENTS 第七节）
- [x] **M1-a 数据库设计（业务三组 21 张）**：`docs/db-schema.md`
- [x] **M1-b 数据库设计（其余四组 20 张）**：全库 **41 张** + §14 对账 SQL
- [x] **M1-c 后端骨架 + 组织与权限/登录**：FastAPI 分层骨架、统一响应/错误码/trace_id、JWT 登录、`require_perm` 接口级 RBAC、用户 CRUD、迁移 `0001_init_org_auth`（6 张表）、`scripts/seed.py`、pytest 8 条

## 进行中

- [ ] 无

## 下一步（只做这一条）

**M1-d：主数据模块** —— 落地 `docs/db-schema.md` **§3 六张表**
（material_category / unit / material / warehouse / location / supplier）：
ORM + 迁移 + repository/service/schema/api（增删改查、停用、软删）+ service 单测与集成测试；
复用 M1-c 的 `require_perm`（权限码 `material:view/material:manage` 已在 `core/permissions.py`）。

## 已知坑 / 未决问题

| 项 | 说明 | 状态 |
|---|---|---|
| 运行库实例 | 本机**没有 PostgreSQL**；测试用 SQLite 内存库（`tests/conftest.py` 覆盖 get_db），目标库仍是 PG。Postgres 专有行为（jsonb、部分唯一索引 `postgresql_where`）待真库验证 | 待办（deploy/ 起独立实例，建议 127.0.0.1:5433，勿用其他项目库） |
| 本机 Python 环境 | 系统缺 `python3-venv`（ensurepip 不可用），venv 用 `--without-pip` + get-pip 引导；已装 fastapi/sqlalchemy/alembic/pydantic-settings/PyJWT/bcrypt/psycopg[pytest/httpx/ruff | 已解决（见 backend/README.md） |
| 操作日志写入 | `operation_log` 表已建，但中间件写日志的逻辑未实现（M1-c 只做结构） | 待后续切片 |
| 库存余额一致性 | `inventory` = 物资×仓库汇总、`inventory_batch` = 批次明细、`inventory_transaction` 为唯一真值源 | 设计已冻结，M2 实现并跑对账 |
| 单据状态机 | 全局 6 态 + 仅请购单审批（单级），迁移集中 `core/state_machine.py` | 设计已冻结，M2 实现 |
| 表数口径 | 全库 **41 张**（§2），方案写"约 36"；页码吃紧优先砍系统组 | 已确认（采纳建议） |
| 非批次物资默认批次 | `batch_no='__DEFAULT__'` + `is_default` | 已确认（Q2，采纳建议） |
| users 表命名 | 用 `users` 而非 `user` | 已确认（Q1，采纳建议） |
| 部门主数据 | 方案无 dept 表，暂用 `dept_name` 文本 | 已确认（Q3，采纳建议） |
| M1-b 开放问题 | M1B-Q1–Q7 见 `docs/db-schema.md` §15 | 已确认（采纳建议） |
| 预测与业务的边界 | ML 只读业务库、只写 `forecast_*` 与建议表 | 已写入 AGENTS.md |
| 数据生成器参数 | Bernoulli–Gamma / 对数正态提前期等参数待冻结 | M3 前定稿 |
| 服务水平定义 | CSL 还是 Fill Rate？**全程必须一致** | M5 前定稿（`service_level_type` 承载） |

## 对账状态（库存相关改动必填）

| 日期 | 对账项 | 结果 |
|---|---|---|
| 2026-09-18 | M1-a 库存表设计口径：批次结存 = 物资×仓库×批次（`inventory_batch`）；汇总结存 = 物资×仓库（`inventory`） | 设计已冻结；库存模块未实现，无可跑数据 |
| 2026-09-18 | M1-b 对账 SQL 口径：`docs/db-schema.md` §14 四条检查 | 设计已冻结；M2 实现过账后执行 |
