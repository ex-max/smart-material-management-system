# ERP 后端镜像：python:3.12-slim + uvicorn，非 root 运行。
# 构建上下文 = 仓库根目录（见 deploy/docker-compose.yml 的 build.context: ..）。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 非 root 运行账户（uid 10001，无登录 shell）
RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 --user-group app

# 可选镜像源（默认官方源；中国网络下可用 deploy/.env 的 PIP_INDEX_URL 覆盖加速）
ARG PIP_INDEX_URL=

# 先装依赖（pyproject + app 源码）以利用构建缓存；再拷贝迁移与脚本
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+--index-url "$PIP_INDEX_URL"} .

COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts
COPY deploy/backend-entrypoint.sh /usr/local/bin/backend-entrypoint.sh
# 附件落盘目录（挂载命名卷；先建好并归属 app，命名卷首次挂载会继承该所有权）
RUN mkdir -p /app/data/attachments && chmod 0755 /usr/local/bin/backend-entrypoint.sh && chown -R app:app /app

USER app
EXPOSE 8000

# 容器内健康检查（不依赖 curl）
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=6 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/backend-entrypoint.sh"]
