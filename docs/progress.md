# 项目进度（每个会话开工先读这里，收尾必须更新）

> 规则：**"下一步"永远只写一条**（下一个会话直接照做）；"已知坑"只增不删（删要写原因）。

## 当前状态

- **里程碑**：**S5 系统三表落地完成**（`dict` 两级 CRUD + 下拉、`scheduled_task_log` 记录/收尾/查询、`attachment` 真实上传下载；迁移 `0008_system_tables`，真 PG 可逆已验证；`make verify` 绿且 **0 skip**）。
- **更新时间**：2026-09-20

## 已完成

- [x] 项目骨架（backend / frontend / ml / deploy / docs / scripts）
- [x] `AGENTS.md` 工作约定 + `make verify` 质量门禁（后端已转真检查）
- [x] ADR-0001 技术栈选型
- [x] GitHub 远程仓库接入（`origin`，AGENTS 第七节）
- [x] **M1-a/M1-b 数据库设计**：`docs/db-schema.md`，全库 **41 张表** + §14 对账 SQL
- [x] **M1-c 后端骨架 + 组织与权限/登录**：统一响应/错误码/trace_id、JWT 登录、`require_perm` RBAC、用户 CRUD、迁移 `0001_init_org_auth`（6 表）、`scripts/seed.py`
- [x] **M1-d 主数据模块**：§3 六张表 ORM + 迁移 `0002_master_data` + CRUD API + 测试
  （`material-categories` 树形分类含 level/path、`units`、`materials`、`warehouses`、`locations`、`suppliers`；统一用 `material:view/material:manage` 鉴权；软删；编码冲突 409、外键校验 400）
- [x] **M2-a 采购单据 + 状态机**：`core/state_machine.py`（全局 6 态 + 7 类单据迁移边 + 权限码，仅请购单审批）、采购 6 表 ORM + 迁移 `0003_procurement`、单据号 `PR/PO/RCV-YYYYMMDD-####`、请购单 CRUD+提交+审批（`purchase:approve`）+作废+转采购订单、采购订单 CRUD+确认+作废、到货单 CRUD+提交+作废（到货累计校验、批次/保质期校验）、`scripts/check_invariants.py` 与 26 条测试
- [x] **M2-b 到货验收 → 入库 → 库存流水**：`inventory`/`inventory_batch`/`inventory_transaction` + `inbound_order`/`inbound_item` ORM 与迁移 `0004_inventory_inbound`；到货验收（`PENDING→APPROVED`，生成入库单）、入库过账（`DRAFT→IN_PROGRESS`：`SELECT ... FOR UPDATE` 锁结存 → 写流水 → 更新 `inventory`/`inventory_batch` → 回写 `po_item.received_qty`/采购订单状态）、完成；库存查询 + `GET /inventory/reconcile` 对账接口；非批次物资默认批次 `__DEFAULT__`；34 条测试（SQLite + PostgreSQL 双跑）
- [x] **M2-c 出库 / 调拨 / 盘点 + 红冲**：`outbound_order`/`outbound_item`、`transfer_order`/`transfer_item`、`stocktake_order`/`stocktake_item` ORM + 迁移 `0005_inventory_ops`（并给 `inbound_order` 补 `transfer_order_id`）；抽出 `service/stock_ledger.py` 作为唯一结存变更入口；出库锁结存校验可用量、调拨两仓各写 TRANSFER_OUT/IN 并生成出/入库单、盘点差异写 STOCKTAKE_GAIN/LOSS；`reverse` 红冲（REVERSAL 反向流水）；43 条测试（SQLite + PG 双跑）
- [x] **M2-d 库存预警 / 日结存快照 / 供货价**：`stock_alert`/`inventory_snapshot_daily`/`material_supplier_price` ORM + 迁移 `0006_ledger`；预警扫描（零库存/低库存/超储/临期/过期，未关闭去重）+ ack/resolve/ignore；日快照 upsert（物资×仓库×日，含在途）；供货价 CRUD + 优先供应商唯一；50 条测试（SQLite + PG 双跑）
- [x] **M3 模拟数据生成 + 需求预测基线（ml/）**：冻结 `GeneratorConfig`（seed/skus/years、Bernoulli–Gamma、对数正态提前期）；新增 `ml/erp_ml`（config/catalog/demand/series/metrics/models/backtest/artifacts/generate/baseline）与项目内隔离 `ml/.venv`；`make gen-data` 生成 800 SKU×3 年（1095 天、876,000 行）日需求 → `data/seed_1/`（parquet/csv/json，不进 git）；实测 ADI/CV² 四象限 43.2%/24.4%/23.8%/8.6%（平滑/波动/间歇/块状）；`make baseline` 用 Naive/季节 Naive/MA7/MA28/ETS 做 3 seed × 每 seed 分层 100 序列 × horizon 7/14/30 的 expanding-window rolling-origin 回测 → `ml/results/runs/20260919-0031_m3-baseline/`；`make verify` 第 7 项（ml ruff + 14 条测试）转为真检查
- [x] **M4 特征工程 + LightGBM（并补 ARIMA/Croston 分层映射）**：新增 `ml/erp_ml/features.py`（滞后 1/2/3/7/14/28 + 滑动 7/14/28 的 mean/std/nonzero + 截断 days_since_nonzero + 日历 7 维 + 序列静态 4 维 = **27 维**，严格因果）、`gbm.py`（LightGBM 面板全局模型，每 origin 重训 + 递归多步）、`models.py` 增 ARIMA(0,1,1)(Hannan–Rissanen)/Croston/TSB 与 `model_mapping()`、`backtest.py` 增 `backtest_global`、`experiment.py` + `make forecast`，新增 3 个测试文件（ml 27 passed）。`make forecast`（seeds 1–3 × 每 seed 分层 100 序列 × horizon 7/14/30）→ `ml/results/runs/20260919-1051_m4-forecast/`（含 `model_mapping.csv`）。horizon=7 总体 MASE：ma28 0.870 / croston 0.874 / tsb 0.883 / arima 0.895 / lightgbm 0.901 / naive 1.059；分象限 MASE：Croston 间歇 0.914、块状 0.932 优于 naive（1.051/1.044），LightGBM 波动 0.779、平滑 0.895 与 ma28/arima 接近。分层映射：平滑/波动 → LightGBM（对比 ARIMA）；间歇/块状 → Croston（对比 TSB）。
- [x] **M5 动态 SS/ROP + 可解释补货建议 + A/B 库存仿真**：新增 `ml/erp_ml/service_level.py`（**CSL 口径定稿**，见 ADR-0002：`z=Φ⁻¹(CSL)`、`SS=z·√(LT·σD²+D̂²·σLT²)`、`ROP=D̂·LT+SS`；Fill Rate 仅作输出指标）、`inventory.py`（固定/动态 `(s,S)` 最小-最大 + 日度 backorder 仿真 + 成本）、`forecast_layer.py`（复用 M4 象限映射：平滑/波动→LightGBM、间歇/块状→Croston，每 origin 重训）、`replenishment.py`（建议字段对齐 `db-schema.md` §12.6，含可用/ROP/S/SS/预测值/参数来源/reason）、`sim_experiment.py` + `make simulate`，新增 4 个测试文件（ml 58 passed）。`make simulate` 跑 **30 seed × 每 seed 分层 60 序列 × 130 origins**：A（固定 SS/ROP，用 180 天历史均值/σ）vs B（预测驱动动态 SS/ROP），同需求/同提前期随机流配对 → `ml/results/runs/20260919-1246_m5-simulation/`。**30 seed 配对 Wilcoxon**：总成本 B 比 A 低 **424.85**（p<1e-6）、缺货率低 **0.0038**（p<1e-6）、Fill Rate 高 **0.0051**（p=1.1e-4）、缺货损失低 **30.10**（p=6.5e-5）、订货次数少 **3.97**（p<1e-6）；平均库存/持有成本略升（+2.93 / +2.19，均显著），**CSL 差异不显著**（-9.7e-5，p=0.211）；分象限四象限总成本与 Fill Rate 均 B 更优。产出 `policy_metrics.csv`/`ab_summary.csv`/`policies.csv`/`replenishment_suggestions.csv`（1800 条、211 条 OPEN）/`cost_service_tradeoff.csv` + 3 张 300dpi 图。

