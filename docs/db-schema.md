# 数据库设计（全库 41 张表：主数据 / 采购 / 库存作业 / 组织与权限 / 台账与统计 / 预测与决策 / 系统）

> **状态**：全库设计完成。第一部分（业务三组 21 张，M1-a）已评审通过；第二部分（其余四组 20 张，M1-b）待评审。
> **版本**：v1.1（2026-09-18）
> **依据**：毕设完整技术方案 v1 §4「数据库设计」（docs/plan 指向 /root/dsh/毕设-完整技术方案-v1.md）、AGENTS.md 硬规则与领域不变量、erp-db-migration 技能。
> **目标库**：PostgreSQL。金额/数量一律 Decimal（numeric），时间一律 timestamptz 存 UTC。

---

## 0. 范围与决策基线

### 0.1 范围（全部 7 组，共 41 张表）

本文件已覆盖全库设计：**第一部分**（M1-a，§3–§5）为业务三组 21 张（已评审）；**第二部分**（M1-b，§10 起）为其余四组 20 张（待评审）。

| 组 | 张数 | 表 | 章节 |
|---|---|---|---|
| 主数据 | 6 | material_category、material、unit、warehouse、location、supplier | §3 |
| 采购 | 6 | purchase_requisition、pr_item、purchase_order、po_item、supplier_delivery、supplier_delivery_item | §4 |
| 库存作业 | 9 | inbound_order、inbound_item、outbound_order、outbound_item、transfer_order、transfer_item、stocktake_order、stocktake_item、inventory_batch | §5 |
| 组织与权限 | 6 | users、roles、permissions、user_role、role_permission、operation_log | §10 |
| 台账与统计 | 5 | inventory、inventory_transaction、stock_alert、inventory_snapshot_daily、material_supplier_price | §11 |
| 预测与决策 | 6 | demand_series_meta、forecast_run、forecast_result、model_registry、replenishment_policy、replenishment_suggestion | §12 |
| 系统 | 3 | dict、scheduled_task_log、attachment | §13 |
| **合计** | **41** | | |

### 0.2 已确认决策（评审基线）

| # | 决策项 | 取值 | 对表结构的影响 |
|---|---|---|---|
| D1 | 物资分类 | 多级树形（parent_id 自关联） | material_category.parent_id + level + path |
| D2 | 计量单位 | 仅基本单位；material.unit_id 单值，不做多单位换算 | 不新增换算表；单据行统一按基本单位记账 |
| D3 | 审批范围 | 仅请购单需人工审批（单级）；采购订单/出入库/调拨/盘点不设二次审批 | 各单据状态机取全局 6 态的子集（见 1.6） |
| D4 | 批次与结存粒度 | 按 material.is_batch_managed 开关；结存精确到 物资 × 仓库 × 批次 | inventory_batch 为核心表；非批次物资用系统默认批次 |
| D5 | 到货 | 支持分批到货；验收通过后自动生成入库单 | supplier_delivery 头+行；inbound_order 由到货单驱动 |
| D6 | 到货/调拨结构 | 拆头行（比方案示例各 +1 张） | 采购 6 张、库存作业 9 张 |
| D7 | 盘点差异 | 生成盘盈/盘亏流水，不删历史流水，不加独立调整单 | 差异落 inventory_transaction（组5） |
| D8 | 表数 | 业务三组 21 张 + 其余四组 20 张 = 全库 41 张 | 见 0.3 |

### 0.3 与方案的差异（评审需知晓）

1. 方案把 supplier_delivery、transfer_order 各列为单表；本设计拆为“头 + 行”。原因：到货、调拨天然是多物资单据，单表会让单头字段（供应商、日期、状态）在每一行重复，且不利于状态机与追溯。代价是三组由 19 → 21 张。
2. 方案写“约 36 张”，但按其分组示例逐项相加实为 39 张；再加头行拆分 +2，**全库 41 张**（已全部落地，见 §10–§13）。若论文页码预算吃紧，建议优先合并/砍掉系统组（scheduled_task_log、attachment）而非业务表。
3. **结存粒度澄清（M1-b）**：inventory 是 **物资×仓库** 的汇总结存，inventory_batch 是 **物资×仓库×批次** 的明细；约定 SUM(inventory_batch.quantity) == inventory.quantity（见 §11.1、§14）。§5.9 的批次口径不变。
4. docs/plan 只被引用，本会话未改动其中任何内容。

---

## 1. 通用设计约定（所有表适用）

### 1.1 命名与主键

- 表名 snake_case 复数；字段 snake_case；外键统一 表名单数_id。
- 主键统一 **bigint identity**（不用 UUID）。理由：单实例单库、join 与范围查询多，顺序主键索引局部性好、无需额外存储；业务唯一性由 code / doc_no + 部分唯一索引表达。若后续分库再评估（记为开放问题）。
- 索引命名：唯一 uq_表_字段，普通 ix_表_字段，部分唯一 idx 同规则。

### 1.2 通用审计字段（所有业务表都含，后面字段表不再重复）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| created_at | timestamptz | NOT NULL DEFAULT now() | 创建时间（UTC） |
| updated_at | timestamptz | NOT NULL DEFAULT now() | 更新时间（UTC），service 层写入时刷新 |
| created_by | bigint | NOT NULL, FK users(id) | 创建人；系统任务使用保留系统账号 |
| updated_by | bigint | NULL, FK users(id) | 最后修改人 |
| deleted_at | timestamptz | NULL | 软删除；查询默认 deleted_at IS NULL |

> users 表属于组织与权限组（M1-b）。**建议该组表名用 users 而非 user**：PostgreSQL 中 user 是保留关键字，建表必须加引号，容易踩坑；且与“复数表名”约定一致。此为接口契约，M1-b 需确认。

### 1.3 数据类型约定

| 用途 | 类型 | 说明 |
|---|---|---|
| 金额 / 数量 | numeric(18,4) | AGENTS 硬规则：金额数量用 Decimal，不用 float |
| 税率 / 比率 | numeric(5,2) | 税率 0–100；需要更高精度再用 numeric(9,6) |
| 时间戳 | timestamptz | 存 UTC；展示层转 Asia/Shanghai |
| 业务日期 | date | 订单日期、交期、到货日期等业务日 |
| 布尔 | boolean | NOT NULL DEFAULT |
| 枚举 | varchar(16) + CHECK | **不用 PostgreSQL ENUM**：Alembic autogenerate 对 ENUM 变更支持差（见 erp-db-migration），加/改枚举值成本高 |
| 短文本 | varchar(n) | 按语义定长；长备注用 text |
| 编码 / 单号 | varchar(32) / varchar(64) | 全局唯一、不可修改 |

### 1.4 外键与删除策略

- 单据头 → 单据行：ondelete = CASCADE（删草稿单连带删行）。
- 单据行 / 业务表 → 主数据：ondelete = RESTRICT（防误删分类、物资、仓库）。
- 日志类表才用 CASCADE；本组无日志表。
- **所有外键列都显式建索引**（PostgreSQL 不自动建）。
- 已过账单据禁止物理删除：只允许软删 + 状态 CANCELLED，且作废已过账库存单据必须产生反向流水。

### 1.5 索引约定

- 软删场景的唯一性：用部分唯一索引 …… WHERE deleted_at IS NULL。
- 必建：单据号唯一、状态、外键、常用过滤/排序列（created_at、order_date、expected_date）。
- 明细表：UNIQUE(头_id, line_no)；并按 material_id、（必要时）batch_id 建索引。
- 不给低基数字段单独建索引（如 is_active）；复合索引按“等值列在前、范围列在后”。
- 不在本会话引入 pg_trgm 等扩展（属新依赖，需要先说明理由）。

### 1.6 单据状态机（单一事实来源：backend/app/core/state_machine.py）

全局状态集合（6 态，AGENTS 领域不变量 2）：

| 状态 | 含义 |
|---|---|
| DRAFT | 草稿 |
| PENDING | 待审 |
| APPROVED | 已审 / 已确认 |
| IN_PROGRESS | 执行中 |
| COMPLETED | 完成 |
| CANCELLED | 作废 |

通用迁移（每个迁移边都要有权限码与前置条件校验）：

~~~
DRAFT ──提交──▶ PENDING ──审核──▶ APPROVED ──执行──▶ IN_PROGRESS ──完成──▶ COMPLETED
  │                │                 │
  └────────────────┴─────────────────┴──── 作废（需权限，未过账）──▶ CANCELLED
~~~

各单据允许的状态子集（由 D3 决定）：

| 单据 | 允许迁移 | 审批 |
|---|---|---|
| purchase_requisition 请购单 | DRAFT→PENDING→APPROVED→IN_PROGRESS→COMPLETED；任意非终态→CANCELLED | **有（单级）** |
| purchase_order 采购订单 | DRAFT→APPROVED（确认下单）→IN_PROGRESS（部分到货）→COMPLETED；→CANCELLED | 无（不经 PENDING） |
| supplier_delivery 到货单 | DRAFT→PENDING（待验收）→APPROVED（验收通过）→COMPLETED（已入库）；→CANCELLED | 无（PENDING→APPROVED 是验收动作） |
| inbound_order 入库单 | DRAFT→IN_PROGRESS→COMPLETED；仅未过账可→CANCELLED | 无 |
| outbound_order 出库单 | DRAFT→IN_PROGRESS→COMPLETED；仅未过账可→CANCELLED | 无 |
| transfer_order 调拨单 | DRAFT→IN_PROGRESS→COMPLETED；仅未过账可→CANCELLED | 无 |
| stocktake_order 盘点单 | DRAFT→IN_PROGRESS→COMPLETED（过账）；仅未过账可→CANCELLED | 无 |

规则：
1. 状态只能由 service 层的迁移函数修改，**禁止任何代码直接 UPDATE status 字段**。
2. 已 COMPLETED 不可回退到 DRAFT。
3. 作废已过账库存单据 → 生成反向（红冲）流水，不允许删流水、不允许直接改结存。

### 1.7 单据号规则

- 格式：**PREFIX-YYYYMMDD-4 位流水**，例：PR-20260918-0001。
- 前缀：PR 请购、PO 采购订单、RCV 到货、IN 入库、OUT 出库、TR 调拨、ST 盘点。
- 唯一约束兜底；生成在 service 层用“按前缀+日期计数 + 唯一冲突重试”，**不新建序列表**（保持表数，也避免额外并发热点）。
- 单号全局唯一、不可修改；作废后不复用。

