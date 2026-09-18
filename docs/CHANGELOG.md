# 变更日志

格式：`## YYYY-MM-DD · <模块>` + 改动 / 原因 / 验证 / 回滚
（每个工作会话收尾时追加一条）

## 2026-09-18 · 数据库设计（M1-a）

- **改动**：新增 `docs/db-schema.md` —— 主数据(6) + 采购(6) + 库存作业(9) 共 **21 张表**的字段/类型/约束/索引/关系、通用约定（主键/审计/类型/状态机/单号/追溯）、E-R 图、领域不变量落点与接口契约；同步更新 `docs/progress.md`（已完成/进行中/下一步/已知坑/对账状态）。
- **原因**：`docs/progress.md` 的"下一步" M1-a —— 按方案先把主数据 + 采购 + 库存作业三组设计出来，供评审后再补其余四组。本会话评审决策：分类多级树、仅基本单位、仅请购单审批、批次可开关且结存到批次、到货分批并自动生成入库单、到货/调拨拆头行（三组由 19 → 21 张）、盘点差异走流水不新增调整单。
- **验证**：`make verify` 绿（结构/lint/测试/迁移 4 项因后端前端尚未落地而 skip）。
- **回滚**：`git revert <本次提交>`（仅涉及 `docs/`，无代码/迁移副作用）。

## 2026-09-18 · 项目规则 / 数据库设计评审结论

- **改动**：
  - `AGENTS.md`：收尾 DoD 增加第 5 步“`git push origin main`”，并新增第七节「远程仓库与同步」，写入 GitHub 地址 https://github.com/ex-max/smart-material-management-system。
  - `docs/db-schema.md`：§9 由“待确认 / 开放问题”改为“开放问题与已定结论”，Q1–Q8 全部采纳建议（users 命名、非批次默认批次 `__DEFAULT__`、部门用 `dept_name` 文本、单号计数+重试、bigint identity、库位可空、盘点整单过账、出库成本仅占位）。
  - `docs/progress.md`：已知坑状态改为“已确认（采纳建议）”；下一步移除“消化开放问题”。
- **原因**：用户评审指示——§9 开放问题全部采纳建议；并把 GitHub 仓库与“每次收尾同步”写入规则。
- **验证**：`make verify` 绿（跳过 4 项）。远程同步：`origin` 已指向 GitHub 仓库，推送结果见会话结论。
- **回滚**：`git revert <本次提交>`（仅文档与规则，无代码副作用）。

## 2026-09-18 · 数据库设计（M1-b：补全全库 41 张表）

- **改动**：`docs/db-schema.md` 追加第二部分 §10–§13 —— 组织与权限 6（users/roles/permissions/user_role/role_permission/operation_log）、台账与统计 5（inventory/inventory_transaction/stock_alert/inventory_snapshot_daily/material_supplier_price）、预测与决策 6（demand_series_meta/model_registry/forecast_run/forecast_result/replenishment_policy/replenishment_suggestion）、系统 3（dict/scheduled_task_log/attachment）；新增 §14 E-R 补充与四条库存对账 SQL、§15 M1-b 开放问题；同步修正 §0 范围、§2 总览（41 张）、§8 跨组契约（澄清 inventory 粒度：汇总表=物资×仓库、明细表=批次）。`docs/progress.md` 同步更新（M1-b 完成 / 下一步 M1-c / 已知坑 / 对账状态）。
- **原因**：`docs/progress.md` 的"下一步" M1-b —— 按 §8 接口契约补全其余四组，使全库设计闭环，供评审。
- **验证**：`make verify` 绿（结构/lint/测试/迁移 4 项仍 skip）；文档自检：§2 共 41 行、§10–§13 共 20 张表。
- **回滚**：`git revert <本次提交>`（仅 `docs/`，无代码/迁移副作用）。
- **备注**：按用户要求，本次提交**先不推送**，待评审通过后再 `git push origin main`。