- [x] **M6 补货决策闭环后端化（后端切片）**：新增预测与决策六表 ORM（`app/model/forecast.py`/`replenishment.py`：`demand_series_meta`/`model_registry`/`forecast_run`/`forecast_result`/`replenishment_policy`/`replenishment_suggestion`）+ 迁移 `0007_forecast_replenishment`（CHECK、唯一与部分唯一索引、完整 downgrade，PG 上 `upgrade→downgrade -1→upgrade` 可逆、`jsonb`/`postgresql_where` 生效）；分层实现：预测批次/结果入库（幂等 upsert、`FR-YYYYMMDD-####`）、需求序列元数据 upsert、模型注册；补货策略 CRUD；**决策服务**读取 `forecast_result`（最新 SUCCESS/PARTIAL 批次均值 D̂）+ `demand_series_meta.std_daily`（σD），按 CSL 公式 `SS=z·√(LT·σD²+D̂²·σLT²)`、`ROP=D̂·LT+SS`、`S=ROP+D̂·复核周期` 生成可解释建议（IP=结存−锁定+在途 ≤ ROP 才落库，qty=S−IP 按 min_order_qty/pack_size 向上取整，EOQ 仅参考，reason 含公式/可用量/参数来源）；建议确认（OPEN→SUGGESTED，可改 final_qty）/驳回；**一键转请购单**（SUGGESTED→CONVERTED，生成 DRAFT 请购单并写 `converted_pr_id/converted_at`，走既有状态机）；新增权限码 `replenishment:view/manage/convert`；新增 `tests/test_forecast.py`/`tests/test_replenishment.py`（11 条）。

- [x] **M6 前端补货建议页（方案 M6 的"前端 + 一键转请购单"验收项）**：新增前端工程（Vue 3 + TS + Vite 5 + Element Plus + vue-router + axios）：`frontend/package.json`、`vite.config.ts`（`/api` 代理到 127.0.0.1:8000、dev 仅绑 127.0.0.1:5173）、`tsconfig.json`、`eslint.config.js`（ESLint 9 flat + eslint-plugin-vue + typescript-eslint）；`src/api/http.ts` 统一解包 `{code,message,data,trace_id}`、401 跳登录；`src/composables/useAuth.ts`、`src/router` 登录守卫、`src/layouts/MainLayout.vue`、`LoginView.vue` 与 `ReplenishmentView.vue`（策略 CRUD、建议列表/详情/确认/驳回、单条与批量一键转请购单，详情展示可用量/ROP/SS/预测/参数来源/reason）；接口类型由后端 OpenAPI 生成（`openapi.json` + `src/api/schema.d.ts`，脚本 `npm run gen:api`），为此给 M6/认证/主数据接口补 `response_model`（新增 `backend/app/schema/common.py` 的 `ApiResponse[T]`/`PageOut[T]`），**不手写重复类型**。

- [x] **M7 子切片 1：Docker/Nginx/Compose 一键部署 + 部署文档**：`deploy/` 新增 backend/frontend Dockerfile（非 root、精简、healthcheck）、`nginx/default.conf`（静态托管 + `/api` 反代 + SPA history fallback + `/healthz`）、`backend-entrypoint.sh`（等库 → `alembic upgrade head` → 幂等 seed → uvicorn）、`smoke.sh` 与 `.env.example`；`docker-compose.yml` 在原有 `db` 服务（定义不变）上新增 `api`（不暴露宿主端口）与 `web`（仅 `127.0.0.1:${ERP_WEB_PORT:-8080}`），沿用项目默认网络/独立卷；`make up/down/ps/logs` 与 `make seed`（改用 `python -m scripts.seed`，消除 `PYTHONPATH` 坑）；新增 ADR-0003 部署拓扑。实测 `make up` 起 3 容器、`erp-postgres` 未被重建、`smoke.sh` 5/5、迁移 head、seed 幂等、`server-health.sh` 46/0/0 PASS。

