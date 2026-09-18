from typing import Any

# 业务错误码分段（约定见 AGENTS / erp-conventions）：
# 1xxxx 通用、2xxxx 物资与主数据、3xxxx 采购、4xxxx 库存、5xxxx 预测与建议
E_OK = 0
E_BAD_REQUEST = 10001
E_UNAUTHORIZED = 10401
E_FORBIDDEN = 10403
E_NOT_FOUND = 10404
E_CONFLICT = 10409
E_VALIDATION = 10422
E_INTERNAL = 10500


class BizError(Exception):
    """业务异常：HTTP 状态码只表达协议层语义，业务结果看 code。"""

    def __init__(self, code: int, message: str, http_status: int = 400, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data


class Unauthorized(BizError):
    def __init__(self, message: str = "未认证或凭证已失效") -> None:
        super().__init__(E_UNAUTHORIZED, message, 401)


class Forbidden(BizError):
    def __init__(self, message: str = "无权限执行该操作") -> None:
        super().__init__(E_FORBIDDEN, message, 403)


class NotFound(BizError):
    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(E_NOT_FOUND, message, 404)


class Conflict(BizError):
    def __init__(self, message: str = "资源冲突") -> None:
        super().__init__(E_CONFLICT, message, 409)


class BadRequest(BizError):
    def __init__(self, message: str = "请求不合法") -> None:
        super().__init__(E_BAD_REQUEST, message, 400)
