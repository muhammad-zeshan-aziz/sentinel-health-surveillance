"""
Module 8: Conformal Prediction Uncertainty & Operational Guardrails Tests.
Verifies calibrated 95% intervals (PICP >= 0.85, 0 <= lower <= mean <= upper),
drift detection scoring, and automatic forecast withholding.
"""

import pytest
import numpy as np
from src.ml.uncertainty import CalibratedPredictionIntervals
from src.ml.guardrails import ForecastGuardrail, compute_residual_drift

def test_prediction_interval_ordering_and_non_negative():
    engine = CalibratedPredictionIntervals(target_coverage=0.95)
    np.random.seed(42)
    X = np.random.randn(40, 4)
    y = np.abs(X[:, 0] * 10 + 20)
    engine.fit(X, y)

    preds = np.array([12.0, 25.0, 50.0])
    X_test = np.random.randn(3, 4)
    low, high = engine.predict(X_test, preds)

    assert (low >= 0.0).all(), "Lower interval bound must always be non-negative"
    assert (low <= preds).all(), "Lower bound must be <= predicted mean"
    assert (preds <= high).all(), "Predicted mean must be <= upper bound"

def test_held_out_picp_coverage_in_database(db_session):
    from backend.models.ml import ModelRegistry
    active_models = db_session.query(ModelRegistry).filter(ModelRegistry.is_active == True).all()

    import json
    for m in active_models:
        metrics = json.loads(m.metrics)
        picp = metrics.get("conformal_picp_95") or metrics.get("picp_95") or metrics.get("picp")
        assert picp is not None, f"Model {m.model_name} missing PICP metric"
        assert picp >= 0.85, f"Model {m.model_name} PICP {picp} is below 0.85 target threshold"

def test_guardrails_withholding_on_short_history():
    guard = ForecastGuardrail()
    # District with only 12 weeks of historical records (< 26 weeks required)
    is_withheld, reason = guard.evaluate("PK501", history_depth_weeks=12, reporting_coverage_4=0.90)
    assert is_withheld is True
    assert "INSUFFICIENT_HISTORY" in reason

def test_guardrails_withholding_on_poor_coverage():
    guard = ForecastGuardrail()
    # District with 50 weeks history but only 60% reporting coverage (< 75% threshold)
    is_withheld, reason = guard.evaluate("PK501", history_depth_weeks=50, reporting_coverage_4=0.60)
    assert is_withheld is True
    assert "LOW_REPORTING_COVERAGE" in reason

def test_residual_drift_computation():
    recent = [1.2, 1.8, 1.4, 0.6, 2.3, 1.1]
    baseline_mae = 1.0
    drift_result = compute_residual_drift(recent, baseline_mae)
    assert "drift_ratio" in drift_result
    assert "status" in drift_result
    assert drift_result["drift_ratio"] >= 0.0