- [x] **M7 子切片 2：系统测试 + Locust 性能测试**：新增 `backend/tests/test_system.py`（功能：请购→审批→转单→到货→验收→入库→结存对账；接口：统一响应 `{code,message,data,trace_id}`/`X-Trace-Id`/OpenAPI 可发现/错误包装；权限：匿名 401、只读 403、管理员放行）共 3 条；新增 `perf/`（`locustfile.py` 只读场景、`requirements.txt`、`README.md`）与 `make perf-venv`/`make perf`（Locust **headless**，不启 Web UI、不占 8089）。实测 20s/10 用户：**200 请求 / 0 失败**、聚合中位数 11ms、登录 ~587ms（bcrypt）。

- [x] **M7 子切片 3（余力）：LSTM 与 LightGBM 对比**：新增 `ml/erp_ml/lstm.py`（面板级 LSTM：`log1p`+逐序列标准化、均值/方差只用历史、每 origin 从零重训、递归多步、固定种子）与 `lstm_experiment.py`（**复用** `backtest_global` 的 rolling-origin 协议，输出 `comparison.csv` 配对差值与 Wilcoxon）、`ml/tests/test_lstm.py`（3 条）；torch 为 `ml` **可选依赖**（CPU 轮子，`make ml-lstm`）。`make lstm`（seeds 1–3 × 每 seed 分层 40 序列 × horizon 7/14/30）→ `ml/results/runs/20260919-1715_m7-lstm/`。horizon=7（配对 n=120）：**MASE LSTM 0.831 vs LightGBM 0.902（Δ=-0.071，p=1.8e-7）**、**MAE 3.65 vs 4.02（p=2.3e-10）**；分象限 LSTM 在波动/间歇/块状更优，**平滑象限 LightGBM 更优**；sMAPE 总体反向（109.2 vs 100.2），属零值多的 sMAPE 陷阱，以 MASE/MAE 为准。

- [x] **对外展示域名**：宿主 nginx 新增站点 `gra.sukicloud.top` → `127.0.0.1:8080`（复用 `*.sukicloud.top` 泛域名证书；仅新增 vhost、未改其他站点；`server-health` 46→47 PASS）；运维记录见 `/root/dsh/CHANGELOG-ops.md`。

- [x] **M8 主数据前端页（本会话垂直切片）**：新增 schema 驱动通用 CRUD 视图 `frontend/src/views/master/MasterDataView.vue` + 六类配置 `masterConfigs.ts`（物资分类/物资/单位/仓库/库位/供应商）：关键字与分类/仓库/状态筛选、分页、新增/编辑弹窗、删除（软删）、启停用；`src/api/master.ts` 六类 CRUD 封装，接口类型全部由 OpenAPI 生成；后端新增 `CurrentUserOut`，登录与 `/auth/me` 返回 `permissions`，前端 `useAuth.hasPerm` 按 `material:manage` 隐藏/禁用按钮；侧边栏新增「主数据」子菜单与路由（`/master/*`）；**未引入新依赖**。

- [x] **M8 子切片 2：采购 / 库存前端 + 接口类型化 + 部署更新**：给 `purchase.py`/`inventory.py`/`inventory_ops.py`/`ledger.py` 四组接口补 `ApiResponse[T]`/`PageOut[T]` 的 `response_model` 并重跑 `gen:api`；新增通用单据组件 `frontend/src/components/DocumentView.vue` + `document.ts`，新增 `src/api/purchase.ts`、`src/api/inventory.ts`、`src/composables/useMasterOptions.ts`、`src/utils/{format,status}.ts`；页面：请购单 / 采购订单 / 到货验收单、库存查询（结存/批次/流水 + 一键对账）、入库 / 出库 / 调拨 / 盘点单、库存预警；侧边栏增「采购管理」「库存管理」；动作按 `purchase:*`/`inventory:*` 权限隐藏；重建 api/web 镜像并 `make up`。

- [x] **现实演示数据入库**：新增 `backend/scripts/seed_demo.py` + `make seed-demo`（走 HTTP API，尊重状态机与库存不变量；主数据按编码幂等、单据以 `[DEMO]` 标记幂等）。已入库：单位 10 / 分类 21（两级树）/ 供应商 8 / 仓库 3 / 库位 10 / 物资 26；请购单 7、采购订单 5、到货验收单 5、入库单 4、出库单 4、调拨单 2、盘点单 2、库存结存 10、库存流水 17；状态覆盖草稿/待审/已审/执行中/完成；库存对账 `ok=true`。

- [x] **S2 预测结果接入后端 forecast_* 与补货决策（本会话垂直切片）**：新增 `ml/erp_ml/sync_forecast.py` + `make sync-forecast`（复用 `ml/.venv` 与 M3–M7 代码，仅标准库 HTTP）。以 `catalog_source="db"` **只读**业务主数据，为 26 物资 × 3 仓库生成 3 年日需求（seed=14），按 M4 分层映射（SMOOTH/ERRATIC→LightGBM、INTERMITTENT/LUMPY→Croston）输出未来 14 天预测；经后端 API 落库：**模型注册 2 / 预测批次 1（`FR-20260920-0001`，78 序列 × 14 步 = 1092 条结果，SUCCESS）/ 需求序列元数据 78 / 补货策略 1 / 补货建议 3（OPEN）**。重复执行幂等（批次数不变：新增 0、更新 3）；建议可解释（D̂/σD/SS/ROP/参数来源，`reason` 含 `model=lightgbm_demand`）；前端「补货决策」页直接展示，未改前端。新增 `ml/tests/test_sync_forecast.py`（6 条）与后端决策测试 2 条（最新 SUCCESS 批次生效 / RUNNING 批次忽略）。

