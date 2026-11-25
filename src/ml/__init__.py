"""
Sentinel Health Surveillance - Machine Learning Subsystem.
Provides leak-free feature stores, expanding-origin time-aware cross-validation,
baselines, calibrated quantile/conformal uncertainty intervals, and drift guardrails.
"""

from src.ml.feature_store import FeatureStore, assert_zero_future_leakage
from src.ml.baselines import (
    PersistenceBaseline,
    RollingMeanBaseline,
    SeasonalNaiveBaseline,
    SARIMAXBaseline
)
from src.ml.validator_cv import ExpandingOriginCV, evaluate_predictions
from src.ml.uncertainty import CalibratedPredictionIntervals
from src.ml.guardrails import ForecastGuardrail, compute_residual_drift

__all__ = [
    "FeatureStore",
    "assert_zero_future_leakage",
    "PersistenceBaseline",
    "RollingMeanBaseline",
    "SeasonalNaiveBaseline",
    "SARIMAXBaseline",
    "ExpandingOriginCV",
    "evaluate_predictions",
    "CalibratedPredictionIntervals",
    "ForecastGuardrail",
    "compute_residual_drift",
]
