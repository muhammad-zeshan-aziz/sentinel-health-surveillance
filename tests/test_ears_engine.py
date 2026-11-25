"""
Module 9: CDC EARS Outbreak Aberration & Historical Backtesting Tests.
Verifies weekly C1/C2/C3 math invariants, zero-variance standard deviation floor,
and disaggregated historical backtesting performance metrics for Malaria and Typhoid.
"""

import json
import pytest
from src.surveillance.ears_detector import EARSDetector

def test_ears_zero_variance_floor():
    detector = EARSDetector()
    # Constant historical baseline with zero variance
    history = [5.0] * 10
    current_cases = 15.0

    score = detector.compute_single_point(current_cases, history)
    assert score.z1 is not None
    # Must not produce division by zero / NaN / inf
    assert score.z1 == score.z1 # NaN check
    assert score.z1 > 2.0, "Spike from 5 to 15 must trigger aberration"
    assert score.c1_flag is True

def test_ears_c1_c2_c3_differentiation():
    detector = EARSDetector()
    # Baseline with sudden surge
    history = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 12.0, 14.0]
    current = 45.0

    score = detector.compute_single_point(current, history)
    assert score.z1 > 0
    assert score.z2 > 0
    assert score.c3 >= 0

def test_historical_backtest_results_file(paths):
    backtest_file = paths["data_processed"] / "backtest_results.json"
    assert backtest_file.exists(), "backtest_results.json must exist"

    with open(backtest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Disaggregated backtest metrics for Malaria and Typhoid
    assert "malaria" in data, "Missing Malaria backtest entry"
    assert "typhoid" in data, "Missing Typhoid backtest entry"

    m_mal = data["malaria"]["metrics"]
    assert m_mal["recall"] >= 0.70, f"Malaria recall {m_mal['recall']} below 70%"
    assert m_mal["precision"] > 0.15
    assert m_mal["average_lead_time_weeks"] >= 1.0

    m_typh = data["typhoid"]["metrics"]
    assert m_typh["recall"] >= 0.65, f"Typhoid recall {m_typh['recall']} below 65%"
    assert m_typh["average_lead_time_weeks"] >= 1.0

def test_hotspot_dual_layer_generation(paths):
    m_file = paths["data_processed"] / "hotspots_map_malaria.json"
    t_file = paths["data_processed"] / "hotspots_map_typhoid.json"

    assert m_file.exists() and t_file.exists()
    with open(m_file, "r", encoding="utf-8") as f:
        m_geo = json.load(f)

    assert len(m_geo["features"]) == 35
    for feat in m_geo["features"]:
        props = feat["properties"]
        assert "observed_tier" in props or "hotspot_tier" in props
        assert "forecast_tier" in props
