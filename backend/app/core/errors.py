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

# 3xxxx 采购
E_PURCHASE_STATE = 30001
E_PURCHASE_NOT_EDITABLE = 30002

# 6xxxx 系统（字典/任务日志/附件）
E_DICT_DUPLICATE = 60001
E_TASK_LOG_STATE = 60002
E_ATTACHMENT_TYPE = 60003
E_ATTACHMENT_TOO_LARGE = 60004
E_ATTACHMENT_STORE = 60005


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


class InvalidState(BizError):
    """单据状态迁移不合法。"""

    def __init__(self, message: str = "单据状态不允许该操作") -> None:
        super().__init__(E_PURCHASE_STATE, message, 409)


class NotEditable(BizError):
    """单据在当前状态下不允许修改。"""

    def __init__(self, message: str = "单据在当前状态下不可修改") -> None:
        super().__init__(E_PURCHASE_NOT_EDITABLE, message, 409)


class DictDuplicate(BizError):
    """字典项 (dict_type, dict_key) 冲突。"""

    def __init__(self, message: str = "字典键已存在") -> None:
        super().__init__(E_DICT_DUPLICATE, message, 409)


class TaskLogState(BizError):
    """任务日志状态迁移不合法（已终态不可再改）。"""

    def __init__(self, message: str = "任务日志已结束，不可再更新") -> None:
        super().__init__(E_TASK_LOG_STATE, message, 409)


class AttachmentTypeNotAllowed(BizError):
    """附件类型不在允许清单内。"""

    def __init__(self, message: str = "不允许的附件类型") -> None:
        super().__init__(E_ATTACHMENT_TYPE, message, 400)


class AttachmentTooLarge(BizError):
    """附件超过大小上限。"""

    def __init__(self, message: str = "附件超过大小上限") -> None:
        super().__init__(E_ATTACHMENT_TOO_LARGE, message, 413)


class AttachmentStoreError(BizError):
    """附件落盘/读取失败。"""

    def __init__(self, message: str = "附件存储失败") -> None:
        super().__init__(E_ATTACHMENT_STORE, message, 500)
