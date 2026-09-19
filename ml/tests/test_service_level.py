"""服务水平口径（CSL 定稿）测试。"""

import math

import pytest

from erp_ml.service_level import (
    CSL,
    FILL_RATE,
    SERVICE_LEVEL_TYPE,
    ServiceLevelSpec,
    describe,
    z_for_csl,
    z_for_fill_rate,
)


def test_primary_service_level_type_is_csl():
    assert SERVICE_LEVEL_TYPE == "CSL"


def test_z_for_csl_known_values():
    assert z_for_csl(0.95) == pytest.approx(1.6448536, abs=1e-5)
    assert z_for_csl(0.90) == pytest.approx(1.2815516, abs=1e-5)
    assert z_for_csl(0.50) == pytest.approx(0.0, abs=1e-9)


def test_z_for_csl_rejects_invalid_level():
    with pytest.raises(ValueError):
        z_for_csl(1.0)


def test_fill_rate_z_is_close_but_distinct():
    # 仅用于讨论：Fill Rate 的 z 与 CSL 不同源，但数值上单调
    assert z_for_fill_rate(0.95) > z_for_fill_rate(0.90)


def test_service_level_spec_roundtrip():
    spec = ServiceLevelSpec(CSL, 0.95)
    data = spec.to_dict()
    assert data["service_level_type"] == "CSL"
    assert data["z_value"] == pytest.approx(1.6449, abs=1e-3)
    assert math.isfinite(data["z_value"])


def test_unknown_service_level_type_raises():
    with pytest.raises(ValueError):
        ServiceLevelSpec("NOPE", 0.95)


def test_describe_mentions_csl():
    assert "CSL" in describe()
    assert FILL_RATE == "FILL_RATE"