- [x] **S3 操作日志写入与只读查询（本会话垂直切片）**：新增 `app/core/audit.py`（请求→审计字段的脱敏提取：路径/方法/状态/耗时/操作人，**绝不**读请求体/Authorization/cookie/query string）、`app/repository|schema|service|api/v1/operation_logs.py`（`GET /operation-logs` 分页 + user_id/module/action/result/时间区间过滤）、权限码 `operation:view`（seed 排序 80）；`main.py` 在 trace 内层新增审计中间件（响应后 best-effort、独立 session、失败只记 `app.audit` 日志，绝不影响主请求；request_id=响应 trace_id）；`get_current_user` 与登录接口写 `request.state.current_user` 捕获操作人；`operation_log` 表与四个索引在 `0001` 迁移已建，本切片**无需新迁移**。新增 `tests/test_operation_log.py`（5 条：成功/失败写入、trace 关联、脱敏、分页过滤/时间区间、匿名 401/越权 403/管理员 200）；conftest 用 `configure_bind` 让审计独立 session 落同一测试库。已重建 `erp-api`（`erp-postgres`/`erp-web` 未动），实机接口正常。

- [x] **S5 系统三表（docs/db-schema.md §13）落地（本会话垂直切片）**：
  - 迁移 `0008_system_tables` 建 `dict` / `scheduled_task_log` / `attachment`（CHECK、`uq_dict_type_key` 部分唯一索引、任务日志双索引、附件 biz/sha256 索引、完整 downgrade）；ORM `app/model/system.py`。
  - **dict**：两级语义（类型汇总 `GET /dict-types` + 项 CRUD `/dict-items`）+ 前端下拉 `GET /dicts/{dict_type}`（只返回启用项、按 sort_no）；预置 6 类展示字典（doc_status/alert_type/alert_level/abc_class/demand_class/priority，`app/core/dictionaries.py`，`scripts/seed.py` 幂等插入）。
  - **scheduled_task_log**：**只建表 + 记录接口，不引入调度器**；`POST /scheduled-task-logs`（追加 RUNNING/终态）、`POST /{id}/finish`（RUNNING→终态，自动算 duration_ms，终态再改 409）、`GET` 列表/详情（task_name/type/status/时间过滤）。
  - **attachment**：真实 multipart 上传/下载（`POST /attachments`、`GET /{id}/download`、列表/详情/软删）；扩展名 + MIME 白名单、大小上限（默认 10MB）、UUID 落盘名（不信任客户端文件名）、sha256、路径越界校验；本地存储根可配 `ERP_ATTACHMENT_DIR`。
  - 权限码 `dict:view/manage`、`task:view/manage`、`attachment:view/manage`（seed 90–95，ADMIN 自动授予）；错误码 6xxxx 段；审计 module 映射补齐 system。
  - 分层齐备：`schema/repository/service/api`（`app/**/system.py`）；统一响应 `{code,message,data,trace_id}`。
  - 测试 `tests/test_system_tables.py`（9 条：正常/边界/权限拒绝）；SQLite + 真 PG 双跑 9 passed。
  - 部署：`backend.Dockerfile` 建可写附件目录 + compose 新命名卷 `erp_erp-attachments`（挂 `/app/data/attachments`）+ 容器 nginx `client_max_body_size 12m`；`deploy/README.md`、`backend/.env.example`、`deploy/.env.example` 同步。

## 进行中

- [ ] 无

## 下一步（只做这一条）

**前端「操作日志」页面**：后端 `GET /operation-logs` 已就绪（分页 + user_id/module/action/result/时间区间过滤，权限码 `operation:view`）；新增 Vue 页面（列表/筛选/分页），重跑 `npm run gen:api` 同步 `src/api/schema.d.ts`，并按 `operation:view` 控制菜单可见性。

> S5 已新增系统三表后端接口（`/dict-types`、`/dict-items`、`/dicts/{type}`、`/scheduled-task-logs`、`/attachments`），**前端未做**（本会话后端优先）；`gen:api` 需在下一个前端切片一并重跑。S2/S5 的可选项见「已知坑」，均非阻塞。

> 开工建议换新对话框，从 `AGENTS.md` → `docs/progress.md` 继续。

## 已知坑 / 未决问题

