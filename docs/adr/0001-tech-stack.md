# ADR-0001 技术栈选型

- 状态：已接受
- 日期：2026-09-18

## 决策
后端 FastAPI + SQLAlchemy + Alembic + Pydantic + JWT；前端 Vue3 + TS + Element Plus + ECharts；
数据库 PostgreSQL；缓存/队列 Redis + Celery（后期）；算法 Pandas/Numpy/statsmodels/scikit-learn/LightGBM；
交付 Docker Compose + Nginx。

## 理由
业务模块（采购/库存/单据）与预测模块解耦；预测用 Python 生态；前端图表丰富便于答辩展示。

## 备选与否决
- Django + DRF：自带 admin/RBAC，省工期；但预测侧生态与 FastAPI 相当，且本项目前端自建 → 选 FastAPI。
- 同时上 Django 与 FastAPI：框架复杂度翻倍，否决。
