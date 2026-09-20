"""S2 垂直切片：把 ML 分层预测结果同步进业务库 forecast_*，并生成可解释补货建议。

数据流（预测/建议全部经后端 HTTP API 写入，绝不直连写业务库）：

    业务库主数据（只读 SELECT：material / warehouse）
      -> erp_ml 生成器（catalog_source="db"）产出「业务物资 × 仓库」日需求历史
      -> 分层预测：SMOOTH/ERRATIC -> LightGBM 面板模型；INTERMITTENT/LUMPY -> Croston
      -> API: POST /model-registry
              POST /forecast-runs -> POST /forecast-runs/{id}/results -> POST .../finish
              POST /demand-series-meta
              POST /replenishment-policies -> POST /replenishment-suggestions/generate

对应开工三问的推荐口径（用户已确认「按推荐来」）：
(a) 不做「800 合成 SKU -> 26 业务物资」的手工对应表；直接用生成器的业务目录模式
    （catalog_source="db"）为业务物资生成需求历史，material_id/warehouse_id 即业务主键。
(b) 用 ML 模型对业务库现有 26 个物资**重新生成**一个预测批次，而非把 M5 的合成
    seed 建议硬映射进来。
(c) series_key = "material_id:warehouse_id"（与后端 ForecastService.series_key_for 一致）。

边界（AGENTS 不变量 4/5）：
- 只读业务库主数据，只写 forecast_* 与 replenishment_*；绝不写 inventory/单据等业务表。
- 建议的 D̂/σD/SS/ROP 由后端决策服务计算并写入 reason（可解释）。

幂等（重复执行不产生重复批次/建议）：
- 预测批次用稳定 sync token 写进 run.remark；重复执行命中则复用，不新建批次、不重复结果。
- demand-series-meta 为 upsert；model-registry 按 (code,version)、policy 按 code 已存在则跳过。
- 建议生成对同 (物资,仓库) 的 OPEN/SUGGESTED 建议就地更新，不产生重复。

用法::

    # 一键部署栈（web 反代在 8080）
    cd ml && ERP_BASE_URL=http://127.0.0.1:8080 .venv/bin/python -m erp_ml.sync_forecast
    # 本地开发（后端 8000）
    cd ml && ERP_BASE_URL=http://127.0.0.1:8000 .venv/bin/python -m erp_ml.sync_forecast --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from .dataset import build_dataset
from .features import FeatureSpec
from .gbm import DEFAULT_LGB_PARAMS, LGBMForecaster
from .models import forecast, recommend_model

# 模型版本：与 M4/M7 结论绑定的固定版本号（进 model_registry.version 与逐条结果快照）
MODEL_VERSION = "v1-20260919"
# M4 结果来源（供 model_registry.metrics.source_run 追溯）
M4_RUN = "20260919-1051_m4-forecast"
# 预测批次幂等标记前缀
SYNC_MARKER = "[SYNC]"
# 全局预测驱动策略编码（material/warehouse 皆空 -> 对所有物资/仓库生效）
POLICY_CODE = "POL-FORECAST-26"
DEFAULT_DATABASE_URL = "postgresql+psycopg://erp:erp@127.0.0.1:5433/erp"


# ---------------------------------------------------------------------------
# 纯函数（可单测，不依赖网络/数据库）
# ---------------------------------------------------------------------------
def sync_token(seed: int, years: int, warehouses: int, horizon: int, batch_version: str) -> str:
    """稳定批次 token：同参数重复执行命中同一批次。"""
    return "forecast-business-s%d-y%d-w%d-h%d-%s" % (seed, years, warehouses, horizon, batch_version)


def find_existing_run(runs: list[dict], token: str) -> dict | None:
    """在已有批次里按 remark 中的 token 找幂等目标。"""
    for run in runs:
        if token in (run.get("remark") or ""):
            return run
    return None


def model_code_for(demand_class: str) -> str:
    """按 ADI/CV² 象限映射到注册模型编码（与 erp_ml.models.recommend_model 一致）。"""
    return "lightgbm_demand" if recommend_model(str(demand_class)) == "lightgbm" else "croston_demand"


def build_demand_meta_payloads(meta: pd.DataFrame, token: str) -> list[dict]:
    """把 build_dataset 产出的序列元数据转成 /demand-series-meta 入参。"""
    payloads: list[dict] = []
    for row in meta.itertuples():
        payloads.append(
            {
                "series_key": str(row.series_key),
                "material_id": int(row.material_id),
                "warehouse_id": int(row.warehouse_id),
                "data_start_date": str(row.data_start_date),
                "data_end_date": str(row.data_end_date),
                "obs_days": int(row.obs_days),
                "non_zero_days": int(row.non_zero_days),
                "adi": float(row.adi),
                "cv2": float(row.cv2),
                "demand_class": str(row.demand_class),
                "abc_class": str(row.abc_class),
                "mean_daily": float(row.mean_daily),
                "std_daily": float(row.std_daily),
                "remark": "S2 sync;token=" + token,
            }
        )
    return payloads


def build_result_payloads(
    meta: pd.DataFrame,
    predictions: np.ndarray,
    future_dates: pd.DatetimeIndex,
    horizon: int,
    model_version: str,
) -> list[dict]:
    """把 (horizon, n_series) 预测矩阵转成 /forecast-runs/{id}/results 入参。"""
    payloads: list[dict] = []
    for j, row in enumerate(meta.itertuples()):
        model_code = model_code_for(str(row.demand_class))
        for step in range(1, horizon + 1):
            value = float(predictions[step - 1, j])
            if not math.isfinite(value):
                value = 0.0
            payloads.append(
                {
                    "series_key": str(row.series_key),
                    "material_id": int(row.material_id),
                    "warehouse_id": int(row.warehouse_id),
                    "forecast_date": future_dates[step - 1].date().isoformat(),
                    "horizon_step": step,
                    "y_hat": round(max(value, 0.0), 4),
                    "model_code": model_code,
                    "model_version": model_version,
                    "demand_class": str(row.demand_class),
                }
            )
    return payloads


def build_model_specs(feature_config: dict | None) -> list[dict]:
    """本批次实际使用的两个模型（附录可追溯 M4/M7 指标来源）。"""
    return [
        {
            "model_code": "lightgbm_demand",
            "model_type": "LIGHTGBM",
            "version": MODEL_VERSION,
            "params": dict(DEFAULT_LGB_PARAMS),
            "feature_config": feature_config,
            "metrics": {
                "source_run": M4_RUN,
                "horizon": 7,
                "segment": "ALL",
                "mase": 0.900573,
                "smape": 99.5942,
                "mae": 4.3102,
                "note": "M4 面板全局模型；平滑/波动象限主用（对比 ARIMA），M7 平滑以外象限 LSTM 更优",
            },
            "is_active": True,
            "remark": "S2 同步批次引用；论文结论以 ml/results/runs/ 为准",
        },
        {
            "model_code": "croston_demand",
            "model_type": "CROSTON",
            "version": MODEL_VERSION,
            "params": {"season_length": 7, "variant": "croston"},
            "feature_config": None,
            "metrics": {
                "source_run": M4_RUN,
                "horizon": 7,
                "segment": "ALL",
                "mase": 0.874082,
                "smape": 101.093,
                "mae": 4.2301,
                "note": "M4 间歇/块状象限主用（对比 TSB）",
            },
            "is_active": True,
            "remark": "S2 同步批次引用；论文结论以 ml/results/runs/ 为准",
        },
    ]


def build_policy_payload() -> dict:
    """全局预测驱动策略：CSL=0.95，提前期回落到物资主数据。"""
    return {
        "policy_code": POLICY_CODE,
        "policy_name": "业务库物资预测驱动补货策略（S2 同步）",
        "material_id": None,
        "warehouse_id": None,
        "strategy": "FORECAST",
        "service_level_type": "CSL",
        "service_level": 0.95,
        "review_period_days": 7,
        "order_cost": 100,
        "holding_cost_rate": 0.2,
        "min_order_qty": 1,
        "pack_size": 1,
        "lead_time_days": None,
        "is_active": True,
        "remark": "S2 ML 同步；z=Φ⁻¹(0.95)，LT 取物资主数据",
    }


def run_layered_forecast(ds, horizon: int) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """对序列历史做「预测期在历史之后」的分层预测（长度 horizon × n_series）。

    LightGBM 用延伸日历 + 尾部 NaN 递归多步；Croston 只吃历史序列。严格只用历史。
    """
    matrix = ds.demand.astype(float)
    n_days, n_series = matrix.shape
    future_dates = pd.date_range(ds.dates[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    extended_dates = ds.dates.append(future_dates)
    padded = np.vstack([matrix, np.full((horizon, n_series), np.nan)])

    spec = FeatureSpec()
    forecaster = LGBMForecaster(spec=spec, params=dict(DEFAULT_LGB_PARAMS), num_boost_round=300)
    forecaster.fit(matrix, ds.dates, n_days)
    predictions = forecaster.forecast(padded, extended_dates, n_days, horizon)
    for j, demand_class in enumerate(str(c) for c in ds.meta["demand_class"]):
        if recommend_model(demand_class) != "lightgbm":
            predictions[:, j] = forecast("croston", matrix[:, j], horizon, 7)
    return predictions, future_dates


# ---------------------------------------------------------------------------
# HTTP 客户端（仅标准库；与 backend/scripts/seed_demo.py 风格一致）
# ---------------------------------------------------------------------------
class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None

    def _call(self, method: str, path: str, body=None, params=None):
        url = self.base_url + path
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url += ("&" if "?" in url else "?") + query
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                message = json.loads(raw).get("message", raw)
            except json.JSONDecodeError:
                message = raw
            raise ApiError("%s %s -> HTTP %s: %s" % (method, path, exc.code, message)) from None
        if payload.get("code") != 0:
            raise ApiError("%s %s -> code=%s: %s" % (method, path, payload.get("code"), payload.get("message")))
        return payload.get("data")

    def login(self, username: str, password: str) -> None:
        data = self._call("POST", "/api/v1/auth/login", {"username": username, "password": password})
        self.token = data["access_token"]

    def get(self, path: str, params=None):
        return self._call("GET", path, params=params)

    def post(self, path: str, body=None):
        return self._call("POST", path, body=body)

    def list_all(self, path: str, page_size: int = 200) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            data = self.get(path, {"page": page, "page_size": page_size})
            items.extend(data["items"])
            if not data["items"] or len(items) >= data["total"]:
                return items
            page += 1


# ---------------------------------------------------------------------------
# 同步主流程
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="S2：ML 分层预测同步进业务库 forecast_*，并生成补货建议")
    parser.add_argument("--base-url", default=os.environ.get("ERP_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument(
        "--database-url", default=os.environ.get("ERP_ML_DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    parser.add_argument("--admin-user", default=os.environ.get("ERP_ADMIN_USERNAME", "admin"))
    parser.add_argument("--admin-password", default=os.environ.get("ERP_ADMIN_PASSWORD", "admin123"))
    parser.add_argument("--seed", type=int, default=14, help="需求生成器 seed（进 token 与元数据，保证可复现）")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--warehouses", type=int, default=3)
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--horizon", type=int, default=14)
    parser.add_argument("--batch-version", default="v1")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true", help="只计算不写入")
    return parser


def _print_segments(meta: pd.DataFrame) -> None:
    counts = meta["demand_class"].value_counts().to_dict()
    print("  需求分层：" + "，".join("%s=%d" % (k, int(v)) for k, v in sorted(counts.items())))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = GeneratorConfig(
        seed=args.seed, years=args.years, warehouses=args.warehouses, start_date=args.start
    )
    token = sync_token(args.seed, args.years, args.warehouses, args.horizon, args.batch_version)

    print("读取业务库主数据（只读）并生成需求历史：catalog_source=db，seed=%d" % args.seed)
    ds = build_dataset(cfg, catalog_source="db", database_url=args.database_url)
    print(
        "  %d 天 × %d 序列（%d 物资 × %d 仓库）"
        % (ds.demand.shape[0], ds.n_series, ds.catalog.n_materials, ds.catalog.n_warehouses)
    )
    _print_segments(ds.meta)

    print("分层预测：LightGBM 面板 + Croston（预测期在历史之后，horizon=%d）" % args.horizon)
    predictions, future_dates = run_layered_forecast(ds, args.horizon)
    meta_payloads = build_demand_meta_payloads(ds.meta, token)
    result_payloads = build_result_payloads(ds.meta, predictions, future_dates, args.horizon, MODEL_VERSION)
    print(
        "  预测 %d 序列 × %d 步 = %d 条；预测期 %s → %s"
        % (ds.n_series, args.horizon, len(result_payloads), future_dates[0].date(), future_dates[-1].date())
    )
    print("  幂等 token：%s" % token)

    if args.dry_run:
        print("[dry-run] 不写入后端。")
        return 0

    api = ApiClient(args.base_url)
    api.login(args.admin_user, args.admin_password)
    print("已登录：%s（admin=%s）" % (args.base_url, args.admin_user))

    # 1) 模型注册（按 code+version 幂等）
    existing_models = api.list_all("/api/v1/model-registry")
    known = {(row["model_code"], row["version"]) for row in existing_models}
    created_models = 0
    for spec in build_model_specs(FeatureSpec().to_dict()):
        if (spec["model_code"], spec["version"]) in known:
            continue
        api.post("/api/v1/model-registry", spec)
        created_models += 1
    print("模型注册：新增 %d，已存在 %d" % (created_models, len(known)))

    # 2) 预测批次（remark 标记幂等：命中即复用，不产生重复批次）
    run = find_existing_run(api.list_all("/api/v1/forecast-runs"), token)
    if run is None:
        run = api.post(
            "/api/v1/forecast-runs",
            {
                "trigger_type": "MANUAL",
                "horizon_days": args.horizon,
                "train_start_date": ds.dates[0].date().isoformat(),
                "train_end_date": ds.dates[-1].date().isoformat(),
                "forecast_start_date": future_dates[0].date().isoformat(),
                "series_count": ds.n_series,
                "remark": "%s %s；catalog=db；model_mapping=lightgbm/croston" % (SYNC_MARKER, token),
            },
        )
        print("预测批次：新建 %s（id=%d）" % (run["run_no"], run["id"]))
    else:
        print("预测批次：命中已有 %s（id=%d，status=%s），幂等复用" % (run["run_no"], run["id"], run["status"]))

    # 3) 结果入库 + 结束批次（仅 RUNNING 批次可写；已结束则跳过）
    if run["status"] == "RUNNING":
        inserted = 0
        updated = 0
        for offset in range(0, len(result_payloads), args.chunk_size):
            chunk = result_payloads[offset : offset + args.chunk_size]
            counts = api.post("/api/v1/forecast-runs/%d/results" % run["id"], {"items": chunk})
            inserted += counts["inserted"]
            updated += counts["updated"]
        run = api.post("/api/v1/forecast-runs/%d/finish" % run["id"], {"status": "SUCCESS"})
        print("预测结果：inserted=%d，updated=%d；批次结束 status=%s" % (inserted, updated, run["status"]))
    else:
        print("预测结果：批次已结束，跳过重复写入")

    # 4) 需求序列元数据（upsert，供决策服务取 σD）
    for payload in meta_payloads:
        api.post("/api/v1/demand-series-meta", payload)
    print("需求序列元数据：upsert %d 条" % len(meta_payloads))

    # 5) 补货策略（按 code 幂等）
    if any(row["policy_code"] == POLICY_CODE for row in api.list_all("/api/v1/replenishment-policies")):
        print("补货策略：已存在 %s" % POLICY_CODE)
    else:
        api.post("/api/v1/replenishment-policies", build_policy_payload())
        print("补货策略：新建 %s" % POLICY_CODE)

    # 6) 生成补货建议（后端决策服务读最新 SUCCESS/PARTIAL 批次 + σD）
    result = api.post("/api/v1/replenishment-suggestions/generate")
    print(
        "补货建议：scanned=%(scanned)d created=%(created)d updated=%(updated)d closed=%(closed)d "
        "skipped_no_policy=%(skipped_no_policy)d" % result
    )
    for row in api.list_all("/api/v1/replenishment-suggestions"):
        print(
            "  - %s 物资#%d 仓#%d status=%s D̂=%s σD=%s SS=%s ROP=%s 建议=%s run=%s"
            % (
                row["suggestion_no"],
                row["material_id"],
                row["warehouse_id"],
                row["status"],
                row["daily_demand_hat"],
                row["sigma_d"],
                row["safety_stock"],
                row["rop"],
                row["suggested_qty"],
                row["forecast_run_id"],
            )
        )
    print("完成：批次 %s，token=%s" % (run["run_no"], token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
