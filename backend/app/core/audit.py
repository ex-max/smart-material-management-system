"""审计上下文提取：把一次请求映射成 operation_log 行的非敏感字段（§10.6）。

只提炼路径/方法/状态/耗时/操作人等审计所需上下文，**绝不**读取：
- 请求体（也就不会碰到 password 等字段）；
- Authorization / token / cookie；
- query string（防止 token/一次性口令进日志）。

所有字符串按表列宽截断，保证写入不会因超长而失败。
"""

from __future__ import annotations

from starlette.requests import Request

# 不审计的路径前缀（健康检查 / OpenAPI 文档）
SKIP_LOG_PREFIXES = ("/api/health", "/api/docs", "/api/redoc", "/api/openapi.json")

# 路径前缀 -> module（取最长匹配；用于日志分层统计）
_MODULE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/api/v1/material-categories", "material"),
    ("/api/v1/materials", "material"),
    ("/api/v1/units", "material"),
    ("/api/v1/suppliers", "material"),
    ("/api/v1/warehouses", "material"),
    ("/api/v1/locations", "material"),
    ("/api/v1/purchase-requisitions", "purchase"),
    ("/api/v1/purchase-orders", "purchase"),
    ("/api/v1/supplier-deliveries", "purchase"),
    ("/api/v1/inbound-orders", "inventory"),
    ("/api/v1/outbound-orders", "inventory"),
    ("/api/v1/transfer-orders", "inventory"),
    ("/api/v1/stocktake-orders", "inventory"),
    ("/api/v1/inventory", "inventory"),
    ("/api/v1/stock-alerts", "inventory"),
    ("/api/v1/forecast-runs", "forecast"),
    ("/api/v1/demand-series-meta", "forecast"),
    ("/api/v1/model-registry", "forecast"),
    ("/api/v1/replenishment-policies", "replenishment"),
    ("/api/v1/replenishment-suggestions", "replenishment"),
    ("/api/v1/auth", "auth"),
    ("/api/v1/users", "user"),
    ("/api/v1/roles", "role"),
    ("/api/v1/operation-logs", "system"),
)

# 与 §10.6 列宽对齐
_MAX_LENGTHS = {
    "username": 64,
    "module": 32,
    "action": 64,
    "resource_type": 64,
    "resource_id": 64,
    "method": 8,
    "path": 255,
    "ip": 45,
    "user_agent": 255,
    "request_id": 64,
    "error_code": 16,
}


def should_audit(request: Request) -> bool:
    """健康检查/文档与 CORS 预检不落库，避免噪声。"""
    if request.method == "OPTIONS":
        return False
    path = request.url.path
    return not any(path == prefix or path.startswith(prefix + "/") for prefix in SKIP_LOG_PREFIXES)


def module_for_path(path: str) -> str | None:
    for prefix, module in sorted(_MODULE_PREFIXES, key=lambda item: -len(item[0])):
        if path == prefix or path.startswith(prefix + "/"):
            return module
    return None


def resource_type_for_path(path: str) -> str | None:
    parts = [segment for segment in path.split("/") if segment]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2]
    return None


def resource_id_from_params(path_params: dict) -> str | None:
    for key, value in path_params.items():
        if key == "id" or key.endswith("_id"):
            return str(value)
    for value in path_params.values():
        return str(value)
    return None


def client_ip(request: Request) -> str | None:
    """经本项目 nginx 反代时优先取代理注入的真实 IP，其次直连对端。"""
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else None


def _clip(value, field: str):
    if value is None:
        return None
    text = str(value)
    limit = _MAX_LENGTHS.get(field)
    return text[:limit] if limit else text


def build_audit_fields(
    request: Request,
    *,
    status_code: int,
    error_code: str | None,
    duration_ms: int,
    request_id: str,
) -> dict:
    """组装 OperationLog 的可写字段（纯函数，便于单测）。"""
    current = getattr(request.state, "current_user", None) or {}
    route = request.scope.get("route")
    action = getattr(route, "name", None) or "%s %s" % (request.method, request.url.path)
    failed = status_code >= 400
    return {
        "user_id": current.get("id"),
        "username": _clip(current.get("username"), "username"),
        "module": _clip(module_for_path(request.url.path), "module"),
        "action": _clip(action, "action"),
        "resource_type": _clip(resource_type_for_path(request.url.path), "resource_type"),
        "resource_id": _clip(resource_id_from_params(request.path_params), "resource_id"),
        "method": _clip(request.method, "method"),
        "path": _clip(request.url.path, "path"),
        "ip": _clip(client_ip(request), "ip"),
        "user_agent": _clip(request.headers.get("user-agent"), "user_agent"),
        "request_id": _clip(request_id, "request_id"),
        "result": "FAIL" if failed else "SUCCESS",
        "error_code": _clip(error_code, "error_code"),
        "duration_ms": duration_ms,
        "detail": {"status_code": status_code} if failed else None,
    }
