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

## 本切片范围（M6）

补货决策页：补货策略维护 + 建议列表/详情（含可用量/ROP/SS/预测值/参数来源/reason）+ 确认/驳回 + 单条/批量一键转请购单。其余业务模块前端后续切片补齐。
