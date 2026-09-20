"""数据字典预置（展示型）。

边界（docs/db-schema.md §13.1）：业务枚举以代码常量 + 列 CHECK 为单一事实源，
dict **只**提供展示标签/排序/启停，不承载业务判断。因此这里登记的 key 全部来自既有代码常量：

- doc_status   ← app/core/state_machine.py DocStatus.ALL_STATUSES
- alert_type   ← app/model/ledger.py _ALERT_TYPE_CHECK
- alert_level  ← app/model/ledger.py _ALERT_LEVEL_CHECK
- abc_class    ← app/schema/master.py / demand_series_meta CHECK
- demand_class ← ml 分层 / demand_series_meta CHECK
- priority     ← 预留运营字典

scripts/seed.py 按 (dict_type, dict_key) 幂等插入（已存在不改，避免覆盖用户运营修改）。
"""

# (dict_type, dict_key, dict_label, sort_no)
DICT_SEED: list[tuple[str, str, str, int]] = [
    # 单据状态（state_machine.DocStatus）
    ("doc_status", "DRAFT", "草稿", 10),
    ("doc_status", "PENDING", "待审", 20),
    ("doc_status", "APPROVED", "已审", 30),
    ("doc_status", "IN_PROGRESS", "执行中", 40),
    ("doc_status", "COMPLETED", "完成", 50),
    ("doc_status", "CANCELLED", "作废", 60),
    # 库存预警类型（stock_alert.alert_type CHECK）
    ("alert_type", "LOW_STOCK", "低库存", 10),
    ("alert_type", "OUT_OF_STOCK", "零库存", 20),
    ("alert_type", "OVER_STOCK", "超储", 30),
    ("alert_type", "NEAR_EXPIRY", "临期", 40),
    ("alert_type", "EXPIRED", "过期", 50),
    ("alert_type", "SLOW_MOVING", "呆滞", 60),
    # 预警级别（stock_alert.level CHECK）
    ("alert_level", "INFO", "提示", 10),
    ("alert_level", "WARN", "警告", 20),
    ("alert_level", "CRITICAL", "严重", 30),
    # ABC 分类
    ("abc_class", "A", "A 类（重点）", 10),
    ("abc_class", "B", "B 类（常规）", 20),
    ("abc_class", "C", "C 类（次要）", 30),
    # 需求分层（demand_series_meta.demand_class CHECK）
    ("demand_class", "SMOOTH", "平滑", 10),
    ("demand_class", "ERRATIC", "波动", 20),
    ("demand_class", "INTERMITTENT", "间歇", 30),
    ("demand_class", "LUMPY", "块状", 40),
    # 优先级（预留运营字典）
    ("priority", "LOW", "低", 10),
    ("priority", "NORMAL", "普通", 20),
    ("priority", "HIGH", "高", 30),
    ("priority", "URGENT", "紧急", 40),
]