### 1.8 单据行追溯与快照

- 每个单据行必须有 line_no，且 (头_id, line_no) 唯一。
- 单据行保存**物资快照**（material_code、material_name、spec、unit_name）：主数据改名不影响历史单据展示与追溯（AGENTS 不变量 3）。
- 来源链（可一路回溯到请购单）：
  po_item.source_pr_item_id → pr_item → purchase_requisition；
  supplier_delivery_item.po_item_id → po_item；
  inbound_order.delivery_id → supplier_delivery，inbound_item.po_item_id → po_item；
  transfer_item.outbound_item_id / inbound_item_id → outbound_item / inbound_item。

### 1.9 与未建组的接口契约

| 本组引用 | 目标（所属组） | 约定 |
|---|---|---|
| created_by / approved_by 等 → users(id) | 组织与权限 | 该组建 users 表（避免保留字 user）；系统账号预留 |
| inventory、inventory_transaction | 台账与统计 | 粒度 = material × warehouse × batch_id；余额只能由流水推导 + 同事务更新 |
| material_supplier_price | 台账与统计 | 供货物资/供货价在此表；supplier 只存默认交期与评级 |
| stock_alert | 台账与统计 | 依据 material.safety_stock / max_stock + inventory_batch.status 生成 |
| forecast_* / replenishment_* | 预测与决策 | 只读业务表，绝不写本组业务表 |

---

## 2. 表清单总览（41 张）

| # | 表名 | 组 | 职责 | 关键唯一 / 索引 |
|---|---|---|---|---|
| 1 | material_category | 主数据 | 物资多级分类 | uq(COALESCE(parent_id,0), code)；ix(parent_id/path) |
| 2 | unit | 主数据 | 计量单位字典 | uq(code) |
| 3 | material | 主数据 | 物资档案（安全库存/上限/提前期/批次开关） | uq(code)；ix(category/unit/default_supplier/status) |
| 4 | warehouse | 主数据 | 仓库 | uq(code) |
| 5 | location | 主数据 | 库位 | uq(warehouse_id, code) |
| 6 | supplier | 主数据 | 供应商 | uq(code)；ix(name/status) |
| 7 | purchase_requisition | 采购 | 请购单头 | uq(doc_no)；ix(status/requester) |
| 8 | pr_item | 采购 | 请购单行 | uq(requisition_id, line_no) |
| 9 | purchase_order | 采购 | 采购订单头 | uq(doc_no)；ix(supplier/status/order_date) |
| 10 | po_item | 采购 | 采购订单行（含累计到货） | uq(po_id, line_no)；ix(material/source_pr_item) |
| 11 | supplier_delivery | 采购 | 到货/验收单头 | uq(doc_no)；ix(po/supplier/status) |
| 12 | supplier_delivery_item | 采购 | 到货行（批次/保质期/验收结论） | uq(delivery_id, line_no)；ix(po_item/material/batch_no) |
| 13 | inbound_order | 库存作业 | 入库单头（来源可采购/调拨等） | uq(doc_no)；ix(warehouse/status/delivery) |
| 14 | inbound_item | 库存作业 | 入库行（批次、库位、来源订单行） | uq(inbound_id, line_no)；ix(material/batch) |
| 15 | outbound_order | 库存作业 | 出库单头（领用等） | uq(doc_no)；ix(warehouse/status/receiver) |
| 16 | outbound_item | 库存作业 | 出库行（批次、库位） | uq(outbound_id, line_no)；ix(material/batch) |
| 17 | transfer_order | 库存作业 | 调拨单头（源仓→目标仓） | uq(doc_no)；ix(from/to/status) |
| 18 | transfer_item | 库存作业 | 调拨行 | uq(transfer_id, line_no)；ix(material) |
| 19 | stocktake_order | 库存作业 | 盘点单头 | uq(doc_no)；ix(warehouse/status) |
| 20 | stocktake_item | 库存作业 | 盘点行（账面/实盘/差异） | uq(stocktake_id, line_no)；ix(material/batch) |
| 21 | inventory_batch | 库存作业 | 批次结存明细（物资×仓库×批次） | uq(material_id, warehouse_id, batch_no) |
| 22 | users | 组织与权限 | 用户账号 | uq(username)；ix(status) |
| 23 | roles | 组织与权限 | 角色 | uq(code) |
| 24 | permissions | 组织与权限 | 权限（菜单/接口/按钮） | uq(code)；ix(parent_id/type) |
| 25 | user_role | 组织与权限 | 用户-角色 | uq(user_id, role_id) |
| 26 | role_permission | 组织与权限 | 角色-权限 | uq(role_id, permission_id) |
| 27 | operation_log | 组织与权限 | 操作日志（追加写） | ix(created_at/user_id/action/request_id) |
| 28 | inventory | 台账与统计 | 汇总结存（物资×仓库） | uq(material_id, warehouse_id) |
| 29 | inventory_transaction | 台账与统计 | 库存流水（唯一真值源） | ix(material,warehouse,occurred_at)/batch/source |
| 30 | stock_alert | 台账与统计 | 库存预警 | uq(material_id,warehouse_id,batch_id,alert_type) WHERE OPEN |
| 31 | inventory_snapshot_daily | 台账与统计 | 每日结存快照（供预测） | uq(snapshot_date, material_id, warehouse_id) |
| 32 | material_supplier_price | 台账与统计 | 供货物资/供货价 | uq(material_id, supplier_id) |
| 33 | demand_series_meta | 预测与决策 | 序列元数据（ADI/CV²/ABC） | uq(series_key) |
| 34 | forecast_run | 预测与决策 | 预测批次 | uq(run_no)；ix(status,started_at) |
| 35 | forecast_result | 预测与决策 | 预测结果（点值+区间） | uq(run_id, series_key, forecast_date) |
| 36 | model_registry | 预测与决策 | 模型注册表 | uq(model_code, version) |
| 37 | replenishment_policy | 预测与决策 | 补货策略参数（A/B 开关） | uq(policy_code) |
| 38 | replenishment_suggestion | 预测与决策 | 补货建议（可解释） | uq(suggestion_no)；(material,warehouse) WHERE OPEN |
| 39 | dict | 系统 | 展示型数据字典 | uq(dict_type, dict_key) |
| 40 | scheduled_task_log | 系统 | 定时任务日志 | ix(task_name, started_at) |
| 41 | attachment | 系统 | 附件元数据 | ix(biz_type, biz_id) |

---

## 3. 主数据组（6 张）

### 3.1 material_category 物资分类

职责：物资分类树（D1 多级），供 ABC 分层、报表与查询聚合。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| parent_id | bigint | FK→material_category(id) RESTRICT, NULL | 父分类；根节点为空 |
| code | varchar(32) | NOT NULL | 分类编码 |
| name | varchar(64) | NOT NULL | 分类名称 |
| level | smallint | NOT NULL, CHECK 1–5 | 层级（1 为根） |
| path | varchar(255) | NOT NULL | 物化路径，如 /1/12/35/，前缀匹配查子树 |
| sort_no | int | NOT NULL DEFAULT 0 | 同级排序 |
| is_active | boolean | NOT NULL DEFAULT true | 是否启用 |
| remark | varchar(255) | NULL | |

- 约束：**UNIQUE (COALESCE(parent_id, 0), code) WHERE deleted_at IS NULL**。必须用 COALESCE：PostgreSQL 视多个 NULL 互不相等，直接 (parent_id, code) 唯一会让根分类同名无法拦截。
- 索引：ix_material_category_parent_id、ix_material_category_path、ix_material_category_is_active。
- 关系：自关联 1:N；1:N material。

### 3.2 unit 计量单位

职责：计量单位字典（D2 仅基本单位，不做换算）。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| code | varchar(16) | NOT NULL | 单位编码，如 PCS/KG/M/BOX |
| name | varchar(32) | NOT NULL | 单位名称 |
| scale | smallint | NOT NULL DEFAULT 0, CHECK 0–4 | 数量小数位，控制录入与展示精度 |
| sort_no | int | NOT NULL DEFAULT 0 | 排序 |
| is_active | boolean | NOT NULL DEFAULT true | |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (code) WHERE deleted_at IS NULL。
- 关系：1:N material。

### 3.3 material 物资档案

职责：物资主数据；安全库存/上限/再订货点/提前期/批次开关都在这里（方案要求）。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| code | varchar(32) | NOT NULL | 物资编码，全局唯一 |
| name | varchar(128) | NOT NULL | 物资名称 |
| spec | varchar(128) | NULL | 规格型号 |
| category_id | bigint | NOT NULL, FK→material_category RESTRICT | 分类 |
| unit_id | bigint | NOT NULL, FK→unit RESTRICT | 基本单位（D2） |
| brand | varchar(64) | NULL | 品牌 |
| barcode | varchar(64) | NULL | 条码 |
| safety_stock | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 安全库存 |
| max_stock | numeric(18,4) | NULL, CHECK ≥ safety_stock | 库存上限 |
| reorder_point | numeric(18,4) | NULL, CHECK ≥0 | 固定再订货点（对照策略 A 用） |
| lead_time_days | numeric(8,2) | NULL, CHECK >0 | 默认采购提前期（天），供 ROP/仿真 |
| is_batch_managed | boolean | NOT NULL DEFAULT false | 是否批次管理（D4） |
| shelf_life_days | int | NULL, CHECK >0 | 保质期天数，仅批次物资 |
| default_supplier_id | bigint | NULL, FK→supplier RESTRICT | 默认供应商 |
| abc_class | varchar(1) | NULL, CHECK IN ('A','B','C') | ABC 分级（预测输入） |
| status | varchar(16) | NOT NULL DEFAULT 'ACTIVE', CHECK IN ('ACTIVE','INACTIVE') | 状态 |
| remark | text | NULL | |

- 约束：UNIQUE (code) WHERE deleted_at IS NULL；CHECK (NOT is_batch_managed OR shelf_life_days IS NULL OR shelf_life_days > 0)。
- 索引：ix_material_category_id、ix_material_unit_id、ix_material_default_supplier_id、ix_material_status。
- 关系：N:1 category / unit / supplier；1:N 各单据行、inventory_batch。

