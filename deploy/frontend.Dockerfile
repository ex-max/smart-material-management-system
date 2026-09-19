# ERP 前端镜像：多阶段构建 —— node 构建静态资源 → nginx 托管 + /api 反代 + SPA fallback。
# 构建上下文 = 仓库根目录（见 deploy/docker-compose.yml 的 build.context: ..）。
# 用 debian 版 node（glibc）避免 alpine/musl 下 rollup/esbuild 可选依赖缺包问题。
FROM node:20-slim AS build

# 可选 npm 源（默认官方源；中国网络下可用 deploy/.env 的 NPM_REGISTRY 覆盖加速）
ARG NPM_REGISTRY=

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund ${NPM_REGISTRY:+--registry="$NPM_REGISTRY"}
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

# 项目内 nginx 站点配置（静态托管 + /api 反代 + history fallback）
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
