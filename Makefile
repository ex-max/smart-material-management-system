# 毕设项目统一入口（人和 agent 都用这几个命令）
.PHONY: verify test lint migrate gen-data baseline forecast simulate lstm ml-venv ml-test ml-lint ml-lstm perf-venv perf serve seed up down ps logs clean

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

simulate:          ## M5 动态 SS/ROP + 补货建议 + A/B 库存仿真（30 seed，结果落 ml/results/，不进 git）
	cd ml && .venv/bin/python -m erp_ml.sim_experiment --seeds $$(seq 1 30) --skus 800 --years 3 --max-series 60 --tag m5-simulation

ml-venv:           ## 创建 ML 独立虚拟环境并安装依赖（项目内隔离）
	cd ml && python3 -m venv --without-pip .venv \
	  && curl -fsSL -o /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py \
	  && .venv/bin/python /tmp/get-pip.py -q \
	  && .venv/bin/pip install -e ".[dev]"

ml-test:           ## ML 测试
	cd ml && .venv/bin/python -m pytest -q

ml-lint:           ## ML lint
	cd ml && .venv/bin/python -m ruff check .

ml-lstm:           ## 安装 LSTM 可选依赖（CPU torch，仅按需；项目内隔离）
	cd ml && .venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2"

lstm:              ## M7 余力：LSTM 与 LightGBM 对比（结果落 ml/results/，不进 git）
	cd ml && .venv/bin/python -m erp_ml.lstm_experiment --seeds 1 2 3 --max-series 40 --tag m7-lstm

serve:             ## 本地起后端（开发用）
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

seed:              ## 初始化 RBAC 参考数据 + 管理员（幂等；需可连库）
	cd backend && .venv/bin/python -m scripts.seed

perf-venv:         ## 创建性能测试独立虚拟环境（Locust，项目内隔离）
	cd perf && python3 -m venv --without-pip .venv \
	  && curl -fsSL -o /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py \
	  && .venv/bin/python /tmp/get-pip.py -q \
	  && .venv/bin/pip install -r requirements.txt

perf:              ## 性能测试（Locust headless，默认 127.0.0.1:8000；HOST/USERS/RATE/RUN_TIME 可覆盖）
	cd perf && ERP_PERF_HOST="$(or $(HOST),http://127.0.0.1:8000)" .venv/bin/locust -f locustfile.py --headless -u $(or $(USERS),10) -r $(or $(RATE),2) -t $(or $(RUN_TIME),30s) --only-summary

up:                ## 一键部署：构建并启动 web+api+db（仅 127.0.0.1:<ERP_WEB_PORT>）
	cd deploy && docker compose up -d --build

down:              ## 停止一键部署（保留数据卷，不删数据）
	cd deploy && docker compose down

ps:                ## 查看一键部署容器状态
	cd deploy && docker compose ps

logs:              ## 跟踪一键部署日志（Ctrl-C 退出）
	cd deploy && docker compose logs -f --tail=100

clean:
	rm -rf data/* ml/results backend/.pytest_cache frontend/dist