### 3.4 warehouse 仓库

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| code | varchar(32) | NOT NULL | 仓库编码 |
| name | varchar(64) | NOT NULL | 仓库名称 |
| address | varchar(255) | NULL | 地址 |
| manager_id | bigint | NULL, FK→users RESTRICT | 负责人 |
| is_active | boolean | NOT NULL DEFAULT true | |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (code) WHERE deleted_at IS NULL；ix_warehouse_manager_id。
- 关系：1:N location、1:N 各类作业单、1:N inventory_batch。

### 3.5 location 库位

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 所属仓库 |
| code | varchar(32) | NOT NULL | 库位编码 |
| name | varchar(64) | NULL | 库位名称 |
| zone | varchar(32) | NULL | 库区 |
| is_active | boolean | NOT NULL DEFAULT true | |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (warehouse_id, code) WHERE deleted_at IS NULL；ix_location_warehouse_id。
- 说明：D4 的结存口径不含库位，故 inventory_batch 不带 location_id；出入库行上的 location_id 仅作作业位置记录。若后续要做库位级结存，需改 D4 并另立 ADR。
- 关系：N:1 warehouse。

### 3.6 supplier 供应商

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| code | varchar(32) | NOT NULL | 供应商编码 |
| name | varchar(128) | NOT NULL | 供应商名称 |
| short_name | varchar(64) | NULL | 简称 |
| contact_person | varchar(64) | NULL | 联系人 |
| contact_phone | varchar(32) | NULL | 联系电话 |
| email | varchar(128) | NULL | 邮箱 |
| address | varchar(255) | NULL | 地址 |
| tax_no | varchar(64) | NULL | 税号 |
| payment_terms | varchar(64) | NULL | 账期/结算方式 |
| lead_time_days | numeric(8,2) | NULL, CHECK >0 | 默认交货周期（天） |
| rating | numeric(3,2) | NULL, CHECK 0–5 | 评级 |
| status | varchar(16) | NOT NULL DEFAULT 'ACTIVE', CHECK IN ('ACTIVE','INACTIVE','BLACKLIST') | 状态 |
| remark | text | NULL | |

- 约束：UNIQUE (code) WHERE deleted_at IS NULL；ix_supplier_name、ix_supplier_status。
- 说明：供货物资与供货价放组 5 的 material_supplier_price，不在本表；本表 lead_time_days 与 material.lead_time_days 的优先级由 service 层定（建议：物料级优先，回退供应商级）。
- 关系：1:N purchase_order、1:N supplier_delivery、1:N material（默认供应商）。

---

## 4. 采购组（6 张）

### 4.1 purchase_requisition 请购单头

职责：需求发起与单级审批（D3，唯一需要审批的单据）。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| doc_no | varchar(32) | NOT NULL | 单号 PR-YYYYMMDD-#### |
| title | varchar(128) | NULL | 主题 |
| requester_id | bigint | NOT NULL, FK→users RESTRICT | 申请人 |
| dept_name | varchar(64) | NULL | 申请部门（文本，见开放问题） |
| status | varchar(16) | NOT NULL DEFAULT 'DRAFT', CHECK IN (6 态) | 状态 |
| priority | smallint | NOT NULL DEFAULT 3, CHECK 1–5 | 紧急程度（1 最急） |
| expected_date | date | NULL | 期望到货/需求日期 |
| reason | varchar(255) | NULL | 请购事由 |
| total_amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 汇总金额（service 层维护） |
| approved_by | bigint | NULL, FK→users RESTRICT | 审核人 |
| approved_at | timestamptz | NULL | 审核时间 |
| cancelled_by | bigint | NULL, FK→users RESTRICT | 作废人 |
| cancelled_at | timestamptz | NULL | 作废时间 |
| cancel_reason | varchar(255) | NULL | 作废原因 |
| remark | text | NULL | |

- 约束：UNIQUE (doc_no)；CHECK (status <> 'APPROVED' OR approved_by IS NOT NULL)。
- 索引：ix_purchase_requisition_status、ix_..._requester_id、ix_..._expected_date、ix_..._created_at。
- 状态机：DRAFT→PENDING→APPROVED→IN_PROGRESS（已转采购订单、待收货）→COMPLETED；非终态可→CANCELLED。
- 关系：1:N pr_item；1:N purchase_order（来源）。

### 4.2 pr_item 请购单行

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| requisition_id | bigint | NOT NULL, FK→purchase_requisition CASCADE | 头 |
| line_no | int | NOT NULL, CHECK >0 | 行号 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| material_code | varchar(32) | NOT NULL | 快照 |
| material_name | varchar(128) | NOT NULL | 快照 |
| spec | varchar(128) | NULL | 快照 |
| unit_name | varchar(32) | NOT NULL | 快照 |
| quantity | numeric(18,4) | NOT NULL, CHECK >0 | 请购数量（基本单位） |
| purpose | varchar(255) | NULL | 用途 |
| expected_date | date | NULL | 行级期望日期 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (requisition_id, line_no)；ix_pr_item_material_id。
- 关系：N:1 requisition、material；1:N po_item（source_pr_item_id 反向）。

### 4.3 purchase_order 采购订单头

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| doc_no | varchar(32) | NOT NULL | 单号 PO-YYYYMMDD-#### |
| requisition_id | bigint | NULL, FK→purchase_requisition RESTRICT | 来源请购单；空表示直采 |
| supplier_id | bigint | NOT NULL, FK→supplier RESTRICT | 供应商 |
| status | varchar(16) | NOT NULL DEFAULT 'DRAFT', CHECK IN (6 态) | 状态（不经 PENDING） |
| order_date | date | NOT NULL DEFAULT CURRENT_DATE | 下单日期 |
| expected_date | date | NULL | 合同交期 |
| buyer_id | bigint | NULL, FK→users RESTRICT | 采购员 |
| delivery_address | varchar(255) | NULL | 收货地址 |
| currency | varchar(8) | NOT NULL DEFAULT 'CNY' | 币种 |
| total_amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 含税合计（冗余） |
| tax_amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 税额 |
| payment_terms | varchar(64) | NULL | 结算方式（默认取供应商） |
| approved_by | bigint | NULL, FK→users RESTRICT | 确认人（无审批环节，记录确认动作） |
| approved_at | timestamptz | NULL | 确认时间 |
| cancelled_by | bigint | NULL, FK→users RESTRICT | |
| cancelled_at | timestamptz | NULL | |
| cancel_reason | varchar(255) | NULL | |
| remark | text | NULL | |

- 约束：UNIQUE (doc_no)；CHECK (expected_date IS NULL OR expected_date >= order_date)。
- 索引：ix_purchase_order_supplier_id、ix_..._status、ix_..._order_date、ix_..._requisition_id。
- 状态机：DRAFT→APPROVED（确认下单）→IN_PROGRESS（有到货）→COMPLETED（全部到货）；→CANCELLED。由已审请购单生成时可直接置 APPROVED。
- 关系：N:1 requisition / supplier；1:N po_item；1:N supplier_delivery。

### 4.4 po_item 采购订单行

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| po_id | bigint | NOT NULL, FK→purchase_order CASCADE | 头 |
| line_no | int | NOT NULL, CHECK >0 | 行号 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| material_code | varchar(32) | NOT NULL | 快照 |
| material_name | varchar(128) | NOT NULL | 快照 |
| spec | varchar(128) | NULL | 快照 |
| unit_name | varchar(32) | NOT NULL | 快照 |
| quantity | numeric(18,4) | NOT NULL, CHECK >0 | 订购数量 |
| unit_price | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 单价 |
| tax_rate | numeric(5,2) | NOT NULL DEFAULT 0, CHECK 0–100 | 税率(%) |
| amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 金额 = 数量 × 单价（冗余） |
| received_qty | numeric(18,4) | NOT NULL DEFAULT 0 | 累计到货数量 |
| expected_date | date | NULL | 行级交期 |
| source_pr_item_id | bigint | NULL, FK→pr_item RESTRICT | 来源请购行（追溯） |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (po_id, line_no)；CHECK (received_qty ≥0 AND received_qty ≤ quantity)。
- 索引：ix_po_item_material_id、ix_po_item_source_pr_item_id。
- 在途量（in_transit）= SUM(quantity - received_qty)，用于库存可用量/ROP 判断，不落表。

### 4.5 supplier_delivery 到货/验收单头（D5）

职责：登记供应商送货批次，记录验收结论；验收通过后驱动生成入库单。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| doc_no | varchar(32) | NOT NULL | 单号 RCV-YYYYMMDD-#### |
| po_id | bigint | NOT NULL, FK→purchase_order RESTRICT | 来源采购订单 |
| supplier_id | bigint | NOT NULL, FK→supplier RESTRICT | 供应商（冗余便于查询） |
| delivery_date | date | NOT NULL | 到货日期 |
| status | varchar(16) | NOT NULL DEFAULT 'DRAFT', CHECK IN ('DRAFT','PENDING','APPROVED','COMPLETED','CANCELLED') | 状态 |
| received_by | bigint | NULL, FK→users RESTRICT | 收货人 |
| inspected_by | bigint | NULL, FK→users RESTRICT | 验收人 |
| inspected_at | timestamptz | NULL | 验收时间 |
| total_amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 到货金额（冗余） |
| cancel_reason | varchar(255) | NULL | |
| remark | text | NULL | |

- 约束：UNIQUE (doc_no)；CHECK (status <> 'APPROVED' OR inspected_by IS NOT NULL)。
- 索引：ix_supplier_delivery_po_id、ix_..._supplier_id、ix_..._status、ix_..._delivery_date。
- 状态机：DRAFT→PENDING（待验收）→APPROVED（验收通过，触发生成入库单）→COMPLETED（已入库）；→CANCELLED（拒收/作废）。
- 关系：1:N supplier_delivery_item；1:N inbound_order。

### 4.6 supplier_delivery_item 到货行

