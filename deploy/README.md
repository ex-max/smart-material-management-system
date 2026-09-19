# deploy —— 一键部署（Docker Compose）

本项目在**单机 Docker Compose** 内隔离运行，不碰宿主既有服务（halo / forgejo /
forgejo-db / new-api-* / 宝塔 nginx / MySQL）。运维背景与变更记录见
`/root/dsh/CHANGELOG-ops.md`。

## 拓扑

```
浏览器 ──► 127.0.0.1:<ERP_WEB_PORT>(默认 8080)
             │  web 容器：nginx 静态托管 frontend/dist
             │             /api/* 反向代理 ──► api:8000
             └─► api 容器：uvicorn(app.main:app)，启动时等库→alembic upgrade head→幂等 seed
                    │
                    └─► db 容器：postgres:16-alpine（仅 127.0.0.1:5433 对宿主暴露，供本地调试）
```

- **web**：唯一对宿主暴露的入口，**仅 127.0.0.1**；提供 SPA history fallback 与 `/healthz`。
- **api**：不对宿主暴露任何端口，只在项目网络 `erp_default` 内由 web 反代访问。
- **db**：对宿主暴露 `127.0.0.1:5433`（沿用原有独立实例，供本地/测试直连）。
- 卷：`erp_erp-pgdata`（独立，不与其他项目共享）；网络：`erp_default`（项目默认 bridge，隔离）。

## 一键命令

```bash
# 构建并启动（web + api + db），首次会构建镜像
make up

# 查看状态 / 日志
make ps
make logs

# 停止（保留数据卷，不删数据）
make down

# 部署冒烟：web / 反代 / SPA fallback / 登录 / 鉴权
./deploy/smoke.sh                 # 默认 http://127.0.0.1:8080
```

> 也可以直接用 compose：`cd deploy && docker compose up -d --build`。
> 配置放在 `deploy/.env`（从 `deploy/.env.example` 复制，不进 git）。

## 端口与访问方式

| 服务 | 容器内 | 宿主 | 访问 |
|---|---|---|---|
| web (nginx) | 80 | `127.0.0.1:${ERP_WEB_PORT:-8080}` | http://127.0.0.1:8080 |
| api (uvicorn) | 8000 | 不暴露 | 仅经 web 的 `/api` 反代 |
| db (postgres) | 5432 | `127.0.0.1:5433` | 直连调试 |

改端口：编辑 `deploy/.env` 的 `ERP_WEB_PORT` 后 `make down && make up`。
**只允许 127.0.0.1**；如需对外，请走已有 nginx 站点另行加反代（需先与用户确认，本切片未做）。

## 连接串与配置

- 容器内（api → db）：`postgresql+psycopg://erp:erp@db:5432/erp`（compose 注入，不落盘）
- 宿主/本地调试：`postgresql+psycopg://erp:erp@127.0.0.1:5433/erp`（与 `backend/.env.example` 一致）
- 其他配置：`deploy/.env.example`（`ERP_JWT_SECRET`、管理员、CORS、端口）。

## 迁移与初始化

- **启动时自动执行**：后端入口先等待 db 健康，再 `alembic upgrade head`，然后
  `python -m scripts.seed`（幂等，重复执行安全），最后启动 uvicorn。
- 手动执行：

```bash
cd deploy
docker compose exec api alembic upgrade head          # 手动迁移
docker compose exec api python -m scripts.seed        # 手动 seed（幂等）
docker compose exec api alembic current               # 查看当前版本
```

当前迁移版本：`0007_forecast_replenishment`。

## 回滚

```bash
# 1) 停服务、保留数据（可随时 make up 回来）
make down

# 2) 回到旧镜像/旧代码：git checkout <上一个 commit> 后 make up --build
#    或直接停掉本项目的三个容器（不影响其他服务）：
cd deploy && docker compose stop

# 3) 彻底移除本项目资源（含数据卷）——不可逆，先与用户确认：
#    cd deploy && docker compose down -v
```

## 影响与边界

- **对其他服务无影响**：独立 compose 项目（`erp`）、独立卷、独立网络；不 `stop/rm/prune`
  既有容器，不动既有 volume。
- **不改宿主 nginx**：本项目的 nginx 只存在于 web 容器内，仅回环端口。
- **ML 边界**：镜像只含 backend/frontend；不打包 `ml/`，不引入 Redis/Celery。
- **资源**：构建与运行都在本机；镜像 `erp-api:local` / `erp-web:local`。

## 历史说明

本目录最初只有独立 PostgreSQL（`deploy/docker-compose.yml` 仅 `db` 服务），
M7 一键部署在其上增加 `api`/`web` 两个服务，**`db` 服务定义保持不变**，
因此既有容器 `erp-postgres` 与数据卷 `erp_erp-pgdata` 不会被重建。
