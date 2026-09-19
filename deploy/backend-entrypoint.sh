#!/usr/bin/env sh
# 后端容器入口：等库就绪 → alembic upgrade head → 幂等 seed → uvicorn。
set -eu

echo "[entrypoint] 等待数据库..."
python - <<'PY'
import os
import sys
import time

from sqlalchemy import create_engine, text

url = os.environ.get("ERP_DATABASE_URL", "")
if not url:
    print("[entrypoint] 缺少 ERP_DATABASE_URL", file=sys.stderr)
    sys.exit(1)

engine = create_engine(url, pool_pre_ping=True)
for attempt in range(1, 31):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[entrypoint] 数据库就绪（第 %d 次尝试）" % attempt)
        break
    except Exception as exc:  # noqa: BLE001
        print("[entrypoint] 数据库未就绪（第 %d 次）：%s" % (attempt, exc))
        time.sleep(2)
else:
    print("[entrypoint] 数据库等待超时", file=sys.stderr)
    sys.exit(1)
engine.dispose()
PY

echo "[entrypoint] 应用迁移：alembic upgrade head"
alembic upgrade head

echo "[entrypoint] 初始化 RBAC/管理员（幂等）：python -m scripts.seed"
python -m scripts.seed

echo "[entrypoint] 启动 uvicorn（容器内 0.0.0.0:8000，不对宿主暴露）"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