职责：承载“到货含批次与交期”的落点：本次到货数量、批次号、生产/到期日、验收结论。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| delivery_id | bigint | NOT NULL, FK→supplier_delivery CASCADE | 头 |
| line_no | int | NOT NULL, CHECK >0 | 行号 |
| po_item_id | bigint | NOT NULL, FK→po_item RESTRICT | 对应的采购订单行 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| material_code | varchar(32) | NOT NULL | 快照 |
| material_name | varchar(128) | NOT NULL | 快照 |
| spec | varchar(128) | NULL | 快照 |
| unit_name | varchar(32) | NOT NULL | 快照 |
| quantity | numeric(18,4) | NOT NULL, CHECK >0 | 本次到货数量 |
| accepted_qty | numeric(18,4) | NULL, CHECK ≥0 | 验收合格数量 |
| rejected_qty | numeric(18,4) | NULL, CHECK ≥0 | 不合格/拒收数量 |
| batch_no | varchar(64) | NULL | 供应商批次号（批次物资必填，由 service 校验） |
| production_date | date | NULL | 生产日期 |
| expiry_date | date | NULL | 到期日期（批次物资且有保质期时必填） |
| inspection_result | varchar(16) | NULL, CHECK IN ('PASS','CONCESSION','REJECT') | 验收结论：合格/让步接收/拒收 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (delivery_id, line_no)；CHECK (accepted_qty IS NULL OR rejected_qty IS NULL OR accepted_qty + rejected_qty <= quantity)。
- 索引：ix_supplier_delivery_item_po_item_id、ix_..._material_id、ix_..._batch_no。
- 说明：分批到货由“同一 po_item 出现在多张 supplier_delivery 的多行”实现；po_item.received_qty 在到货验收时累加。

---

## 5. 库存作业组（9 张）

> **总原则（AGENTS 领域不变量 1）**：所有库存变动**只**通过 inventory_transaction 记账，并在**同一事务内**更新 inventory（及汇总 inventory_batch）；作业单据本身不直接改余额。本组产出的是“作业单据 + 批次”，实际过账写流水/结存在 M2 实现，届时跑对账（第 7 节）。

### 5.1 inbound_order 入库单头

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| doc_no | varchar(32) | NOT NULL | 单号 IN-YYYYMMDD-#### |
| source_type | varchar(16) | NOT NULL, CHECK IN ('PURCHASE','TRANSFER','RETURN','OTHER') | 来源类型 |
| source_id | bigint | NULL | 多态来源单据 id（辅助追溯） |
| delivery_id | bigint | NULL, FK→supplier_delivery RESTRICT | 采购到货来源（source_type=PURCHASE） |
| transfer_order_id | bigint | NULL, FK→transfer_order RESTRICT | 调拨入库来源（source_type=TRANSFER） |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 入库仓库 |
| status | varchar(16) | NOT NULL DEFAULT 'DRAFT', CHECK IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED') | 状态 |
| inbound_by | bigint | NULL, FK→users RESTRICT | 入库操作人 |
| inbound_at | timestamptz | NULL | 入库过账时间 |
| total_amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 金额（冗余，非财务口径） |
| cancel_reason | varchar(255) | NULL | |
| remark | text | NULL | |

- 约束：UNIQUE (doc_no)；CHECK ((source_type='PURCHASE') = (delivery_id IS NOT NULL) OR source_type <> 'PURCHASE')（简化：PURCHASE 必须有 delivery_id，其它类型可空）。
- 索引：ix_inbound_order_warehouse_id、ix_..._status、ix_..._delivery_id、ix_..._transfer_order_id、ix_..._(source_type, source_id)。
- 状态机：DRAFT→IN_PROGRESS→COMPLETED（过账写流水）；仅未过账可→CANCELLED。
- 关系：N:1 warehouse / supplier_delivery / transfer_order；1:N inbound_item。

### 5.2 inbound_item 入库行

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| inbound_id | bigint | NOT NULL, FK→inbound_order CASCADE | 头 |
| line_no | int | NOT NULL, CHECK >0 | 行号 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| material_code | varchar(32) | NOT NULL | 快照 |
| material_name | varchar(128) | NOT NULL | 快照 |
| spec | varchar(128) | NULL | 快照 |
| unit_name | varchar(32) | NOT NULL | 快照 |
| quantity | numeric(18,4) | NOT NULL, CHECK >0 | 入库数量 |
| unit_price | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 单价（采购入库取 po_item.unit_price） |
| amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 金额（冗余） |
| batch_id | bigint | NULL, FK→inventory_batch RESTRICT | 产生的批次（过账时创建/复用） |
| batch_no | varchar(64) | NULL | 批次号（与 inventory_batch 对应） |
| production_date | date | NULL | 生产日期 |
| expiry_date | date | NULL | 到期日期 |
| location_id | bigint | NULL, FK→location RESTRICT | 入库库位（可选） |
| po_item_id | bigint | NULL, FK→po_item RESTRICT | 来源采购订单行（追溯） |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (inbound_id, line_no)；CHECK (batch_id IS NULL OR batch_no IS NOT NULL)。
- 索引：ix_inbound_item_material_id、ix_..._batch_id、ix_..._po_item_id、ix_..._location_id。
- 过账（M2）：写 inventory_transaction(方向 IN) → 同事务 UPDATE inventory.quantity → upsert inventory_batch（按 material×warehouse×batch_no）。

### 5.3 outbound_order 出库单头

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| doc_no | varchar(32) | NOT NULL | 单号 OUT-YYYYMMDD-#### |
| source_type | varchar(32) | NOT NULL, CHECK IN ('REQUISITION_ISSUE','TRANSFER','SCRAP','OTHER') | 领用出库/调拨出库/报废/其他（M2-c 修正：REQUISITION_ISSUE 长 17，原 varchar(16) 放不下，列宽改 32） |
| source_id | bigint | NULL | 多态来源 id |
| transfer_order_id | bigint | NULL, FK→transfer_order RESTRICT | 调拨出库来源 |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 出库仓库 |
| receiver_id | bigint | NULL, FK→users RESTRICT | 领用人/接收人 |
| dept_name | varchar(64) | NULL | 领用部门（文本，见开放问题） |
| status | varchar(16) | NOT NULL DEFAULT 'DRAFT', CHECK IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED') | 状态 |
| outbound_by | bigint | NULL, FK→users RESTRICT | 出库操作人 |
| outbound_at | timestamptz | NULL | 出库过账时间 |
| total_amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 金额（冗余，非财务口径；见范围声明） |
| cancel_reason | varchar(255) | NULL | |
| remark | text | NULL | |

- 约束：UNIQUE (doc_no)。
- 索引：ix_outbound_order_warehouse_id、ix_..._status、ix_..._receiver_id、ix_..._transfer_order_id。
- 状态机：DRAFT→IN_PROGRESS→COMPLETED；仅未过账可→CANCELLED。
- 说明：方案范围不含财务与成本核算；unit_price/amount 仅作数量口径与管理展示占位。

### 5.4 outbound_item 出库行

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| outbound_id | bigint | NOT NULL, FK→outbound_order CASCADE | 头 |
| line_no | int | NOT NULL, CHECK >0 | 行号 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| material_code | varchar(32) | NOT NULL | 快照 |
| material_name | varchar(128) | NOT NULL | 快照 |
| spec | varchar(128) | NULL | 快照 |
| unit_name | varchar(32) | NOT NULL | 快照 |
| quantity | numeric(18,4) | NOT NULL, CHECK >0 | 出库数量 |
| batch_id | bigint | NULL, FK→inventory_batch RESTRICT | 指定批次（批次物资必填） |
| location_id | bigint | NULL, FK→location RESTRICT | 出库库位（可选） |
| unit_price | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 单价（占位） |
| amount | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 金额（冗余） |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (outbound_id, line_no)。
- 索引：ix_outbound_item_material_id、ix_..._batch_id。
- 并发（M2）：出库过账需 SELECT ... FOR UPDATE 锁 inventory（按 grain）行，校验可用量 ≥ 0，写反向/负向流水并同步更新结存；禁止超卖。

### 5.5 transfer_order 调拨单头

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| doc_no | varchar(32) | NOT NULL | 单号 TR-YYYYMMDD-#### |
| from_warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 源仓库 |
| to_warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 目标仓库 |
| status | varchar(16) | NOT NULL DEFAULT 'DRAFT', CHECK IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED') | 状态 |
| applicant_id | bigint | NULL, FK→users RESTRICT | 申请人 |
| transfer_date | date | NOT NULL DEFAULT CURRENT_DATE | 调拨日期 |
| completed_at | timestamptz | NULL | 完成时间 |
| cancel_reason | varchar(255) | NULL | |
| remark | text | NULL | |

- 约束：UNIQUE (doc_no)；CHECK (from_warehouse_id <> to_warehouse_id)。
- 索引：ix_transfer_order_from_warehouse_id、ix_..._to_warehouse_id、ix_..._status。
- 状态机：DRAFT→IN_PROGRESS→COMPLETED；仅未过账可→CANCELLED。
- 说明：调拨 = 源仓出库 + 目标仓入库，由本单驱动生成 outbound_order 与 inbound_order（或直接在同一事务内对两仓各写一张流水），**仍只写流水、不改余额**。

### 5.6 transfer_item 调拨行

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| transfer_id | bigint | NOT NULL, FK→transfer_order CASCADE | 头 |
| line_no | int | NOT NULL, CHECK >0 | 行号 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| material_code | varchar(32) | NOT NULL | 快照 |
| material_name | varchar(128) | NOT NULL | 快照 |
| spec | varchar(128) | NULL | 快照 |
| unit_name | varchar(32) | NOT NULL | 快照 |
| quantity | numeric(18,4) | NOT NULL, CHECK >0 | 调拨数量 |
| batch_id | bigint | NULL, FK→inventory_batch RESTRICT | 批次（批次物资必填） |
| from_location_id | bigint | NULL, FK→location RESTRICT | 源库位 |
| to_location_id | bigint | NULL, FK→location RESTRICT | 目标库位 |
| outbound_item_id | bigint | NULL, FK→outbound_item RESTRICT | 生成的出库行 |
| inbound_item_id | bigint | NULL, FK→inbound_item RESTRICT | 生成的入库行 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (transfer_id, line_no)。
- 索引：ix_transfer_item_material_id、ix_..._batch_id。

