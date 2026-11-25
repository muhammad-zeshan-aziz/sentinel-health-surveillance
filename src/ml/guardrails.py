"""
Drift & Reporting-Gap Guardrails for Disease Surveillance (Phase 4).
Enforces automated forecast withholding when historical depth is insufficient (< 26 weeks)
or rolling reporting completeness drops (< 75%), and monitors operational prediction drift.
"""

from typing import Tuple, Optional, Dict, Any, List
import numpy as np


class ForecastGuardrail:
    """
    Automated Forecast Withholding Guardrail (Blueprint Section 5.6).
    Protects public health decision-makers from misleading forecasts generated
    under sparse historical data or unstable facility reporting gaps.
    """
    MIN_HISTORY_WEEKS: int = 26
    MIN_REPORTING_COVERAGE: float = 0.75

    @classmethod
    def evaluate(
        cls,
        district_pcode: str,
        history_depth_weeks: int,
        reporting_coverage_4: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether a forecast should be withheld.
        Returns: (is_withheld: bool, withholding_reason: Optional[str])
        """
        if history_depth_weeks < cls.MIN_HISTORY_WEEKS:
            return True, f"INSUFFICIENT_HISTORY: District has {history_depth_weeks} weeks (< {cls.MIN_HISTORY_WEEKS} required)"

        if reporting_coverage_4 < cls.MIN_REPORTING_COVERAGE:
            pct = int(round(reporting_coverage_4 * 100))
            return True, f"LOW_REPORTING_COVERAGE: 4-week reporting completeness is {pct}% (< 75% required)"

        return False, None


def compute_residual_drift(
    recent_residuals: List[float],
    historical_baseline_mae: float
) -> Dict[str, Any]:
    """
    Monitors operational forecast drift.
    Compares recent 4-week mean absolute error against historical cross-validation MAE.
    """
    if not recent_residuals or len(recent_residuals) == 0:
        return {
            "drift_ratio": 1.0,
            "status": "STABLE",
            "recent_mae": historical_baseline_mae,
            "baseline_mae": historical_baseline_mae,
            "drift_alert": False
        }

    recent_mae = float(np.mean(np.abs(recent_residuals)))
    baseline_safe = max(1.0, float(historical_baseline_mae))
    drift_ratio = round(recent_mae / baseline_safe, 2)

    if drift_ratio >= 1.80:
        status = "SIGNIFICANT_DRIFT"
        drift_alert = True
    elif drift_ratio >= 1.30:
        status = "MODERATE_DRIFT"
        drift_alert = False
    else:
        status = "STABLE"
        drift_alert = False

    return {
        "drift_ratio": drift_ratio,
        "status": status,
        "recent_mae": round(recent_mae, 2),
        "baseline_mae": round(historical_baseline_mae, 2),
        "drift_alert": drift_alert
    }
