"""ERP 后端 Locust 性能测试（只读为主，可复现、不污染业务数据）。

用法（见 perf/README.md）：
    make perf-venv
    make perf                                  # 默认 http://127.0.0.1:8000，10 用户 30s
    make perf HOST=http://127.0.0.1:8080 USERS=20 RUN_TIME=60s

设计要点：
- 只做 GET + 登录，不写业务表，重复运行结果可比、可复现；
- on_start 登录一次拿 JWT，任务里带 Bearer；
- 每个请求用 name= 归并，避免高基数 URL 打散统计；
- headless 模式不启动 Web UI（不占用 8089 等端口），只做对外连接。
"""

import os

from locust import HttpUser, between, task


class ErpUser(HttpUser):
    """模拟一个已登录的 ERP 用户，偏只读浏览。"""

    wait_time = between(0.5, 1.5)
    host = os.environ.get("ERP_PERF_HOST", "http://127.0.0.1:8000")

    username = os.environ.get("ERP_PERF_USERNAME", "admin")
    password = os.environ.get("ERP_PERF_PASSWORD", "admin123")

    def on_start(self) -> None:
        self.token = ""
        self._login()

    def _login(self) -> None:
        with self.client.post(
            "/api/v1/auth/login",
            json={"username": self.username, "password": self.password},
            name="POST /api/v1/auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                self.token = resp.json().get("data", {}).get("access_token", "")
                resp.success()
            else:
                resp.failure("login failed: HTTP %s" % resp.status_code)

    @property
    def _auth(self) -> dict:
        return {"Authorization": "Bearer " + self.token} if self.token else {}

    @task(2)
    def health(self) -> None:
        self.client.get("/api/health", name="GET /api/health")

    @task(3)
    def me(self) -> None:
        self.client.get("/api/v1/auth/me", headers=self._auth, name="GET /api/v1/auth/me")

    @task(4)
    def materials(self) -> None:
        self.client.get("/api/v1/materials", headers=self._auth, name="GET /api/v1/materials")

    @task(2)
    def inventory(self) -> None:
        self.client.get("/api/v1/inventory", headers=self._auth, name="GET /api/v1/inventory")

    @task(2)
    def requisitions(self) -> None:
        self.client.get(
            "/api/v1/purchase-requisitions", headers=self._auth, name="GET /api/v1/purchase-requisitions"
        )

    @task(2)
    def suggestions(self) -> None:
        self.client.get(
            "/api/v1/replenishment-suggestions", headers=self._auth, name="GET /api/v1/replenishment-suggestions"
        )