### 5.7 stocktake_order 盘点单头

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| doc_no | varchar(32) | NOT NULL | 单号 ST-YYYYMMDD-#### |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 盘点仓库 |
| scope | varchar(16) | NOT NULL DEFAULT 'PARTIAL', CHECK IN ('FULL','PARTIAL') | 全盘/抽盘 |
| status | varchar(16) | NOT NULL DEFAULT 'DRAFT', CHECK IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED') | 状态 |
| planned_date | date | NULL | 计划日期 |
| started_at | timestamptz | NULL | 开始时间 |
| finished_at | timestamptz | NULL | 结束时间 |
| posted_by | bigint | NULL, FK→users RESTRICT | 过账人 |
| posted_at | timestamptz | NULL | 过账时间 |
| cancel_reason | varchar(255) | NULL | |
| remark | text | NULL | |

- 约束：UNIQUE (doc_no)。
- 索引：ix_stocktake_order_warehouse_id、ix_..._status。
- 状态机：DRAFT→IN_PROGRESS→COMPLETED（过账）；仅未过账可→CANCELLED。

### 5.8 stocktake_item 盘点行

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| stocktake_id | bigint | NOT NULL, FK→stocktake_order CASCADE | 头 |
| line_no | int | NOT NULL, CHECK >0 | 行号 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| batch_id | bigint | NULL, FK→inventory_batch RESTRICT | 盘点批次 |
| location_id | bigint | NULL, FK→location RESTRICT | 库位（可选） |
| book_qty | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 账面数量（盘点开始时快照） |
| actual_qty | numeric(18,4) | NULL, CHECK ≥0 | 实盘数量 |
| diff_qty | numeric(18,4) | NULL | 差异 = actual_qty − book_qty（service 层维护） |
| reason | varchar(255) | NULL | 差异原因 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (stocktake_id, line_no)；CHECK (diff_qty IS NULL OR actual_qty IS NULL OR diff_qty = actual_qty - book_qty)。
- 索引：ix_stocktake_item_material_id、ix_..._batch_id。
- **过账（D7）**：diff_qty ≠ 0 → 生成 inventory_transaction（盘盈/盘亏，source_type=STOCKTAKE、source_id=盘点单）并同事务更新结存；**不修改/删除任何历史流水，不新增独立调整单**。

### 5.9 inventory_batch 批次结存（D4 核心）

职责：按 物资 × 仓库 × 批次 维护结存；是库存余额的批次维度视图，供预警（临期/呆滞）与对账使用。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 仓库 |
| batch_no | varchar(64) | NOT NULL | 批次号；非批次物资固定用 '__DEFAULT__' |
| is_default | boolean | NOT NULL DEFAULT false | 是否为非批次物资的系统默认批次 |
| production_date | date | NULL | 生产日期 |
| expiry_date | date | NULL | 到期日期 |
| inbound_date | date | NULL | 首次入库日期（呆滞判断） |
| quantity | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 当前批次结存 |
| locked_qty | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 预留/锁定数量（可用量 = quantity − locked_qty） |
| status | varchar(16) | NOT NULL DEFAULT 'NORMAL', CHECK IN ('NORMAL','NEAR_EXPIRY','EXPIRED','FROZEN') | 批次状态，供库存预警 |
| remark | varchar(255) | NULL | |

- 约束：
  - UNIQUE (material_id, warehouse_id, batch_no) WHERE deleted_at IS NULL。
  - 每个 物资×仓库 至多一个默认批次：部分唯一索引 (material_id, warehouse_id) WHERE is_default AND deleted_at IS NULL。
  - CHECK (quantity ≥ locked_qty)。
- 索引：ix_inventory_batch_warehouse_id、ix_..._expiry_date、ix_..._(material_id, warehouse_id)、ix_..._status。
- **一致性（M2 必测）**：
  1. 只能通过流水过账同事务更新，禁止代码路径直接 UPDATE inventory_batch.quantity（对账检查项）。
  2. SUM(inventory_batch.quantity) 按 (material_id, warehouse_id) 汇总，必须等于组 5 inventory 的 quantity（若有批次维度则一一对应）。
  3. 批次汇总 ≡ inventory_transaction 汇总（对账任务，见第 7 节）。
- 非批次物资策略（D4 落地细节，请评审确认）：为其在 material×warehouse 建立唯一 is_default=true、batch_no='__DEFAULT__' 的批次行，使 inventory / inventory_transaction 的 batch_id 可保持 NOT NULL，唯一约束与对账口径统一。若你更希望 batch_id 可空，则需要用 COALESCE 表达式索引，复杂度更高，建议维持本策略。

---

## 6. E-R 说明

### 6.1 主数据

