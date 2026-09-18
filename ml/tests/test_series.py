import numpy as np

from erp_ml.series import adi_cv2, classify


def test_adi_cv2_smooth():
    adi, cv2, nonzero = adi_cv2(np.full(100, 5.0))
    assert adi == 1.0
    assert cv2 == 0.0
    assert nonzero == 100


def test_adi_cv2_intermittent():
    values = np.zeros(100)
    values[::2] = 4.0
    adi, cv2, nonzero = adi_cv2(values)
    assert adi == 2.0
    assert cv2 == 0.0
    assert nonzero == 50


def test_adi_cv2_all_zero():
    adi, cv2, nonzero = adi_cv2(np.zeros(30))
    assert adi == 30.0
    assert cv2 == 0.0
    assert nonzero == 0


def test_classify_boundaries():
    assert classify(1.0, 0.1) == "SMOOTH"
    assert classify(1.5, 0.1) == "INTERMITTENT"
    assert classify(1.0, 0.8) == "ERRATIC"
    assert classify(1.5, 0.8) == "LUMPY"
