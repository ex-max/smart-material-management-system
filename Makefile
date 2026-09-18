# 毕设项目统一入口（人和 agent 都用这几个命令）
.PHONY: verify test lint migrate gen-data serve clean

verify:            ## 质量门禁：结构 + lint + 测试 + 迁移可解析（交付前必跑）
	./scripts/verify.sh

test:              ## 后端测试
	cd backend && .venv/bin/python -m pytest -q

lint:              ## 后端 lint
	cd backend && .venv/bin/python -m ruff check .

migrate:           ## 应用数据库迁移
	cd backend && .venv/bin/alembic upgrade head

gen-data:          ## 生成模拟业务数据（参数见 docs/plan）
	cd ml && python -m erp_ml.generate --seed 1 --skus 800 --years 3

serve:             ## 本地起后端（开发用）
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

clean:
	rm -rf data/* ml/results backend/.pytest_cache frontend/dist
