# AGENTS.md — 本项目的工作约定（每个会话开工先读）

智能物资管理系统（毕设）。题目：《基于 Python 的智能物资管理系统设计与实现——融合机器学习的物资需求预测与补货决策研究》。
方案与页码预算见 `docs/plan/`；**当前进度与下一步见 `docs/progress.md`**；技术栈决策见 `docs/adr/`。

## 一、目录边界（改代码只在对应目录内）

| 目录 | 职责 | 约定 |
|---|---|---|
| `backend/` | FastAPI 业务服务（物资/供应商/采购/出入库/库存/权限） | 分层：`api/`(路由) → `service/`(业务) → `repository/`(数据) → `model/`(ORM)；路由不写业务逻辑 |
| `frontend/` | Vue3 + TS + Element Plus | 接口类型从后端 OpenAPI 生成，不手写重复类型 |
| `ml/` | 数据生成、特征、模型、评估、仿真 | **只读业务库，不写业务表**；结果落 `ml/results/`（不进 git） |
| `deploy/` | docker-compose / nginx | 只服务本项目，不碰宿主其他站点 |
| `docs/` | progress / CHANGELOG / ADR / 方案 | 每会话收尾必须更新 progress |
| `data/` | 生成的数据 | **不进 git**（`.gitignore` 已排除） |

## 二、命令（唯一入口，别自己发明）

```bash
make verify     # 质量门禁：结构 + lint + 测试 + 迁移可解析 —— 交付前必跑，必须绿
make test       # 后端 pytest
make lint       # 后端 ruff
make migrate    # alembic upgrade head
make gen-data   # 生成模拟数据（seed/skus/years 见 options）
make serve      # 本地起后端
```

## 三、每个会话的收尾要求（Definition of Done，缺一不可）

1. `make verify` **绿**（红的不许收尾，宁可回滚也不留坏状态）
2. `docs/progress.md` 更新（已完成 / 进行中 / 下一步 / 已知坑）
3. `docs/CHANGELOG.md` 追加一条（改动 / 原因 / 验证 / 回滚）
4. `git commit`（Conventional Commits：`feat(采购): …` / `fix(库存): …` / `docs: …`）
5. **同步远程**：`git push origin main` —— 每个会话收尾都要推送到 GitHub（地址见第七节）
6. 会话结束时项目必须**可运行**：迁移能升、服务能起、测试能过

## 四、硬规则

- **一个会话只做一个垂直切片**（一个模块或一次重构），不跨模块顺手改。
- **不要动 `docs/plan/` 里的方案与页码预算**；要改先说明理由并记 ADR。
- **不引入新依赖前先说明理由**；能不加就不加（答辩要能解释每个依赖）。
- **业务规则不许猜**：物资分类口径、单据流转与审批规则、验收标准 → 问人。
- **密钥不进仓库**：用 `.env`（提供 `.env.example`），`data/`、`ml/results/` 不进 git。
- **金额/数量用 `Decimal`**，浮点只用于预测与统计。
- **时间统一 UTC 存储、展示按 Asia/Shanghai**；所有业务表带 `created_at/updated_at/created_by`。
- 库存相关改动必须同时更新 `docs/progress.md` 的"对账状态"（见 `erp-db-migration` 技能）。
- **服务器缺环境→自行安装**：项目需要的运行环境（如 PostgreSQL）服务器上没有时，**自行安装/启动，不必等用户逐条授权**；但必须按 `server-ops` 技能隔离且可回滚：
  - 优先**项目内隔离**方案（`deploy/docker-compose.yml` 的独立容器 + 独立卷），**只监听 `127.0.0.1`**，先 `ss -lntp` 确认端口空闲，不影响既有服务；
  - 不 `apt upgrade`、不改内核/防火墙/其他站点；不 stop / rm / prune 既有容器、不动既有 volume；
  - 改动前后各跑一次 `/root/dsh/server-health.sh` 对比，并在 `/root/dsh/CHANGELOG-ops.md` 记录（改动/原因/验证/回滚/影响）；
  - 连接串/端口写进 `deploy/README.md` 与 `.env.example`；新容器要加入 health 清单，避免"未在清单内"告警。

## 五、领域不变量（违反即 bug）

1. **库存余额只能由流水推导**：所有单据只写 `inventory_transaction` + 同事务更新 `inventory`，并提供对账任务。
2. **单据必须走状态机**：草稿→待审→已审→执行中→完成/作废；状态迁移受权限约束，不允许直接改状态字段。
3. **任何单据行必须可追溯**：来源单据号 + 操作人 + 时间。
4. **预测模块不得写业务表**：预测结果只落 `forecast_*` 表，供补货建议读取。
5. **补货建议必须可解释**：给出触发依据（当前库存、在途、ROP、SS、预测值、参数来源）。

## 六、按需加载的技能（用 `skill` 工具）

- `erp-conventions`：命名/分层/错误码/事务与锁/提交规范
- `erp-db-migration`：Alembic 流程 + 库存余额对账 checklist
- `forecast-experiment`：滚动回测协议 + 结果落盘 + 表格模板
- `server-ops`：动服务器 / 装环境 / 改配置前必读（硬边界、health 前后对比、回滚与 CHANGELOG-ops）

## 七、远程仓库与同步（每个会话收尾必做）

- **远程仓库**：`origin` → https://github.com/ex-max/smart-material-management-system
- **默认分支**：`main`（本地与远程保持一致）
- **收尾顺序**：`make verify` 绿 → 更新 `docs/progress.md` 与 `docs/CHANGELOG.md` → `git commit` → **`git push origin main`**。
- 推送前确认没有把密钥/token/`.env`/`data/`/`ml/results/` 带进提交（`make verify` 第 2 项会查）。
- **推送失败不许静默跳过**：无凭据或网络不可用时，在会话结束说明中写明“本地已提交、未推送 + 原因”，并给出恢复命令。
- 凭据只放本机（SSH key 或 git credential helper），**不得写入仓库**。
