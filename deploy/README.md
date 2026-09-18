# deploy —— 本地开发依赖

## PostgreSQL（独立实例，仅在需要验证 PG 行为时启动）

本项目目标库为 PostgreSQL；测试默认用 SQLite 内存库。需要验证 PG 专有行为
（jsonb、部分唯一索引、`COALESCE` 表达式唯一索引、timestamptz）时启动本实例：

```bash
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml ps
```

- 连接串：`postgresql+psycopg://erp:erp@127.0.0.1:5433/erp`（与 `backend/.env.example` 一致）
- 仅监听 **127.0.0.1:5433**，不对外暴露；独立卷 `erp_erp-pgdata`，不影响宿主其他容器。
- 停止（不删数据）：`docker compose -f deploy/docker-compose.yml stop`
- 彻底移除（含卷，需确认）：`docker compose -f deploy/docker-compose.yml down -v`

> 运维背景见 `/root/dsh/CHANGELOG-ops.md`；禁止影响 halo / forgejo / forgejo-db / new-api-* 等既有服务。