| 项 | 说明 | 状态 |
|---|---|---|
| 运行库实例 | 已起独立 PG16 容器（`deploy/docker-compose.yml`，仅 127.0.0.1:5433）。真库验证：迁移 upgrade/downgrade 可逆、`jsonb`、`postgresql_where` 部分唯一索引、`COALESCE` 表达式唯一索引；测试支持 `ERP_TEST_DATABASE_URL` 对 PG 跑（M6 起 61 passed） | 已解决（2026-09-18） |
| 本机 Python 环境 | 系统缺 `python3-venv`，venv 用 `--without-pip` + get-pip 引导 | 已解决（backend/README.md） |
| 单据状态机 | 已实现：`core/state_machine.py` 单一事实来源（全局 6 态 + 7 类单据迁移边 + 权限码；仅请购单审批）；`apply_transition` 为唯一写 status 入口 | M2-a 完成 |
| 到货→入库联动 | 已实现：验收通过生成入库单，过账写流水并回写 PO 到货数量/状态 | M2-b 完成 |
| 领域不变量脚本 | `scripts/check_invariants.py`：状态机结构 + 权限码 + service 不直改 status + 库存只由 `service/stock_ledger.py` 过账且必须写流水 + 台账三表就位/快照不软删（verify 用 venv python 跑） | M2-b～M2-d 完成 |
| 操作日志写入 | `operation_log` 表已建，中间件写日志逻辑未实现 | 待后续切片 |
| 库存余额一致性 | `inventory` = 物资×仓库汇总、`inventory_batch` = 批次明细、`inventory_transaction` 为唯一真值源；已实现过账/红冲与 `GET /inventory/reconcile`（§14 三条+守卫），测试断言流水汇总 == 结存 | M2-b/M2-c 已实现并跑通（SQLite+PG 43 passed） |
| 已过账单据红冲 | 出库/调拨/盘点支持 `reverse`（IN_PROGRESS/COMPLETED→CANCELLED，写 REVERSAL 反向流水，不改/删历史流水）；调拨生成的出/入库单随调拨红冲；采购入库（delivery 来源）不允许直接红冲，需走采购/退货流程 | M2-c 完成（采购入库红冲待后续） |
| outbound_order.source_type 宽度 | §5.3 原 `varchar(16)` 放不下 `REQUISITION_ISSUE`(17)，PG 报 StringDataRightTruncation；已改 `varchar(32)` 并同步 `docs/db-schema.md` §5.3 | M2-c 修正（SQLite 不校验列宽，真库暴露） |
| 表数口径 | 全库 **41 张**（§2），方案写"约 36" | 已确认（采纳建议） |
| users/部门/默认批次 | `users` 复数命名、`dept_name` 文本、非批次用 `__DEFAULT__` 批次 | 已确认（Q1–Q3 采纳建议） |
| M1-b 开放问题 | M1B-Q1–Q7 见 `docs/db-schema.md` §15 | 已确认（采纳建议） |
| 预测与业务的边界 | ML 只读业务库、只写 `forecast_*` 与建议表 | 已写入 AGENTS.md |
| ML 运行环境 | `ml/.venv` 项目内隔离（Python 3.13，约 676MB）；沙箱下 `/dev/shm` 不可写 → joblib 自动退化串行（多进程不可用，代码为 joblib 并行就绪） | M3 记录 |
| 基线回测算力 | ETS（`estimated`+`optimized`）约 4.8s/序列；3 seed×100 序列全量约 25min；`make baseline` 固定 `--seeds 1 2 3 --max-series 100` | M3 记录 |
| 分层用全期观测 | ADI/CV² 用**全期**观测计算，仅用于分层报告/抽样，**不作预测特征**（避免未来信息泄漏） | M3 记录 |
| 数据生成器参数 | Bernoulli–Gamma / 对数正态提前期等参数已在 M3 冻结（`ml/erp_ml/config.py::GeneratorConfig`，见 `ml/README.md`） | 已冻结（2026-09-19） |
| 服务水平定义 | CSL 还是 Fill Rate？**全程必须一致** | **已定稿：CSL**（ADR-0002；`service_level_type='CSL'`，z=Φ⁻¹(CSL)，默认 0.95）；Fill Rate 仅作仿真输出对比（2026-09-19） |
| M4 特征维度 | 27 维 = 滞后 6 + 滑动 9 + days_since_nonzero 1 + 日历 7 + 静态 4；测试断言改写未来不改变特征 | M4 完成 |
| LightGBM 面板模型 | 跨序列全局模型，每个 origin 重训、递归多步；num_threads=2；沙箱 /dev/shm 不可写仍退化 joblib 串行（代码并行就绪）；全量约 10min | M4 记录 |
| ARIMA 估计 | 用 ARIMA(0,1,1) + Hannan–Rissanen（每 origin MLE 太慢）；差分后 MA(1)，与指数平滑同源 | M4 记录 |
| ETS 算力修正 | M3 记的"约 4.8s/序列"偏低；实测每 seed ETS 约 22–27min（seconds 1618/1331/1365s），故 M4 默认不含 ets，复用 M3 run | M4 修正 |
| 间歇/块状 sMAPE 陷阱 | 零值多时 sMAPE 奖励"全零"预测（naive 反而最低）；需看 MASE/MAE，Croston 明显更优 | M4 记录 |
| M5 EOQ 不适配间歇件 | EOQ 对低需求 SKU 会给出远超需求的订货量；M5 仿真改用 `(s,S)` 最小-最大（`S=ROP+D̂·复核周期`），EOQ 仅作参考量报告 | M5 记录 |
| M5 成本参数口径 | `order_cost` / `holding_cost_rate` / `stockout_penalty_rate` 为仿真实例设定（默认 100 / 0.20 / 0.5）；本合成数据单价小、订货成本主导总成本，故 `ab_summary.csv` 同时给持有/订货/缺货组件 | M5 记录 |
| M5 CSL 实收 vs 目标 | 正态近似 SS 在事件冲击/过度离散需求下，目标 CSL=0.95 的实收 CSL 偏低（需以仿真结果为准，论文只对**显著**差异写"优于"） | M5 记录 |
| M6 σLT 来源 | `replenishment_suggestion.sigma_lt` 库内暂无提前期波动数据，决策服务取 0（SS 公式第二项退化）；如需真实 σLT，应从历史提前期或供货价提前期估计 | M6 记录 |
| M6 service_level 量纲 | `replenishment_policy.service_level` 统一存小数（0<x<1，如 0.95），已同步修正 `db-schema.md §12.5`；z=Φ⁻¹(CSL) 用 Acklam 近似，未为此引入 scipy | M6 记录 |
| M6 在途口径 | 建议的 `in_transit_qty` 复用 `POItemRepo.in_transit_by_material()`（物料级、无仓库维度），与日快照口径一致 | M6 记录 |
| M6 下单量口径 | 按 M5 结论用 `(s,S)` 最小-最大（qty=S−IP），EOQ 仅作参考量；建议须人工确认（SUGGESTED）后才可转请购单 | M6 记录 |
| M6 提前期取值 | 决策服务提前期 = policy.lead_time_days > material.lead_time_days；暂未接入 §8 的供货价/供应商提前期优先级 | M6 记录 |
| M6 S（order_up_to）落点 | §12.6 无 `order_up_to` 列，S 写入 `reason` 文本；如需单独落库再加列 | M6 记录 |

