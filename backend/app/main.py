import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.audit import build_audit_fields, should_audit
from app.core.config import get_settings
from app.core.errors import (
    E_BAD_REQUEST,
    E_CONFLICT,
    E_FORBIDDEN,
    E_INTERNAL,
    E_NOT_FOUND,
    E_UNAUTHORIZED,
    E_VALIDATION,
    BizError,
)
from app.core.response import fail, ok, trace_id_var
from app.service.operation_log import record_operation_log

_STATUS_TO_CODE = {
    400: E_BAD_REQUEST,
    401: E_UNAUTHORIZED,
    403: E_FORBIDDEN,
    404: E_NOT_FOUND,
    409: E_CONFLICT,
    422: E_VALIDATION,
    500: E_INTERNAL,
}

logger = logging.getLogger("app.audit")


def _emit_audit(request, *, status_code: int, error_code, duration_ms: int) -> None:
    """best-effort 审计：任何异常都不得影响主请求。"""
    try:
        record_operation_log(
            build_audit_fields(
                request,
                status_code=status_code,
                error_code=error_code,
                duration_ms=duration_ms,
                request_id=trace_id_var.get(),
            )
        )
    except Exception:  # pragma: no cover - 依赖真实故障路径
        logger.exception("操作日志记录失败（best-effort，已忽略）")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def audit_middleware(request, call_next):
        if not should_audit(request):
            return await call_next(request)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            _emit_audit(request, status_code=500, error_code=E_INTERNAL, duration_ms=duration_ms)
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        error_code = getattr(request.state, "error_code", None)
        if response.status_code >= 400 and error_code is None:
            error_code = _STATUS_TO_CODE.get(response.status_code)
        _emit_audit(request, status_code=response.status_code, error_code=error_code, duration_ms=duration_ms)
        return response

    @app.middleware("http")
    async def trace_middleware(request, call_next):
        tid = request.headers.get("X-Trace-Id") or uuid4().hex
        token = trace_id_var.set(tid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            trace_id_var.reset(token)
        response.headers["X-Trace-Id"] = tid
        response.headers["X-Process-Time-Ms"] = "%.1f" % ((time.perf_counter() - start) * 1000)
        return response

    @app.exception_handler(BizError)
    async def _biz_handler(request, exc: BizError):
        request.state.error_code = exc.code
        return JSONResponse(status_code=exc.http_status, content=jsonable_encoder(fail(exc.code, exc.message, exc.data)))

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request, exc: RequestValidationError):
        request.state.error_code = E_VALIDATION
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(fail(E_VALIDATION, "参数校验失败", exc.errors())),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request, exc: StarletteHTTPException):
        code = _STATUS_TO_CODE.get(exc.status_code, E_BAD_REQUEST)
        request.state.error_code = code
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(fail(code, str(exc.detail))))

    @app.exception_handler(Exception)
    async def _unhandled_handler(request, exc: Exception):
        request.state.error_code = E_INTERNAL
        return JSONResponse(status_code=500, content=jsonable_encoder(fail(E_INTERNAL, "服务器内部错误")))

    @app.get("/api/health", tags=["系统"])
    def health():
        return ok({"status": "up"})

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
