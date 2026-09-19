# 前端（Vue 3 + TypeScript + Element Plus）

## 开发

```bash
npm install
npm run dev          # http://127.0.0.1:5173 ，/api 代理到 http://127.0.0.1:8000
```

后端先起：项目根目录 `make serve`（或 `cd backend && .venv/bin/uvicorn app.main:app --port 8000`）。默认账号 `admin / admin123`。

## 接口类型（不手写重复类型）

类型从后端 OpenAPI 生成（AGENTS：接口类型从后端 OpenAPI 生成）：

```bash
# 1) 导出后端 OpenAPI（backend 已激活 venv）
cd ../backend && .venv/bin/python -c "from app.main import app; import json; open('../frontend/openapi.json','w').write(json.dumps(app.openapi(), ensure_ascii=False, indent=2))"
# 2) 生成 TS 类型
cd ../frontend && npm run gen:api     # -> src/api/schema.d.ts
```

## 质量门禁

```bash
npm run lint         # eslint
npm run typecheck    # vue-tsc --noEmit
npm run build        # typecheck + vite build
```

`make verify` 第 4 项在检测到 `node_modules` 后会自动跑 `npm run -s lint`。

## 已实现页面

- **登录**：JWT 登录，401 自动跳登录页。
- **主数据（M8）**：物资分类 / 物资 / 单位 / 仓库 / 库位 / 供应商 六类 CRUD（关键字与条件筛选、分页、新增/编辑弹窗、软删除、启停用）；采用 schema 驱动的通用视图（`src/views/master/MasterDataView.vue` + `masterConfigs.ts`）。按钮按 `material:manage` 隐藏/禁用（后端 403 仍为最终兜底）。
- **采购（M8）**：请购单（提交/审批/转采购订单/作废）、采购订单（确认/作废）、到货/验收单（提交/验收入库/拒收作废），均支持新建弹窗与明细编辑。
- **库存（M8）**：库存查询（结存/批次/流水 + 一键对账）、入库单（过账/完成/红冲/作废）、出库单、调拨单、盘点单（开始/录入实盘/完成/红冲）、库存预警（扫描/确认/解决/忽略）。
- **补货决策（M6）**：补货策略维护 + 建议列表/详情（含可用量/ROP/SS/预测值/参数来源/reason）+ 确认/驳回 + 单条/批量一键转请购单。

采购/库存列表页统一复用 `src/components/DocumentView.vue`（列表/筛选/详情/动作，动作按 `purchase:*`/`inventory:*` 权限隐藏）。
