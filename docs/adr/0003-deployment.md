# ADR-0003 部署拓扑：单机 Docker Compose + 容器内 nginx

- 状态：已接受
- 日期：2026-09-19
- 关联：M7（工程化 —— Docker 一键部署）

## 背景

毕设系统此前只有"本地开发"运行方式（后端 `make serve`、前端 Vite dev、数据库独立 PG 容器）。
答辩与交付需要一个**可复现的一键部署**：一条命令起 web + api + db，且不影响这台服务器上
其他既有服务。方案 M7 要求容器化、迁移/seed 自动化、文档齐全。

约束来自 `AGENTS.md` 第六节与 `server-ops` 技能：项目内隔离、仅监听 `127.0.0.1`、
不动既有容器/卷、不引入不必要的中间件。

## 决策

采用**单机 Docker Compose**（`deploy/docker-compose.yml`，项目名 `erp`）：

- **web**：前端多阶段构建（`node:20-slim` 构建 → `nginx:1.27-alpine` 托管），
  容器内 nginx 提供静态资源、`/api` 反代到 `api:8000`、Vue Router history fallback。
  仅宿主 `127.0.0.1:${ERP_WEB_PORT:-8080}`。
- **api**：FastAPI + uvicorn，`python:3.12-slim`，非 root（uid 10001），
  **不映射宿主端口**；入口脚本 = 等库 → `alembic upgrade head` → 幂等 `scripts.seed` → uvicorn。
- **db**：沿用独立 `postgres:16-alpine`（`127.0.0.1:5433`，独立卷 `erp_erp-pgdata`）。
- 依赖顺序用 `depends_on: condition: service_healthy` + 各服务 healthcheck；
  网络用 compose 默认 bridge `erp_default`（项目级隔离），不新增外部网络。

## 理由

- **与已有环境一致**：数据库已是 compose 容器；沿用默认网络即可让 api/web 通过服务名互访，
  且不改变 `db` 服务定义 → 既有容器与卷不会被重建（避免停/删既有容器）。
- **单一入口、最小暴露**：只有 web 监听回环端口，业务 API 与数据库都不对公网暴露，
  契合"仅 127.0.0.1"与服务器安全边界。
- **不引入 Redis/Celery**：当前无异步任务/缓存需求；避免为部署增加无谓依赖（答辩可解释）。
- **迁移与初始化内聚**：把 `alembic upgrade head` + 幂等 seed 放进容器入口，
  "一键部署"真正一键，且重复执行安全。

## 备选与否决

- **宿主机 nginx + systemd 裸跑**：会改到宿主 nginx/系统服务（server-ops 红线），
  且与本机宝塔站点耦合；否决。
- **Kubernetes / docker swarm**：单机毕设过度设计；否决。
- **引入 Redis/Celery 做启动编排或异步**：当前无此需求；否决（如后续需要再单独 ADR）。
- **前端只 COPY 宿主预构建 dist**：不可复现、`dist/` 不进 git；否决，改为镜像内多阶段构建。

## 影响

- 新增 `deploy/backend.Dockerfile`、`deploy/frontend.Dockerfile`、`deploy/nginx/default.conf`、
  `deploy/backend-entrypoint.sh`、根 `.dockerignore`；`make up/down/ps/logs/seed` 作为入口。
- 部署拓扑、端口、连接串、迁移/seed/回滚写进 `deploy/README.md` 与 `deploy/.env.example`。
- 新增长期容器 `erp-api` / `erp-web`（及原 `erp-postgres`）纳入服务器 health 清单与
  `CHANGELOG-ops.md`；仅回环暴露，不影响宿主其他服务。
- 性能/系统测试（Locust 方案）与 LSTM 对比不在本 ADR 范围，属 M7 后续子切片。
