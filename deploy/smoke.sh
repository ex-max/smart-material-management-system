#!/usr/bin/env bash
# 部署冒烟测试（在宿主机执行）：验证 web 起点、/api 反代、SPA fallback、登录与鉴权接口。
# 用法：deploy/smoke.sh [http://127.0.0.1:8080]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8080}"
USER="${ERP_ADMIN_USERNAME:-admin}"
PASS="${ERP_ADMIN_PASSWORD:-admin123}"

pass=0
fail=0
ok()  { printf '  \033[32mok\033[0m    %s\n' "$1"; pass=$((pass + 1)); }
bad() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail + 1)); }

echo "== 部署冒烟：$BASE =="

# 1) web 健康端点
if [ "$(curl -fsS "$BASE/healthz" 2>/dev/null | tr -d '\r\n')" = "ok" ]; then
  ok "web /healthz"
else
  bad "web /healthz"
fi

# 2) /api 反代 → 后端健康
if curl -fsS "$BASE/api/health" 2>/dev/null | grep -q '"up"'; then
  ok "反代 /api/health"
else
  bad "反代 /api/health"
fi

# 3) SPA history fallback（未知路由回 index.html）
if curl -fsS "$BASE/replenishment" 2>/dev/null | grep -qi '<div id="app">'; then
  ok "SPA fallback /replenishment"
else
  bad "SPA fallback /replenishment"
fi

# 4) 登录（经反代）拿 token
LOGIN_JSON="$(curl -fsS -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}" 2>/dev/null || true)"
TOKEN="$(printf '%s' "$LOGIN_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["access_token"])' 2>/dev/null || true)"
if [ -n "$TOKEN" ]; then
  ok "登录 /api/v1/auth/login"
else
  bad "登录 /api/v1/auth/login"
fi

# 5) 带 token 访问受保护接口
if [ -n "$TOKEN" ] && curl -fsS "$BASE/api/v1/auth/me" -H "Authorization: Bearer $TOKEN" 2>/dev/null | grep -q '"username"'; then
  ok "鉴权 /api/v1/auth/me"
else
  bad "鉴权 /api/v1/auth/me"
fi

printf '\n== 结果：%d 通过 / %d 失败 ==\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
