# perf —— Locust 性能测试（项目内隔离）

对后端做**可复现**的性能/并发冒烟，方案按 M7 采用 Locust。独立目录、独立 venv，
不进入后端运行依赖，也不进 `make verify`（需要先起服务）。

## 为什么单独隔离

- Locust 会带来 gevent/flask 等较重依赖，放进 `backend/.venv` 会拖慢测试与镜像；
- 性能测试需要一个**运行中的后端**，与单元/集成测试的纯内存库不同，单独目录更清晰。

## 安装与运行

```bash
make perf-venv     # 创建 perf/.venv 并安装 locust（项目内隔离）

# 先起后端（二选一）：
make serve         # http://127.0.0.1:8000 （本地开发）
make up            # http://127.0.0.1:8080 （一键部署栈，经 web 反代）

make perf          # 默认 http://127.0.0.1:8000，10 用户 / 30s，headless
```

可覆盖参数（make 变量）：

```bash
make perf HOST=http://127.0.0.1:8080 USERS=20 RATE=5 RUN_TIME=60s
```

## 端口约定（重要：本机多项目）

- Locust 用 `--headless`，**不启动 Web UI**，因此不占用 8089；
- 只对 `HOST` 发起连接；默认 `127.0.0.1:8000`（后端）或 `127.0.0.1:8080`（部署栈）；
- 不改任何监听端口，不影响本机其他项目。

## 场景与可复现性

- 登录一次拿 JWT，其余为只读 GET（health / me / materials / inventory /
  purchase-requisitions / replenishment-suggestions）；
- **不写业务表**，重复运行结果可比；
- 每个任务用固定 `name=` 归并统计；用户数/速率/时长在命令行固定。

> 说明：这里只给"后端自身"的性能基线（单机、合成数据规模）。若要做写路径
> 压测，请另建场景并指向一次性测试库，避免污染 `data/` 与业务表。

## 参考基线（本机 2026-09-19）

命令：`make perf HOST=http://127.0.0.1:8000 USERS=10 RATE=5 RUN_TIME=20s`
（本地 uvicorn + PostgreSQL 16 @127.0.0.1:5433，4 核）。

| 指标 | 值 |
|---|---|
| 总请求 / 失败 | 200 / **0（0.00%）** |
| 聚合中位数 | 11 ms |
| 聚合平均 / P95 | 41 ms / 340 ms |
| `GET /api/health` | avg 2 ms |
| `GET /api/v1/materials` 等只读 | avg 9–17 ms |
| `POST /api/v1/auth/login` | avg 587 ms（bcrypt 口令哈希，属预期） |

> 这是**相对基线**（用于回归对比），不是容量结论；换机器/数据规模数值会变。
