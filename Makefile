# 毕设项目统一入口（人和 agent 都用这几个命令）
.PHONY: verify test lint migrate gen-data baseline forecast ml-venv ml-test ml-lint serve clean

verify:            ## 质量门禁：结构 + lint + 测试 + 迁移 + ML（交付前必跑）
	./scripts/verify.sh

test:              ## 后端测试
	cd backend && .venv/bin/python -m pytest -q

lint:              ## 后端 lint
	cd backend && .venv/bin/python -m ruff check .

migrate:           ## 应用数据库迁移
	cd backend && .venv/bin/alembic upgrade head

gen-data:          ## 生成模拟业务数据（参数见 docs/plan；产物落 data/，不进 git）
	cd ml && .venv/bin/python -m erp_ml.generate --seed 1 --skus 800 --years 3 --out ../data

baseline:          ## M3 基线预测滚动回测（结果落 ml/results/，不进 git）
	cd ml && .venv/bin/python -m erp_ml.baseline --seeds 1 2 3 --skus 800 --years 3 --max-series 100 --tag m3-baseline

forecast:          ## M4 特征工程 + LightGBM 预测实验（结果落 ml/results/，不进 git）
	cd ml && .venv/bin/python -m erp_ml.experiment --seeds 1 2 3 --skus 800 --years 3 --max-series 100 --tag m4-forecast

ml-venv:           ## 创建 ML 独立虚拟环境并安装依赖（项目内隔离）
	cd ml && python3 -m venv --without-pip .venv \
	  && curl -fsSL -o /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py \
	  && .venv/bin/python /tmp/get-pip.py -q \
	  && .venv/bin/pip install -e ".[dev]"

ml-test:           ## ML 测试
	cd ml && .venv/bin/python -m pytest -q

ml-lint:           ## ML lint
	cd ml && .venv/bin/python -m ruff check .

serve:             ## 本地起后端（开发用）
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

clean:
	rm -rf data/* ml/results backend/.pytest_cache frontend/dist
