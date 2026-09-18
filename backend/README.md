# backend/ —— FastAPI 业务服务

## 分层（AGENTS / erp-conventions）

| 目录 | 职责 |
|---|---|
| app/api/ | 路由：参数校验 + 权限依赖 + 调 service + 包装响应（不写业务逻辑） |
| app/service/ | 业务：事务边界、状态机、领域不变量 |
| app/repository/ | 数据：SQLAlchemy 查询 |
| app/model/ | ORM 实体 |
| app/schema/ | Pydantic DTO |
| app/core/ | 配置、安全、错误码、依赖 |
| alembic/ | 迁移 |
| scripts/seed.py | RBAC 参考数据 + 管理员账号（幂等） |
| tests/ | pytest |

## 环境

- Python >= 3.12（本机 3.13）；依赖见 pyproject.toml（ADR-0001 技术栈）。
- 本机若缺 python3-venv（ensurepip 不可用），可用：

~~~
python3 -m venv --without-pip .venv
curl -o /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py
.venv/bin/python /tmp/get-pip.py
.venv/bin/pip install -e ".[dev]"
~~~

## 命令（在 backend/ 下执行）

~~~
.venv/bin/python -m pytest -q        # 测试（当前用 SQLite 内存库）
.venv/bin/ruff check .               # lint
cp .env.example .env                 # 配置（.env 不进仓库）
.venv/bin/alembic upgrade head       # 建表（需要 PostgreSQL）
.venv/bin/python scripts/seed.py     # 初始化 RBAC + 管理员
.venv/bin/uvicorn app.main:app --reload --port 8000   # 本地起服务
~~~

根目录统一入口仍是 make verify / make test / make lint / make migrate / make serve。

## 数据库说明（重要）

- 目标库是 **PostgreSQL**（ADR-0001）；.env 的 ERP_DATABASE_URL 指向 PG。
- 已提供独立 PG16 实例：`docker compose -f deploy/docker-compose.yml up -d`
  （仅 127.0.0.1:5433，独立卷，**勿用机器上其他项目的库**）。
- 默认 `pytest` 用 **SQLite 内存库**（tests/conftest.py 覆盖 get_db）；要对真库跑：
  `ERP_TEST_DATABASE_URL=postgresql+psycopg://erp:erp@127.0.0.1:5433/erp .venv/bin/python -m pytest -q`。
- make verify 的迁移检查是**离线渲染**（alembic upgrade head --sql），不需要连接数据库。

## 已实现（M1-c ~ M2-b）

- 统一响应 {code, message, data, trace_id} + 业务错误码分段 + 全局异常处理 + 请求 trace_id
- JWT 登录；require_perm 依赖做接口级 RBAC（users/roles/permissions/user_role/role_permission）
- 用户创建/列表/详情/修改/分配角色；角色、权限查询
- 操作日志表（结构；写入逻辑在后续切片）
- 迁移 0001_init_org_auth（6 张表）

## 待实现

- 主数据模块：material_category / material / unit / warehouse / location / supplier
- 采购、库存作业、台账与统计、预测与决策、系统组
