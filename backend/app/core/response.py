from contextvars import ContextVar
from typing import Any

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data, "trace_id": trace_id_var.get()}


def fail(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data, "trace_id": trace_id_var.get()}
