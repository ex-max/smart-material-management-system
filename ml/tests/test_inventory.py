"""SS/ROP/EOQ 公式与库存仿真测试。"""

import numpy as np
import pytest

from erp_ml.inventory import (
    SimulationConfig,
    dynamic_policies,
    eoq,
    expand_policy_path,
    fixed_policy,
    lead_time_pool,
    lead_time_std,
    reorder_point,
    rolling_sigma_path,
    round_order_qty,
    safety_stock,
    simulate_series,
)
from erp_ml.service_level import z_for_csl


def _cfg(**kwargs) -> SimulationConfig:
    base = dict(
        start_day=0,
        warmup_days=0,
        review_period_days=7,
        order_cost=50.0,
        holding_cost_rate=0.2,
        stockout_penalty_rate=0.5,
        min_order_qty=1.0,
        pack_size=1.0,
    )
    base.update(kwargs)
    return SimulationConfig(**base)


def test_safety_stock_and_rop_formula():
    z = z_for_csl(0.95)
    ss = safety_stock(forecast_daily=10.0, sigma_d=2.0, lead_time_mean=5.0, sigma_lt=0.0, z_value=z)
    assert ss == pytest.approx(z * float(np.sqrt(5.0 * 4.0)), rel=1e-9)
    rop = reorder_point(10.0, 5.0, ss)
    assert rop == pytest.approx(50.0 + ss, rel=1e-9)


def test_safety_stock_includes_lead_time_variance():
    base = safety_stock(5.0, 1.0, 4.0, 0.0, 1.645)
    with_lt = safety_stock(5.0, 1.0, 4.0, 2.0, 1.645)
    assert with_lt > base


def test_lead_time_std_lognormal():
    assert lead_time_std(10.0, 0.0) == pytest.approx(0.0, abs=1e-12)
    assert lead_time_std(10.0, 0.35) == pytest.approx(10.0 * np.sqrt(np.exp(0.35**2) - 1.0), rel=1e-9)


def test_eoq_and_rounding():
    assert eoq(1000.0, 50.0, 10.0) == pytest.approx(np.sqrt(2 * 1000 * 50 / 10), rel=1e-9)
    assert eoq(0.0, 50.0, 10.0) == 0.0
    assert round_order_qty(7.2, min_order_qty=5.0, pack_size=4.0) == 8.0
    assert round_order_qty(1.0, min_order_qty=10.0, pack_size=1.0) == 10.0


def test_dynamic_policies_use_forecast_mean():
    forecast = np.array([[10.0, 20.0]])  # 1 origin, horizon 2
    sigma = np.array([2.0])
    policies = dynamic_policies(
        forecast, sigma, lead_time_mean=5.0, log_sigma_lt=0.0, unit_price=10.0, cfg=_cfg()
    )
    assert len(policies) == 1
    z = z_for_csl(0.95)
    assert policies[0].forecast_daily == pytest.approx(15.0)
    assert policies[0].ss == pytest.approx(z * np.sqrt(5.0 * 4.0), rel=1e-9)
    assert policies[0].rop == pytest.approx(15.0 * 5.0 + policies[0].ss, rel=1e-9)
    # 目标库存位置 S = ROP + D̂ · 复核周期
    assert policies[0].order_up_to == pytest.approx(policies[0].rop + 15.0 * 7.0, rel=1e-9)
    assert policies[0].eoq > 0


def test_fixed_policy_from_history():
    history = np.array([10.0, 10.0, 10.0, 10.0])
    policy = fixed_policy(history, lead_time_mean=4.0, log_sigma_lt=0.0, unit_price=10.0, cfg=_cfg())
    assert policy.forecast_daily == pytest.approx(10.0)
    assert policy.sigma_d == pytest.approx(0.0)
    assert policy.rop == pytest.approx(40.0)
    assert policy.order_up_to == pytest.approx(40.0 + 10.0 * 7.0)


