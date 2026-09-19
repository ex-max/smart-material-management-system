"""权限码单一事实源。

服务端以 code 鉴权（require_perm），种子迁移按此表写入 permissions。
"""


class Perm:
    USER_VIEW = "user:view"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    ROLE_VIEW = "role:view"
    ROLE_MANAGE = "role:manage"
    MATERIAL_VIEW = "material:view"
    MATERIAL_MANAGE = "material:manage"
    PURCHASE_VIEW = "purchase:view"
    PURCHASE_APPROVE = "purchase:approve"
    PURCHASE_MANAGE = "purchase:manage"
    INVENTORY_VIEW = "inventory:view"
    INVENTORY_MANAGE = "inventory:manage"
    FORECAST_VIEW = "forecast:view"
    FORECAST_MANAGE = "forecast:manage"
    REPLENISHMENT_VIEW = "replenishment:view"
    REPLENISHMENT_MANAGE = "replenishment:manage"
    REPLENISHMENT_CONVERT = "replenishment:convert"


# (code, name, type, sort_no)
PERMISSION_SEED: list[tuple[str, str, str, int]] = [
    (Perm.USER_VIEW, "查看用户", "API", 10),
    (Perm.USER_CREATE, "新建用户", "API", 11),
    (Perm.USER_UPDATE, "修改用户", "API", 12),
    (Perm.USER_DELETE, "删除用户", "API", 13),
    (Perm.ROLE_VIEW, "查看角色", "API", 20),
    (Perm.ROLE_MANAGE, "管理角色", "API", 21),
    (Perm.MATERIAL_VIEW, "查看主数据", "API", 30),
    (Perm.MATERIAL_MANAGE, "管理主数据", "API", 31),
    (Perm.PURCHASE_VIEW, "查看采购", "API", 40),
    (Perm.PURCHASE_APPROVE, "审批采购", "API", 41),
    (Perm.PURCHASE_MANAGE, "管理采购", "API", 42),
    (Perm.INVENTORY_VIEW, "查看库存", "API", 50),
    (Perm.INVENTORY_MANAGE, "库存作业", "API", 51),
    (Perm.FORECAST_VIEW, "查看预测", "API", 60),
    (Perm.FORECAST_MANAGE, "管理预测", "API", 61),
    (Perm.REPLENISHMENT_VIEW, "查看补货建议", "API", 70),
    (Perm.REPLENISHMENT_MANAGE, "管理补货建议", "API", 71),
    (Perm.REPLENISHMENT_CONVERT, "补货建议转请购单", "API", 72),
]

ROLE_ADMIN = "ADMIN"
ROLE_ADMIN_NAME = "系统管理员"
