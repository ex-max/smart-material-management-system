"""通用响应/分页模型（供 FastAPI response_model 使用，前端类型由 OpenAPI 生成）。"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int
    message: str
    data: T | None = None
    trace_id: str = ""


class PageOut(BaseModel, Generic[T]):
    total: int
    items: list[T]