def test_expand_policy_path_segments():
    policies = dynamic_policies(np.array([[1.0], [2.0]]), np.array([0.0, 0.0]), 3.0, 0.0, 10.0, _cfg())
    rop, s_path = expand_policy_path(policies, [0, 2], n_days=4)
    assert rop[0] == pytest.approx(policies[0].rop)
    assert rop[1] == pytest.approx(policies[0].rop)
    assert rop[2] == pytest.approx(policies[1].rop)
    assert rop[3] == pytest.approx(policies[1].rop)
    assert np.all(s_path > rop)
    assert s_path[0] == pytest.approx(policies[0].order_up_to)


def test_rolling_sigma_is_causal():
    demand = np.arange(20.0)
    origins = [10, 12]
    first = rolling_sigma_path(demand, origins, window=5)
    # 只污染 max(origins) 之后的数据：任一 origin 的窗口都不应受影响
    poisoned = demand.copy()
    poisoned[12:] = 999.0
    second = rolling_sigma_path(poisoned, origins, window=5)
    assert np.array_equal(first, second)


def test_lead_time_pool_deterministic():
    pool_a = lead_time_pool(8.0, 0.35, 16, np.random.default_rng(1))
    pool_b = lead_time_pool(8.0, 0.35, 16, np.random.default_rng(1))
    assert np.array_equal(pool_a, pool_b)
    assert np.all(pool_a > 0)


def test_simulate_backorder_fill_rate():
    demand = np.full(20, 10.0)
    # 初始 5，ROP=-1 且不下单：前 195 单位需求缺货
    result = simulate_series(
        demand,
        rop_path=np.full(20, -1e9),
        s_path=np.full(20, -1e9),
        lead_times=np.array([2.0]),
        start_day=0,
        initial_on_hand=5.0,
        unit_price=10.0,
        cfg=_cfg(),
    )
    assert result.metrics["demand_total"] == pytest.approx(200.0)
    assert result.metrics["backorder_qty"] == pytest.approx(195.0)
    assert result.metrics["fill_rate"] == pytest.approx(1.0 - 195.0 / 200.0, abs=1e-9)
    assert result.metrics["orders_placed"] == 0
    assert result.metrics["cycle_service_level"] == 1.0


def test_simulate_replenishment_cycle():
    demand = np.full(20, 10.0)
    result = simulate_series(
        demand,
        rop_path=np.full(20, 5.0),
        s_path=np.full(20, 260.0),
        lead_times=np.array([1.0]),
        start_day=0,
        initial_on_hand=0.0,
        unit_price=10.0,
        cfg=_cfg(),
    )
    # 第 0 天缺货 10，第 1 天到货 260 先补欠交，随后满足需求；20 天内只下 1 单
    assert result.metrics["orders_placed"] == 1
    assert result.metrics["backorder_qty"] == pytest.approx(10.0)
    assert result.metrics["fill_rate"] == pytest.approx(0.95)
    assert result.final_on_hand > 0


def test_simulate_warmup_discards_transient():
    demand = np.full(30, 10.0)
    result = simulate_series(
        demand,
        rop_path=np.full(30, 5.0),
        s_path=np.full(30, 100.0),
        lead_times=np.array([1.0]),
        start_day=0,
        initial_on_hand=0.0,
        unit_price=10.0,
        cfg=_cfg(warmup_days=5),
    )
    assert result.metrics["eval_days"] == 25
    assert result.on_hand.size == 25


def test_csl_ignores_warmup_stockout():
    demand = np.full(20, 10.0)
    result = simulate_series(
        demand,
        rop_path=np.full(20, 5.0),
        s_path=np.full(20, 1000.0),
        lead_times=np.array([1.0]),
        start_day=0,
        initial_on_hand=0.0,
        unit_price=10.0,
        cfg=_cfg(warmup_days=5),
    )
    # 仅预热期第 0 天缺货；评估窗口内无缺货、无新订货周期 -> CSL=1
    assert result.metrics["stockout_days"] == 0
    assert result.metrics["cycle_service_level"] == 1.0


def test_min_max_orders_up_to_target():
    demand = np.full(4, 10.0)
    result = simulate_series(
        demand,
        rop_path=np.full(4, 5.0),
        s_path=np.full(4, 50.0),
        lead_times=np.array([1.0]),
        start_day=0,
        initial_on_hand=0.0,
        unit_price=10.0,
        cfg=_cfg(),
    )
    # 首日 position=0 <= ROP，下单数量 = S - position = 50
    assert result.orders_placed == 1