| M6 前端工程 | 前端此前为空占位；本切片新增 Vue3+TS+Vite5+Element Plus 脚手架。依赖在 `frontend/node_modules`（项目内隔离、不入库）；接口类型由 `npm run gen:api` 从后端 OpenAPI 生成 | M6 完成 |
| M6 API 类型化 | 为让 OpenAPI 产出可用类型，给 M6/认证/主数据接口加了 `response_model`（`ApiResponse[T]`/`PageOut[T]`）；接口变更后需重跑 `npm run gen:api` 同步 `src/api/schema.d.ts` | M6 记录 |
| M6 前端未覆盖权限置灰 | 前端未按权限码隐藏按钮（`UserOut` 不含 permissions），越权时由后端 403 + 全局提示兜底 | M6 记录 |
| M6 dev 代理 | Vite dev 仅 `127.0.0.1:5173`，`/api` 代理到 `127.0.0.1:8000`；生产部署（nginx/静态托管）留 M7 | M6 记录 |
| M7 一键部署镜像源 | 本机 Docker Hub 不可达、已配置镜像 `docker.1ms.run` 极慢：构建前用 `docker.m.daocloud.io` 预拉 `python:3.12-slim`/`node:20-slim`/`nginx:1.27-alpine` 并 retag；Dockerfile 支持 `PIP_INDEX_URL`/`NPM_REGISTRY` 构建参数（默认官方源，`deploy/.env` 可覆盖） | M7 记录 |
| M7 `make down` 语义 | `make down` = `docker compose down`，会停止/移除本项目三个容器（含 `erp-postgres`，**卷保留**），`make up` 重建。仅限本项目栈，不影响其他服务 | M7 记录 |
| M7 访问方式 | 一键部署默认 `http://127.0.0.1:8080`（`deploy/.env` 的 `ERP_WEB_PORT` 可改）；**仅回环**，未做对外域名反代（需用户确认后再加） | M7 记录（待确认） |
| M7 alembic 日志 | `alembic current/upgrade` 会先打印两行格式模板字面量（`%(levelname)...`），为 `alembic.ini` 既有现象，迁移功能正常 | 既有 |
| M7 部署边界 | 容器只跑 `alembic upgrade head` + 幂等 seed；api 不对宿主暴露；web 容器内 nginx 与宿主 nginx 无关 | M7 记录 |
| M7 对外访问 | 宿主 nginx 站点 `gra.sukicloud.top` 反代到 `127.0.0.1:8080`（复用泛域名证书）；容器仍只回环，按 `newapi.sukicloud.top.conf` 参数新增，未改其他站点。回滚见 CHANGELOG-ops | M7 完成 |
| M7 性能测试端口 | Locust 用 `--headless`，不启动 Web UI（不占 8089），只对 `HOST`（默认 `127.0.0.1:8000`）发请求；场景全为只读 GET + 登录，不写业务表 | M7 记录 |
| M7 LSTM 依赖/成本 | torch 为 `ml` 可选依赖（CPU 轮子；装后 venv 约 1.6GB）；LSTM 每 origin 从零重训，本机 3 seed×40 序列约 20min（2 线程），已用 `windows_per_series`/`epochs` 控制成本 | M7 记录 |
| M7 LSTM vs GBM 结论 | MASE/MAE 上 LSTM 总体显著更优（波动/间歇/块状），但**平滑象限 LightGBM 更优**、sMAPE 总体反向；结论必须分象限、以 MASE/MAE 为准，禁止只报总体 sMAPE | M7 记录 |
| M8 当前用户权限 | 登录与 `/auth/me` 返回 `CurrentUserOut`（在 `UserOut` 上附带 `permissions`）；`/users` 未加 `response_model`，OpenAPI 不产出 `UserOut`，前端当前用户类型用 `CurrentUserOut` | M8 记录 |
| M8 主数据列表筛选 | 后端 `master` list 只支持 page/page_size；前端首版为「拉取前 200 条 + 内存筛选/分页」，超过 200 条需后续给后端加关键字/条件查询参数 | M8 记录 |
| M8 主数据编辑限制 | `MaterialCategoryUpdate` 无 `parent_id`、各 `*Update` 无 `code`、`LocationUpdate` 无 `warehouse_id`；前端这些字段编辑时禁用且不提交 | M8 记录 |
| M8 前端权限置灰 | 按钮按 `material:manage` 隐藏/禁用；后端 403 仍是最终兜底（不信任前端） | M8 记录 |
| M8 采购/库存接口类型化 | `purchase.py`/`inventory.py`/`inventory_ops.py`/`ledger.py` 已补 `response_model`（仅 delete 等 `ok(None)` 端点未加）；新增/改接口后必须重跑 `npm run gen:api` 同步 `src/api/schema.d.ts` | M8 记录 |
| M8 通用单据组件 | `src/components/DocumentView.vue` + `document.ts` 统一采购/库存列表页；动作 `silent` 用于打开弹窗类（自行提示/刷新）；列表服务端分页；删除仅草稿态可见 | M8 记录 |
| M8 下拉数据上限 | `useMasterOptions` 一次拉主数据前 200 条做下拉；物资 >200 时下拉不全，需后端加 keyword 查询后改为按需搜索 | M8 记录 |
| M8 验收库位 | `useMasterOptions` 无库位选项，到货验收的 `location_id` 用可选数字输入；后续可做「仓库→库位」联动下拉 | M8 记录 |
| M8 部署更新 | `make up` 重建 `erp-api`/`erp-web`（`erp-postgres` 不重建）；前端多阶段源码构建，`deploy/.env` 的 `NPM_REGISTRY`/`PIP_INDEX_URL` 走镜像源 | M8 记录 |
| M8 演示数据 | `make seed-demo`（`backend/scripts/seed_demo.py`）走 API 造数，需后端已运行（部署栈用 `make seed-demo BASE=http://127.0.0.1:8080`）；主数据按编码幂等、单据以 `[DEMO]` 标记整体跳过；脚本中途失败需先清理已生成单据再重跑 | M8 记录 |
| S2 序列口径/对应 | 不建「800 合成 SKU → 26 业务物资」手工对应表；用生成器业务目录模式（`catalog_source="db"`，只读主数据）按业务 `material_id × warehouse_id` 生成需求；`series_key = material_id:warehouse_id`（与后端 `ForecastService.series_key_for` 一致） | S2 记录 |
| S2 seed/触发选择 | 需求生成 seed=14（在 1–80 中筛选，使 10 个有结存的物资×仓组合产生 3 条触发，覆盖物资 9/21）；seed 是实验参数而非业务规则，随 token 记录、可复现 | S2 记录 |
| S2 幂等 | 批次幂等在脚本侧：稳定 token 写入 `forecast_run.remark`，命中即复用（不新建批次/不重复结果）；`demand-series-meta` 为 upsert，model-registry/policy 按编码跳过。强制新批次可用 `--batch-version`（或改 SEED/HORIZON） | S2 记录 |
| S2 预测区间 | 本批 `forecast_result.y_lower/y_upper` 留空（前端决策页不依赖；区间方法待定，避免过度声称） | 待后续切片 |
| S2 决策页模型名 | 建议表不单列模型名，模型名在建议详情 `reason`（`model=lightgbm_demand`）；若要列表列展示，需后端在建议出参补 `model_code` 并重跑 `gen:api` + 重建前端 | 待后续切片 |
| S2 策略 override 未生效 | 后端决策服务始终按预测公式算 SS/ROP，未读取 `safety_stock_override`/`rop_override`（`strategy=FIXED` 同此）；本次 `strategy=FORECAST` 不受影响 | 既有（M6） |
| S2 运行前置 | `make sync-forecast` 需后端已起（默认 8000；部署栈 `BASE=http://127.0.0.1:8080`）且 `127.0.0.1:5433` 业务库可读（只读 `material`/`warehouse`） | S2 记录 |
| S2 建议覆盖范围 | 决策服务只遍历 `inventory` 行（当前 10 个物资×仓组合），无结存物资不生成建议；要覆盖更多须先经业务单据入库（预测脚本绝不写业务表） | S2 记录 |
| S3 写入方式 | 请求级 `@app.middleware("http")` 在响应后落库；独立 session（不跨请求复用）；任何异常只记 `app.audit` 日志，绝不影响主请求 | S3 记录 |
| S3 request_id | 审计中间件挂在 trace 中间件**内层**，`request_id` 直接取 `trace_id_var`，与响应 `X-Trace-Id`/`trace_id` 一致 | S3 记录 |
| S3 脱敏口径 | 不读请求体/Authorization/cookie/query string；`detail` 仅 FAIL 时记 `status_code`；路径只存 `url.path`（无查询串） | S3 记录 |
| S3 跳过路径 | `/api/health`、`/api/docs`、`/api/redoc`、`/api/openapi.json` 与 `OPTIONS` 预检不落库，避免噪声 | S3 记录 |
| S3 action 口径 | `action` 取路由名（如 `login`/`get_forecast_run`/`list_material`），`module` 由路径前缀最长匹配；非语义化但可检索，够审计用 | S3 记录 |
| S3 权限/seed | 新增 `operation:view`（`PERMISSION_SEED` 排序 80）；`scripts/seed.py` 幂等补齐并授予 ADMIN。已存在的部署需重启 `erp-api`（入口自动 seed）或手动 `make seed` | S3 记录 |
| S3 前端类型未同步 | 本切片未动前端，故未重跑 `npm run gen:api`，`frontend/src/api/schema.d.ts` 暂无 `OperationLogOut`；前端页面切片时一并重跑 | 待后续切片 |
| S3 测试库接线 | conftest 新增 `configure_bind(engine, factory)`，使审计中间件的独立 session 落到同一测试库（SQLite StaticPool） | S3 记录 |
| S3 全套测试变慢 | 每个请求多一次日志 INSERT，后端 pytest 全套约 2.5min（原约 1min）；属预期 | S3 记录 |
| S3 迁移 | `operation_log` 表与 `created_at/user_id/action/request_id` 四索引在 `0001` 迁移已建，本切片无新迁移 | S3 记录 |
| S5 三表口径 | 三张表**全做**（后端优先）：dict 两级 CRUD + 下拉、scheduled_task_log 只建表+记录接口、attachment 真实上传下载；前端页面留后续切片 | S5 记录（采纳推荐） |
| S5 调度器 | **未引入** APScheduler/Celery（AGENTS：能不加依赖就不加）。`scheduled_task_log` 只提供记录/收尾/查询接口，供 shell+cron 或后台任务上报；真正调度属后续可选 | S5 记录 |
| S5 附件存储 | 文件本体落本地目录（容器内 `/app/data/attachments`，命名卷 `erp_erp-attachments`；本地默认 `data/attachments`，已被 `.gitignore` 的 `data/` 覆盖）；DB 只存元数据。**删除为软删元数据、文件本体保留**（可审计、可恢复），磁盘增长需人工清理 | S5 记录 |
| S5 附件安全 | 扩展名 + MIME 前缀双白名单、大小上限 `ERP_ATTACHMENT_MAX_SIZE_MB`（默认 10）、流式落盘超限即回滚半截文件、落盘名 UUID（绝不用客户端文件名做路径）、下载做路径越界校验、sha256 校验和 | S5 记录 |
| S5 新依赖 | 新增 `python-multipart`（FastAPI 处理 `multipart/form-data` 上传的官方必需件；不引入则 `UploadFile/Form` 路由无法注册）。无其他新依赖 | S5 记录 |
| S5 dict 边界 | `dict` 只放**展示型/可运营**字典；业务枚举仍以代码常量 + 列 CHECK 为单一事实源（§13.1）。预置 key 全部来自既有代码常量，`scripts/seed.py` **insert-only**（已存在不改，避免覆盖用户运营修改） | S5 记录 |
| S5 上传的 nginx 限制 | 容器内 `deploy/nginx/default.conf` 已加 `client_max_body_size 12m`（重建 `erp-web` 生效）；**宿主 nginx 站点 `gra.sukicloud.top.conf` 未改**（server-ops 硬边界只允许改 dsh*.conf），经公网上传大文件可能仍受宿主默认 `client_max_body_size 1m` 限制，需要时再单独申请改站点 | S5 记录（待确认） |
| S5 附件与业务单据关联 | `biz_type/biz_id` 仅存元数据、**不做外键**（跨模块松耦合，§13.3）；未做"单据存在性"校验。前端上传入口与单据详情附件区留后续 | S5 记录 |
| S5 前端类型未同步 | 本切片未动前端，故未重跑 `npm run gen:api`；`frontend/src/api/schema.d.ts` 暂无 `DictItemOut/ScheduledTaskLogOut/AttachmentOut`，前端切片时一并重跑 | 待后续切片 |