~~~mermaid
erDiagram
    material_category ||--o{ material_category : "父子"
    material_category ||--o{ material : "分类"
    unit ||--o{ material : "基本单位"
    supplier ||--o{ material : "默认供应商"
    warehouse ||--o{ location : "含库位"
~~~

### 6.2 采购

~~~mermaid
erDiagram
    purchase_requisition ||--o{ pr_item : "含行"
    purchase_requisition ||--o{ purchase_order : "转单"
    supplier ||--o{ purchase_order : "供货"
    purchase_order ||--o{ po_item : "含行"
    pr_item ||--o{ po_item : "来源行"
    material ||--o{ pr_item : "物资"
    material ||--o{ po_item : "物资"
    purchase_order ||--o{ supplier_delivery : "分批到货"
    supplier ||--o{ supplier_delivery : "送货"
    supplier_delivery ||--o{ supplier_delivery_item : "含行"
    po_item ||--o{ supplier_delivery_item : "对应订单行"
~~~

### 6.3 库存作业

~~~mermaid
erDiagram
    supplier_delivery ||--o{ inbound_order : "验收后生成"
    transfer_order ||--o{ inbound_order : "调拨入库"
    warehouse ||--o{ inbound_order : "入库仓"
    inbound_order ||--o{ inbound_item : "含行"
    material ||--o{ inbound_item : "物资"
    po_item ||--o{ inbound_item : "来源订单行"
    inventory_batch ||--o{ inbound_item : "产生批次"
    location ||--o{ inbound_item : "入库库位"

    warehouse ||--o{ outbound_order : "出库仓"
    transfer_order ||--o{ outbound_order : "调拨出库"
    outbound_order ||--o{ outbound_item : "含行"
    material ||--o{ outbound_item : "物资"
    inventory_batch ||--o{ outbound_item : "扣减批次"

    warehouse ||--o{ transfer_order : "源/目标仓"
    transfer_order ||--o{ transfer_item : "含行"
    material ||--o{ transfer_item : "物资"
    transfer_item ||--o{ outbound_item : "生成出库行"
    transfer_item ||--o{ inbound_item : "生成入库行"

    warehouse ||--o{ stocktake_order : "盘点仓"
    stocktake_order ||--o{ stocktake_item : "含行"
    material ||--o{ stocktake_item : "物资"
    inventory_batch ||--o{ stocktake_item : "盘点批次"

    material ||--o{ inventory_batch : "批次结存"
    warehouse ||--o{ inventory_batch : "批次结存"
~~~

### 6.4 业务流程（采购→到货→入库→流水→结存）

~~~mermaid
flowchart LR
    A[请购单 PR] -->|单级审批| B[采购订单 PO]
    B --> C[到货登记/验收 RCV]
    C -->|验收通过| D[入库单 IN]
    D --> E[写 inventory_transaction]
    E --> F[同事务更新 inventory / inventory_batch]
    G[出库单 OUT] --> E
    H[调拨单 TR] --> E
    I[盘点单 ST] -->|盘盈/盘亏| E
~~~

---

## 7. 领域不变量在设计中的落点

| 不变量（AGENTS §5） | 本设计的落点 |
|---|---|
| 1. 库存余额只能由流水推导 | 出入库/调拨/盘点作业单只产生“作业行”，过账时**只写 inventory_transaction + 同事务更新 inventory/inventory_batch**；inventory_batch 不提供直接改 balance 的写入口；M2 提供对账任务 |
| 2. 单据必须走状态机 | 1.6 定义全局 6 态与各单据子集；状态迁移集中在 core/state_machine.py；禁止直接 UPDATE status |
| 3. 单据行可追溯 | 1.8 快照字段 + 来源链（source_pr_item_id/po_item_id/delivery_id/transfer_item 关联）；每行 line_no + 操作人 + 时间 |
| 4. 预测模块不得写业务表 | 本组表不向预测模块开放写权限；预测只落 forecast_*（组 6） |
| 5. 补货建议必须可解释 | material.safety_stock / reorder_point / lead_time_days + inventory_batch 结存 + po_item 在途量，构成建议依据（组 5/6 消费） |
| 库存相关改动须更新对账状态 | 本会话已在 docs/progress.md 的“对账状态”追加设计口径行 |

---

## 8. 跨组接口契约（M1-b 已落地，详见 §10–§13）

1. **users(id)（§10.1）**：created_by/updated_by/approved_by/receiver_id 等全部引用 users(id)；系统任务使用保留系统账号。
2. **inventory（§11.1）**：粒度 = **material_id × warehouse_id**（汇总结存），UNIQUE(material_id, warehouse_id)；批次明细在 inventory_batch（material×warehouse×batch_no）。**修正**：本节初稿曾写 inventory 含 batch_id，M1-b 定为“inventory 汇总 + inventory_batch 明细”，二者必须满足 SUM(batch) == inventory（对账见 §14）。
3. **inventory_transaction（§11.2）**：字段含 material_id、warehouse_id、batch_id、**带符号 quantity**（SUM(quantity) 即为结存）、txn_type、source_type、source_id/source_no/source_line_id、occurred_at、created_by；所有作业过账只写它。
4. **stock_alert（§11.3）**：依据 material.safety_stock/max_stock、inventory 结存与 inventory_batch.status/expiry_date 生成。
5. **material_supplier_price（§11.5）**：供货物资与供货价；提前期取值优先级（service 层统一）= material.lead_time_days > material_supplier_price.lead_time_days > supplier.lead_time_days。
6. **forecast_/replenishment_（§12）**：只读业务表、只写预测与建议表，绝不回写业务表（AGENTS 不变量 4）。

---

## 9. 开放问题与已定结论（评审通过：全部采纳建议）

| # | 问题 | 结论（已采纳，实现按此） |
|---|---|---|
| Q1 | 组织与权限组表名用 users 还是 user | users（PostgreSQL 保留字 + 复数约定）；M1-b 按此建表 |
| Q2 | 非批次物资的默认批次 | batch_no='__DEFAULT__' + is_default=true，batch_id 保持 NOT NULL（见 5.9） |
| Q3 | 部门主数据 | 暂用 dept_name 文本；若要做部门主数据需在组织组加表并记 ADR |
| Q4 | 单号流水生成 | “计数 + 冲突重试”，不建序列表；唯一约束兜底 |
| Q5 | 主键类型 | bigint identity；改用 UUID 需 ADR |
| Q6 | 库位是否强制 | 可空（按仓库记账）；若要强制，收紧出入库行 location_id 为 NOT NULL |
| Q7 | 盘点是否允许部分过账 | 整单过账（COMPLETED 时统一处理） |
| Q8 | 出库成本口径 | 不含财务成本核算，unit_price/amount 仅占位（方案范围声明） |

> 结论已同步到 docs/progress.md 的“已知坑 / 未决问题”（状态：已确认 · 采纳建议）。

---

# 第二部分：其余四组（M1-b，20 张）

## 10. 组织与权限组（6 张）

> RBAC：用户 —(user_role)— 角色 —(role_permission)— 权限。权限 code 逐级下钻到接口，后端强制校验、前端仅做展示。Q1 已定：表名用复数 users/roles/permissions（避开 PostgreSQL 保留字 user）。

### 10.1 users 用户

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| username | varchar(64) | NOT NULL | 登录名 |
| password_hash | varchar(255) | NOT NULL | 口令哈希（bcrypt/argon2），禁止明文 |
| real_name | varchar(64) | NULL | 姓名 |
| phone | varchar(32) | NULL | 手机 |
| email | varchar(128) | NULL | 邮箱 |
| avatar | varchar(255) | NULL | 头像地址 |
| dept_name | varchar(64) | NULL | 部门（Q3：方案无 dept 表，用文本） |
| is_superuser | boolean | NOT NULL DEFAULT false | 超级管理员（绕过权限校验，慎用） |
| status | varchar(16) | NOT NULL DEFAULT 'ACTIVE', CHECK IN ('ACTIVE','DISABLED','LOCKED') | 状态 |
| last_login_at | timestamptz | NULL | 最后登录时间 |
| last_login_ip | varchar(45) | NULL | 最后登录 IP（兼容 IPv6） |
| pwd_updated_at | timestamptz | NULL | 口令最后修改时间 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (username) WHERE deleted_at IS NULL。
- 索引：ix_users_status。
- 关系：1:N user_role；1:N operation_log；被各业务表 created_by/updated_by 引用。

### 10.2 roles 角色

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| code | varchar(32) | NOT NULL | 角色编码，如 ADMIN/BUYER/KEEPER |
| name | varchar(64) | NOT NULL | 角色名称 |
| description | varchar(255) | NULL | 说明 |
| is_builtin | boolean | NOT NULL DEFAULT false | 内置角色（不可删） |
| sort_no | int | NOT NULL DEFAULT 0 | 排序 |
| status | varchar(16) | NOT NULL DEFAULT 'ACTIVE', CHECK IN ('ACTIVE','INACTIVE') | 状态 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (code) WHERE deleted_at IS NULL。
- 关系：1:N user_role、role_permission。

### 10.3 permissions 权限

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| parent_id | bigint | NULL, FK→permissions RESTRICT | 父权限（菜单树） |
| code | varchar(64) | NOT NULL | 权限码，如 material:create、purchase:approve、inventory:view |
| name | varchar(64) | NOT NULL | 名称 |
| type | varchar(16) | NOT NULL, CHECK IN ('MENU','API','BUTTON','DATA') | 类型：菜单/接口/按钮/数据范围 |
| method | varchar(8) | NULL | HTTP 方法（type=API 时） |
| path | varchar(255) | NULL | 路由或接口路径 |
| sort_no | int | NOT NULL DEFAULT 0 | 排序 |
| is_active | boolean | NOT NULL DEFAULT true | |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (code) WHERE deleted_at IS NULL；ix_permissions_parent_id、ix_permissions_type。
- 说明：服务端以 code 做鉴权（require_perm('purchase:approve')）；菜单项仅影响前端可见性。

### 10.4 user_role 用户-角色

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| user_id | bigint | NOT NULL, FK→users CASCADE | 用户 |
| role_id | bigint | NOT NULL, FK→roles CASCADE | 角色 |

- 约束：UNIQUE (user_id, role_id)；ix_user_role_role_id。含通用审计字段。

### 10.5 role_permission 角色-权限

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| role_id | bigint | NOT NULL, FK→roles CASCADE | 角色 |
| permission_id | bigint | NOT NULL, FK→permissions CASCADE | 权限 |

- 约束：UNIQUE (role_id, permission_id)；ix_role_permission_permission_id。含通用审计字段。

### 10.6 operation_log 操作日志

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| user_id | bigint | NULL, FK→users RESTRICT | 操作人 |
| username | varchar(64) | NULL | 操作人快照 |
| module | varchar(32) | NULL | 模块（material/purchase/inventory/...） |
| action | varchar(64) | NOT NULL | 操作码，如 purchase.order.approve |
| resource_type | varchar(64) | NULL | 资源类型 |
| resource_id | varchar(64) | NULL | 资源 id |
| method | varchar(8) | NULL | HTTP 方法 |
| path | varchar(255) | NULL | 请求路径 |
| ip | varchar(45) | NULL | 来源 IP |
| user_agent | varchar(255) | NULL | UA |
| request_id | varchar(64) | NULL | 链路 id（响应体的 trace_id） |
| result | varchar(16) | NOT NULL DEFAULT 'SUCCESS', CHECK IN ('SUCCESS','FAIL') | 结果 |
| error_code | varchar(16) | NULL | 业务错误码 |
| duration_ms | int | NULL | 耗时 |
| detail | jsonb | NULL | 关键参数/变更前后（仅审计用） |
| created_at | timestamptz | NOT NULL DEFAULT now() | 写入时间（UTC） |

- **日志类例外**：只追加、不更新、不软删，故不设 updated_at/updated_by/deleted_at/created_by（created_at + user_id 足够）；detail 用 PostgreSQL 原生 jsonb，不引入新依赖。
- 索引：ix_operation_log_created_at、ix_operation_log_user_id、ix_operation_log_action、ix_operation_log_request_id。

---

## 11. 台账与统计组（5 张）

> 本组是库存不变量 1 的落点：余额只能由流水推导。inventory / inventory_batch 只能由过账服务在同一事务内更新，任何直接 UPDATE 结存的代码路径都是 bug（对账见 §14）。

### 11.1 inventory 汇总结存（物资×仓库）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 仓库 |
| quantity | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 结存 = SUM(流水) = SUM(批次) |
| locked_qty | numeric(18,4) | NOT NULL DEFAULT 0, CHECK ≥0 | 预留/锁定 |
| version | int | NOT NULL DEFAULT 0 | 乐观锁版本号 |
| last_txn_at | timestamptz | NULL | 最近一次流水时间 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (material_id, warehouse_id) WHERE deleted_at IS NULL；CHECK (quantity >= locked_qty)。
- 索引：ix_inventory_warehouse_id、ix_inventory_(material_id, warehouse_id)。
- 一致性：quantity = SUM(inventory_transaction.quantity) = SUM(inventory_batch.quantity)（按 material+warehouse）。非批次物资也有默认批次（§5.9），口径统一。

### 11.2 inventory_transaction 库存流水（唯一真值源）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| idem_key | varchar(64) | NULL | 幂等键（如 单据:行号:类型），防重复过账 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 仓库 |
| batch_id | bigint | NOT NULL, FK→inventory_batch RESTRICT | 批次（非批次物资为默认批次） |
| quantity | numeric(18,4) | NOT NULL, CHECK <> 0 | **带符号**：入库为正、出库为负；盘盈正、盘亏负 |
| txn_type | varchar(16) | NOT NULL, CHECK IN ('INBOUND','OUTBOUND','TRANSFER_IN','TRANSFER_OUT','STOCKTAKE_GAIN','STOCKTAKE_LOSS','REVERSAL') | 业务类型 |
| source_type | varchar(16) | NOT NULL, CHECK IN ('INBOUND','OUTBOUND','TRANSFER','STOCKTAKE','MANUAL') | 来源单据类型 |
| source_id | bigint | NULL | 来源单据 id |
| source_no | varchar(32) | NULL | 来源单号快照 |
| source_line_id | bigint | NULL | 来源单据行 id |
| balance_after | numeric(18,4) | NULL | 过账后该批次结存（追溯） |
| unit_price | numeric(18,4) | NULL, CHECK ≥0 | 单价（非财务口径） |
| amount | numeric(18,4) | NULL | 金额（冗余） |
| occurred_at | timestamptz | NOT NULL DEFAULT now() | 业务发生时间 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (idem_key) WHERE idem_key IS NOT NULL。
- 索引：ix_itxn_(material_id, warehouse_id, occurred_at)、ix_itxn_batch_id、ix_itxn_(source_type, source_id)、ix_itxn_txn_type、ix_itxn_occurred_at。
- **写规则**：只 INSERT，禁止 UPDATE/DELETE；单据作废/红冲产生 txn_type=REVERSAL 的反向流水。

### 11.3 stock_alert 库存预警

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| warehouse_id | bigint | NULL, FK→warehouse RESTRICT | 仓库（空=全局） |
| batch_id | bigint | NULL, FK→inventory_batch RESTRICT | 批次（临期类） |
| alert_type | varchar(16) | NOT NULL, CHECK IN ('LOW_STOCK','OUT_OF_STOCK','OVER_STOCK','NEAR_EXPIRY','EXPIRED','SLOW_MOVING') | 预警类型 |
| level | varchar(8) | NOT NULL DEFAULT 'WARN', CHECK IN ('INFO','WARN','CRITICAL') | 级别 |
| status | varchar(16) | NOT NULL DEFAULT 'OPEN', CHECK IN ('OPEN','ACKED','RESOLVED','IGNORED') | 状态 |
| threshold | numeric(18,4) | NULL | 触发阈值 |
| current_value | numeric(18,4) | NULL | 触发时实际值 |
| message | varchar(255) | NULL | 描述 |
| triggered_at | timestamptz | NOT NULL DEFAULT now() | 触发时间 |
| acked_by | bigint | NULL, FK→users RESTRICT | 确认人 |
| acked_at | timestamptz | NULL | 确认时间 |
| resolved_at | timestamptz | NULL | 解决时间 |
| remark | varchar(255) | NULL | |

- 约束：同物料/仓库/批次同类型未关闭前不重复 → 部分唯一 (material_id, COALESCE(warehouse_id,0), COALESCE(batch_id,0), alert_type) WHERE status IN ('OPEN','ACKED')（COALESCE 处理 NULL 语义）。
- 索引：ix_stock_alert_(material_id, status)、ix_stock_alert_(alert_type, status)、ix_stock_alert_triggered_at。

### 11.4 inventory_snapshot_daily 每日结存快照

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| snapshot_date | date | NOT NULL | 业务日（Asia/Shanghai） |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 仓库 |
| quantity | numeric(18,4) | NOT NULL DEFAULT 0 | 当日结存 |
| locked_qty | numeric(18,4) | NOT NULL DEFAULT 0 | 当日锁定 |
| in_transit_qty | numeric(18,4) | NOT NULL DEFAULT 0 | 当日在途（po_item 未到货量） |
| created_at | timestamptz | NOT NULL DEFAULT now() | |

- 约束：UNIQUE (snapshot_date, material_id, warehouse_id)。
- 索引：ix_isd_snapshot_date、ix_isd_(material_id, snapshot_date)。
- 说明：粒度=物资×仓库×日（供预测聚合日序列）；定时任务生成、当日可重算（upsert）；ML 只读。

### 11.5 material_supplier_price 供货物资/供货价

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| supplier_id | bigint | NOT NULL, FK→supplier RESTRICT | 供应商 |
| unit_price | numeric(18,4) | NOT NULL, CHECK ≥0 | 供货价 |
| currency | varchar(8) | NOT NULL DEFAULT 'CNY' | 币种 |
| min_order_qty | numeric(18,4) | NULL, CHECK >0 | 起订量 |
| lead_time_days | numeric(8,2) | NULL, CHECK >0 | 该供应商对该物料的交期 |
| is_preferred | boolean | NOT NULL DEFAULT false | 是否优先供应商 |
| valid_from | date | NULL | 生效日 |
| valid_to | date | NULL | 失效日 |
| status | varchar(16) | NOT NULL DEFAULT 'ACTIVE', CHECK IN ('ACTIVE','INACTIVE') | 状态 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (material_id, supplier_id) WHERE deleted_at IS NULL；每物料至多一个优先供应商 → 部分唯一 (material_id) WHERE is_preferred AND deleted_at IS NULL。
- 索引：ix_msp_supplier_id。
- 说明：价格历史版本化（valid_from/valid_to）见 §15-Q3，本期先单条当前价。

---

## 12. 预测与决策组（6 张，论文核心）

> AGENTS 不变量 4：预测模块只读业务表，只写本组表；预测失败不得影响业务单据。

### 12.1 demand_series_meta 需求序列元数据

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| series_key | varchar(64) | NOT NULL | 序列键（material_id:warehouse_id），唯一 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| warehouse_id | bigint | NULL, FK→warehouse RESTRICT | 仓库（空=按物资聚合） |
| data_start_date | date | NULL | 序列起始 |
| data_end_date | date | NULL | 序列结束 |
| obs_days | int | NULL | 观测天数 |
| non_zero_days | int | NULL | 非零需求天数 |
| adi | numeric(10,4) | NULL | 平均需求间隔 |
| cv2 | numeric(10,4) | NULL | 需求变异系数平方 |
| demand_class | varchar(16) | NULL, CHECK IN ('SMOOTH','ERRATIC','INTERMITTENT','LUMPY') | 平滑/波动/间歇/块状 |
| abc_class | varchar(1) | NULL, CHECK IN ('A','B','C') | ABC 分级 |
| mean_daily | numeric(18,4) | NULL | 日均需求 |
| std_daily | numeric(18,4) | NULL | 日需求标准差 |
| last_calc_at | timestamptz | NULL | 最近计算时间 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (series_key)；ix_dsm_(material_id, warehouse_id)、ix_dsm_demand_class。
- 分层判据（§6.1）：ADI < 1.32 且 CV² < 0.49 → SMOOTH；ADI ≥ 1.32 且 CV² < 0.49 → INTERMITTENT；其余 → ERRATIC/LUMPY（由计算任务写入，不在库内计算）。

### 12.2 model_registry 模型注册表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| model_code | varchar(64) | NOT NULL | 模型编码（如 lgbm_demand_v1） |
| model_type | varchar(32) | NOT NULL, CHECK IN ('NAIVE','SEASONAL_NAIVE','MA','ETS','ARIMA','SARIMA','RIDGE','RF','LIGHTGBM','XGBOOST','CROSTON','TSB','LSTM','TCN') | 模型类别 |
| version | varchar(32) | NOT NULL | 版本 |
| params | jsonb | NULL | 超参快照 |
| feature_config | jsonb | NULL | 特征配置快照 |
| metrics | jsonb | NULL | 训练/验证指标快照（sMAPE/MASE…） |
| artifact_path | varchar(255) | NULL | 模型文件相对路径（不入 git） |
| trained_at | timestamptz | NULL | 训练时间 |
| trained_by | bigint | NULL, FK→users RESTRICT | 训练发起人 |
| is_active | boolean | NOT NULL DEFAULT false | 是否当前启用 |
| status | varchar(16) | NOT NULL DEFAULT 'READY', CHECK IN ('TRAINING','READY','ARCHIVED','FAILED') | 状态 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (model_code, version)；ix_model_registry_(model_type, is_active)。
- 说明：定时重训 + 版本回滚（§11 答辩要点）；is_active 唯一性由 service 层按预测场景保证。

### 12.3 forecast_run 预测批次

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| run_no | varchar(32) | NOT NULL | 批次号 FR-YYYYMMDD-#### |
| trigger_type | varchar(16) | NOT NULL, CHECK IN ('MANUAL','SCHEDULED','BACKTEST') | 触发方式 |
| status | varchar(16) | NOT NULL DEFAULT 'RUNNING', CHECK IN ('RUNNING','SUCCESS','PARTIAL','FAILED') | 状态 |
| horizon_days | int | NOT NULL, CHECK >0 | 预测步长（7/14/30） |
| train_start_date | date | NULL | 训练窗起 |
| train_end_date | date | NULL | 训练窗止 |
| forecast_start_date | date | NULL | 预测起 |
| series_count | int | NOT NULL DEFAULT 0 | 计划序列数 |
| success_count | int | NOT NULL DEFAULT 0 | 成功数 |
| failed_count | int | NOT NULL DEFAULT 0 | 失败数 |
| started_at | timestamptz | NOT NULL DEFAULT now() | 开始 |
| finished_at | timestamptz | NULL | 结束 |
| duration_ms | int | NULL | 耗时 |
| error_summary | text | NULL | 失败摘要 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (run_no)；ix_forecast_run_(status, started_at)。
- 说明：一次批量预测 = 一个 run；A/B 仿真可用 BACKTEST 触发。

### 12.4 forecast_result 预测结果

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| run_id | bigint | NOT NULL, FK→forecast_run CASCADE | 批次 |
| series_key | varchar(64) | NOT NULL | 序列键 |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| warehouse_id | bigint | NULL, FK→warehouse RESTRICT | 仓库 |
| forecast_date | date | NOT NULL | 预测目标日 |
| horizon_step | int | NOT NULL, CHECK >0 | 步长序号 |
| y_hat | numeric(18,4) | NOT NULL, CHECK ≥0 | 预测值（点估计） |
| y_lower | numeric(18,4) | NULL | 区间下界 |
| y_upper | numeric(18,4) | NULL | 区间上界 |
| model_code | varchar(64) | NULL | 模型编码快照 |
| model_version | varchar(32) | NULL | 模型版本快照 |
| demand_class | varchar(16) | NULL | 分层快照 |
| created_at | timestamptz | NOT NULL DEFAULT now() | |

- 约束：UNIQUE (run_id, series_key, forecast_date)；CHECK (y_lower IS NULL OR y_upper IS NULL OR y_lower <= y_hat AND y_hat <= y_upper)。
- 索引：ix_forecast_result_(material_id, forecast_date)、ix_forecast_result_run_id。
- 说明：区间用于"预测不准怎么办"（§11 答辩要点）；仅 forecast_* 表可写，业务表只读。

### 12.5 replenishment_policy 补货策略参数

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| policy_code | varchar(32) | NOT NULL | 策略编码 |
| policy_name | varchar(64) | NULL | 策略名称 |
| material_id | bigint | NULL, FK→material RESTRICT | 适用物料（空=全局） |
| warehouse_id | bigint | NULL, FK→warehouse RESTRICT | 适用仓库（空=全部） |
| strategy | varchar(16) | NOT NULL, CHECK IN ('FIXED','FORECAST','EOQ','MIN_MAX') | 固定阈值(A)/预测驱动(B)/EOQ/最小-最大 |
| service_level_type | varchar(16) | NULL, CHECK IN ('CSL','FILL_RATE') | 服务水平口径（M5 定稿，全程一致） |
| service_level | numeric(5,2) | NULL, CHECK 0–100 | 目标服务水平 |
| z_value | numeric(6,3) | NULL | 正态分位数（如 95% → 1.645） |
| review_period_days | int | NULL, CHECK >0 | 检查周期 |
| order_cost | numeric(18,4) | NULL, CHECK ≥0 | 订货成本 S（EOQ 用） |
| holding_cost_rate | numeric(9,6) | NULL, CHECK ≥0 | 持有成本率/单位持有成本 H |
| min_order_qty | numeric(18,4) | NULL, CHECK >0 | 起订量 |
| pack_size | numeric(18,4) | NULL, CHECK >0 | 包装倍数 |
| lead_time_days | numeric(8,2) | NULL, CHECK >0 | 提前期覆盖 |
| safety_stock_override | numeric(18,4) | NULL | 手工指定 SS（策略 A 用） |
| rop_override | numeric(18,4) | NULL | 手工指定 ROP（策略 A 用） |
| is_active | boolean | NOT NULL DEFAULT true | |
| effective_from | date | NULL | 生效日 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (policy_code) WHERE deleted_at IS NULL。
- 索引：ix_replenishment_policy_(material_id, warehouse_id)。
- 说明：A/B 仿真靠它切换；取值优先级 material+warehouse > material > 全局（service 层统一）。

### 12.6 replenishment_suggestion 补货建议（可解释）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| suggestion_no | varchar(32) | NOT NULL | 建议号 RS-YYYYMMDD-#### |
| material_id | bigint | NOT NULL, FK→material RESTRICT | 物资 |
| warehouse_id | bigint | NOT NULL, FK→warehouse RESTRICT | 仓库 |
| policy_id | bigint | NULL, FK→replenishment_policy RESTRICT | 采用的策略 |
| forecast_run_id | bigint | NULL, FK→forecast_run RESTRICT | 引用预测批次 |
| trigger_type | varchar(16) | NOT NULL, CHECK IN ('BELOW_ROP','FORECAST','SAFETY','MANUAL') | 触发方式 |
| status | varchar(16) | NOT NULL DEFAULT 'OPEN', CHECK IN ('OPEN','SUGGESTED','CONVERTED','REJECTED','EXPIRED','CLOSED') | 状态 |
| current_qty | numeric(18,4) | NOT NULL DEFAULT 0 | 当前结存 |
| locked_qty | numeric(18,4) | NOT NULL DEFAULT 0 | 锁定 |
| in_transit_qty | numeric(18,4) | NOT NULL DEFAULT 0 | 在途 |
| available_qty | numeric(18,4) | NOT NULL DEFAULT 0 | 可用 = 结存 − 锁定 + 在途 |
| daily_demand_hat | numeric(18,4) | NULL | 预测日均需求 |
| lead_time_days | numeric(8,2) | NULL | 提前期均值 |
| sigma_d | numeric(18,4) | NULL | 需求标准差（日） |
| sigma_lt | numeric(8,2) | NULL | 提前期标准差 |
| safety_stock | numeric(18,4) | NULL | SS = z·√(LT·σD² + D̂²·σLT²) |
| rop | numeric(18,4) | NULL | ROP = D̂·LT + SS |
| eoq | numeric(18,4) | NULL | EOQ 参考量 |
| suggested_qty | numeric(18,4) | NOT NULL, CHECK ≥0 | 建议订货量（按起订量/包装取整前） |
| final_qty | numeric(18,4) | NULL, CHECK ≥0 | 取整/人工确认后数量 |
| reason | text | NULL | **触发依据**（可解释性） |
| generated_at | timestamptz | NOT NULL DEFAULT now() | 生成时间 |
| expires_at | timestamptz | NULL | 失效时间 |
| converted_pr_id | bigint | NULL, FK→purchase_requisition RESTRICT | 一键转请购单 |
| converted_at | timestamptz | NULL | 转单时间 |
| handled_by | bigint | NULL, FK→users RESTRICT | 处理人 |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (suggestion_no)；同物料/仓库未处理建议不重复 → 部分唯一 (material_id, warehouse_id) WHERE status IN ('OPEN','SUGGESTED')。
- 索引：ix_rs_(status, generated_at)、ix_rs_(material_id, warehouse_id)。
- 说明（AGENTS 不变量 5）：current_qty/in_transit_qty/available_qty/rop/safety_stock/预测值/参数来源（policy_id、forecast_run_id）齐备，天然可解释；reason 存自然语言触发依据。

---

## 13. 系统组（3 张）

### 13.1 dict 数据字典

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| dict_type | varchar(64) | NOT NULL | 字典类型（如 priority、alert_level） |
| dict_key | varchar(64) | NOT NULL | 键 |
| dict_label | varchar(128) | NOT NULL | 展示值 |
| sort_no | int | NOT NULL DEFAULT 0 | 排序 |
| is_active | boolean | NOT NULL DEFAULT true | |
| remark | varchar(255) | NULL | |

- 约束：UNIQUE (dict_type, dict_key)。
- 说明：**边界**——业务枚举以代码常量 + 列 CHECK 为单一事实源；dict 只放展示型/可运营字典，避免双份真值。

### 13.2 scheduled_task_log 定时任务日志

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| task_name | varchar(64) | NOT NULL | 任务名（forecast_daily/alert_scan/snapshot_daily…） |
| task_type | varchar(32) | NULL | 类型 |
| status | varchar(16) | NOT NULL DEFAULT 'RUNNING', CHECK IN ('RUNNING','SUCCESS','FAILED','SKIPPED') | 状态 |
| started_at | timestamptz | NOT NULL DEFAULT now() | 开始 |
| finished_at | timestamptz | NULL | 结束 |
| duration_ms | int | NULL | 耗时 |
| affected_rows | int | NULL | 影响行数 |
| result_summary | varchar(255) | NULL | 摘要 |
| error_detail | text | NULL | 错误详情 |
| trace_id | varchar(64) | NULL | 链路 id |

- 约束：日志类，追加写。
- 索引：ix_stl_(task_name, started_at)、ix_stl_status。

### 13.3 attachment 附件元数据

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK identity | |
| biz_type | varchar(32) | NOT NULL | 关联业务类型（purchase_order/inbound_order…） |
| biz_id | bigint | NOT NULL | 关联业务 id |
| file_name | varchar(255) | NOT NULL | 原始文件名 |
| file_path | varchar(512) | NOT NULL | 存储相对路径（本地磁盘，不入 git） |
| file_size | bigint | NULL, CHECK ≥0 | 字节数 |
| content_type | varchar(128) | NULL | MIME |
| sha256 | varchar(64) | NULL | 校验和 |
| storage | varchar(16) | NOT NULL DEFAULT 'LOCAL', CHECK IN ('LOCAL','OSS','S3') | 存储类型 |
| uploaded_by | bigint | NULL, FK→users RESTRICT | 上传人 |

- 索引：ix_attachment_(biz_type, biz_id)、ix_attachment_sha256。
- 说明：文件本体不入库；DB 只存元数据与路径。

---

## 14. E-R 补充与库存对账口径

### 14.1 组织与权限

~~~mermaid
erDiagram
    users ||--o{ user_role : "授予"
    roles ||--o{ user_role : "被授予"
    roles ||--o{ role_permission : "拥有"
    permissions ||--o{ role_permission : "被拥有"
    permissions ||--o{ permissions : "父子"
    users ||--o{ operation_log : "操作"
~~~

### 14.2 台账与统计 / 预测与决策

~~~mermaid
erDiagram
    material ||--o{ inventory : "汇总结存"
    warehouse ||--o{ inventory : "汇总结存"
    inventory_batch ||--o{ inventory_transaction : "批次流水"
    material ||--o{ inventory_transaction : "流水"
    warehouse ||--o{ inventory_transaction : "流水"
    material ||--o{ stock_alert : "预警"
    material ||--o{ inventory_snapshot_daily : "日快照"
    material ||--o{ material_supplier_price : "供货价"
    supplier ||--o{ material_supplier_price : "供货价"
    material ||--o{ demand_series_meta : "序列"
    forecast_run ||--o{ forecast_result : "含结果"
    model_registry ||--o{ forecast_result : "产出"
    material ||--o{ replenishment_policy : "适用"
    replenishment_policy ||--o{ replenishment_suggestion : "生成"
    forecast_run ||--o{ replenishment_suggestion : "依据"
    purchase_requisition ||--o{ replenishment_suggestion : "转单"
~~~

### 14.3 库存对账 SQL（M2 实现后必须跑；差异处置策略：告警 + 阻断过账）

~~~sql
-- ① 批次明细汇总 == 仓库汇总结存
SELECT i.material_id, i.warehouse_id, i.quantity AS inventory_qty, b.batch_sum
FROM inventory i
LEFT JOIN (
  SELECT material_id, warehouse_id, SUM(quantity) AS batch_sum
  FROM inventory_batch WHERE deleted_at IS NULL GROUP BY material_id, warehouse_id
) b ON b.material_id = i.material_id AND b.warehouse_id = i.warehouse_id
WHERE i.deleted_at IS NULL AND i.quantity <> COALESCE(b.batch_sum, 0);

-- ② 流水汇总 == 仓库汇总结存
SELECT i.material_id, i.warehouse_id, i.quantity AS inventory_qty, t.txn_sum
FROM inventory i
LEFT JOIN (
  SELECT material_id, warehouse_id, SUM(quantity) AS txn_sum
  FROM inventory_transaction GROUP BY material_id, warehouse_id
) t ON t.material_id = i.material_id AND t.warehouse_id = i.warehouse_id
WHERE i.deleted_at IS NULL AND i.quantity <> COALESCE(t.txn_sum, 0);

-- ③ 批次级：流水 == 批次结存
SELECT b.material_id, b.warehouse_id, b.batch_no, b.quantity, t.txn_sum
FROM inventory_batch b
LEFT JOIN (
  SELECT batch_id, SUM(quantity) AS txn_sum
  FROM inventory_transaction GROUP BY batch_id
) t ON t.batch_id = b.id
WHERE b.deleted_at IS NULL AND b.quantity <> COALESCE(t.txn_sum, 0);

-- ④ 不变量守卫：不得出现负结存 / 锁定超结存
SELECT * FROM inventory WHERE quantity < 0 OR quantity < locked_qty;
~~~

---

## 15. 开放问题与已定结论（M1-b 评审通过：全部采纳建议）

| # | 问题 | 结论（已采纳，实现按此） |
|---|---|---|
| M1B-Q1 | 数据范围权限 | 本期只做功能权限 RBAC（MENU/API/BUTTON）；DATA 类型权限码仅预留，不做行级隔离 |
| M1B-Q2 | 服务水平口径 CSL / Fill Rate | 由 replenishment_policy.service_level_type 承载；M5 前定稿并全程一致 |
| M1B-Q3 | 供货价历史版本化 | 本期单条当前价（valid_from/valid_to 预留）；需要历史再加价格历史表 |
| M1B-Q4 | 日快照保留期 | 3 年（与生成数据一致），超期归档 |
| M1B-Q5 | 附件存储 | 本期本地磁盘（storage=LOCAL + 相对路径），后续可换对象存储 |
| M1B-Q6 | operation_log 保留/清理 | 按年归档、不物理删除 |
| M1B-Q7 | dict 与代码枚举边界 | 业务枚举以代码常量 + 列 CHECK 为单一事实源；dict 仅展示型 |

> 结论已同步到 docs/progress.md 的“已知坑 / 未决问题”。