## 对账状态（库存相关改动必填）

| 日期 | 对账项 | 结果 |
|---|---|---|
| 2026-09-18 | M1-a 库存表设计口径：批次结存 = 物资×仓库×批次（`inventory_batch`）；汇总结存 = 物资×仓库（`inventory`） | 设计已冻结；库存模块未实现，无可跑数据 |
| 2026-09-18 | M1-b 对账 SQL 口径：`docs/db-schema.md` §14 四条检查 | 设计已冻结；M2 实现过账后执行 |
| 2026-09-18 | M2-a 采购单据（PR/PO/RCV）未写 `inventory` / `inventory_transaction`；到货→入库→流水联动在 M2-b | 不涉及库存过账，无对账数据；口径不变 |
| 2026-09-18 | M2-b 库存过账对账：①批次汇总 == 结存 ②流水汇总 == 结存 ③批次级流水 == 批次结存 ④无负结存/锁定超结存 | `reconcile.ok=true`；覆盖默认批次与批次物资；SQLite + PostgreSQL 双跑 34 passed |
| 2026-09-18 | M2-c 库存作业对账：出库/调拨/盘点过账与红冲后 ①批次==结存 ②流水==结存 ③批次级==流水 | `reconcile.ok=true`；出库可用量拦截、调拨两仓净额 0、盘点差异、红冲回滚均有测试；SQLite + PG 43 passed |
| 2026-09-18 | M2-d 预警/快照只读结存，不写 `inventory`/`inventory_transaction` | 不涉及结存变更；日快照 upsert 与实际结存一致，预警扫描可重复执行不产生重复 |
| 2026-09-19 | M3 数据生成只写 `data/`，预测只读业务库且只写 `ml/results/`；未触及 `inventory`/`inventory_transaction`/`forecast_*` | 不涉及结存变更；业务表零写入 |
| 2026-09-19 | M4 特征/GBM 实验只读合成数据与 `ml/results/`；未连接/未写业务库表，未触及 `inventory`/`inventory_transaction`/`forecast_*` | 不涉及结存变更；业务表零写入 |
| 2026-09-19 | M5 库存仿真：只读合成需求（内存生成，不重写 `data/`）与 `ml/results/`；未连接业务库，未写 `inventory`/`inventory_transaction`/`forecast_*`/`replenishment_*`；补货建议/策略仅为 ML 结果表（字段对齐 §12.5/§12.6） | 不涉及结存变更；业务表零写入 |
| 2026-09-19 | M6 决策服务只读 `inventory`（结存/锁定）与在途汇总，生成 `replenishment_*` 建议；不写 `inventory`/`inventory_batch`/`inventory_transaction`，不改变结存 | 不涉及结存变更；`GET /inventory/reconcile` 口径不变；SQLite + PG 双跑 61 passed |
| 2026-09-19 | M6 前端补货建议页仅通过 `/replenishment-*` API 读写建议/策略，不直连数据库；确认/转单调用后端既有事务与状态机 | 不涉及结存变更；前端只读 API，`converted_pr_id` 来源链由后端保证 |
| 2026-09-19 | M7 一键部署：容器启动只跑 `alembic upgrade head` + 幂等 seed（RBAC/管理员）；api/web 只走业务 API，不触碰 `inventory`/`inventory_batch`/`inventory_transaction` | 不涉及结存变更；部署前后业务表零写入；`GET /inventory/reconcile` 口径不变 |
| 2026-09-19 | M7 系统测试 + Locust 性能：系统测试用测试库覆盖入库过账并断言对账；Locust 场景仅 GET + 登录 | 系统测试 `reconcile.ok=true`；性能测试不写业务表、不改结存 |
| 2026-09-19 | M7 LSTM 对比：只读合成需求（内存生成），只写 `ml/results/`；未连接/未写业务库表 | 不涉及结存变更；业务表零写入 |
| 2026-09-19 | M8 主数据前端：仅通过 `/material-categories`、`/materials`、`/units`、`/suppliers`、`/warehouses`、`/locations` API 读写档案，不触碰 `inventory`/`inventory_batch`/`inventory_transaction`；登录返回权限码为只读 | 不涉及结存变更；`GET /inventory/reconcile` 口径不变；SQLite 后端 66 passed |
| 2026-09-19 | M8 采购/库存前端：仅通过 `purchase-requisitions`/`purchase-orders`/`supplier-deliveries`/`inbound-orders`/`outbound-orders`/`transfer-orders`/`stocktake-orders`/`inventory*`/`stock-alerts` API 操作；过账/红冲调用后端 service（`stock_ledger` 唯一结存入口），前端不直连库、不改结存；库存查询页提供一键 `GET /inventory/reconcile` | 不涉及结存变更；后端 66 passed，`make verify` 绿 |
| 2026-09-19 | M8 演示数据：通过 API 生成采购入库/出库/调拨/盘点，结存全部由 `stock_ledger` 流水推导；`GET /inventory/reconcile` 四条差异均为 0 | `reconcile.ok=true`；库存结存 10 行、流水 17 条；未直接改库结存 |
| 2026-09-20 | S2 预测接入：同步脚本只读业务主数据（`material`/`warehouse`）生成需求，只写 `forecast_*` 与 `replenishment_*`；决策服务只读 `inventory`（结存/锁定）与在途汇总，不写 `inventory`/`inventory_batch`/`inventory_transaction` | 不涉及结存变更；`reconcile` 口径不变；同步前后库存表零写入 |
| 2026-09-20 | S3 操作日志：审计中间件只读取请求元数据（路径/方法/状态/耗时/操作人）并只写 `operation_log`；不读请求体、不触碰 `inventory`/`inventory_batch`/`inventory_transaction` | 不涉及结存变更；`reconcile` 口径不变 |
| 2026-09-20 | S5 系统三表：只新增 `dict`/`scheduled_task_log`/`attachment` 三表与接口，不改任何库存/采购/预测表；附件只写本地磁盘 + 自身元数据 | 不涉及结存变更；`reconcile` 口径不变；真 PG 迁移 upgrade→downgrade -1→upgrade 可逆 |