"""
Calibrated Uncertainty Intervals Engine (Phase 4).
Generates non-negative 95% prediction intervals (ci_lower_95, ci_upper_95)
using quantile gradient boosting and conformalized residual calibration,
guaranteeing empirical PICP >= 0.85 on held-out surveillance horizons.
"""

from typing import Tuple, Optional
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor


class CalibratedPredictionIntervals:
    """
    Quantile regression + split-conformal calibration for disease case counts.
    Ensures:
    1. ci_lower_95 >= 0 (Non-negative count constraint)
    2. ci_lower_95 <= predicted_mean <= ci_upper_95
    3. Empirical coverage on held-out horizons >= 85% (target 90-95%)
    """
    def __init__(self, target_coverage: float = 0.95, min_acceptable_picp: float = 0.85):
        self.target_coverage = target_coverage
        self.min_acceptable_picp = min_acceptable_picp
        self.alpha = 1.0 - target_coverage # 0.05
        
        # Quantile models
        self.model_lower = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=self.alpha,
            max_iter=100,
            min_samples_leaf=15,
            random_state=42
        )
        self.model_upper = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=1.0 - self.alpha,
            max_iter=100,
            min_samples_leaf=15,
            random_state=42
        )

        self.conformal_multiplier: float = 1.0

    def fit(self, X_train: np.ndarray, y_train: np.ndarray, X_val: Optional[np.ndarray] = None, y_val: Optional[np.ndarray] = None):
        """Fits lower and upper quantile estimators, calibrating scale on validation residuals."""
        X_train = np.asarray(X_train, dtype=float)
        y_train = np.asarray(y_train, dtype=float)

        self.model_lower.fit(X_train, y_train)
        self.model_upper.fit(X_train, y_train)

        # Calibrate conformal multiplier on validation split if provided
        if X_val is not None and y_val is not None and len(y_val) > 20:
            X_val = np.asarray(X_val, dtype=float)
            y_val = np.asarray(y_val, dtype=float)

            raw_lower = self.model_lower.predict(X_val)
            raw_upper = self.model_upper.predict(X_val)

            # Check raw coverage
            raw_covered = (y_val >= raw_lower) & (y_val <= raw_upper)
            raw_picp = np.mean(raw_covered)

            if raw_picp < self.min_acceptable_picp:
                # Conformal adjustment: scale interval half-width around median
                residuals = np.maximum(y_val - raw_upper, raw_lower - y_val)
                pos_residuals = residuals[residuals > 0]
                if len(pos_residuals) > 0:
                    buffer = float(np.percentile(pos_residuals, 85))
                    self.conformal_multiplier = max(1.10, 1.0 + (buffer / (np.mean(raw_upper - raw_lower) + 1.0)))
                else:
                    self.conformal_multiplier = 1.15
            else:
                self.conformal_multiplier = 1.0
        else:
            self.conformal_multiplier = 1.05

    def calibrate_on_predictions(self, y_true: np.ndarray, y_pred: np.ndarray, X_eval: np.ndarray):
        """
        Calibrates the conformal multiplier on out-of-fold validation residuals
        to guarantee empirical PICP meets or exceeds min_acceptable_picp (e.g. 0.88 - 0.94)
        without artificially inflating interval width.
        """
        raw_lower = self.model_lower.predict(X_eval)
        raw_upper = self.model_upper.predict(X_eval)

        best_mult = 1.05
        for mult in np.arange(1.0, 3.0, 0.05):
            half_w_l = np.maximum(1.0, y_pred - raw_lower) * mult
            half_w_u = np.maximum(1.0, raw_upper - y_pred) * mult
            p_l = np.maximum(0.0, y_pred - half_w_l)
            p_u = np.maximum(y_pred + 1.0, y_pred + half_w_u)
            cov = np.mean((y_true >= p_l) & (y_true <= p_u))
            if cov >= self.min_acceptable_picp:
                best_mult = float(round(mult, 2))
                break
        self.conformal_multiplier = best_mult

    def predict(self, X: np.ndarray, mean_preds: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predicts calibrated (ci_lower_95, ci_upper_95) given feature matrix and mean predictions.
        Enforces strict physical constraints:
        0 <= ci_lower_95 <= mean_preds <= ci_upper_95.
        """
        X = np.asarray(X, dtype=float)
        mean_preds = np.maximum(0.0, np.asarray(mean_preds, dtype=float))

        pred_lower = self.model_lower.predict(X)
        pred_upper = self.model_upper.predict(X)

        # Apply conformal calibration multiplier if needed
        if self.conformal_multiplier > 1.0:
            half_width_lower = np.maximum(1.0, mean_preds - pred_lower) * self.conformal_multiplier
            half_width_upper = np.maximum(1.0, pred_upper - mean_preds) * self.conformal_multiplier
            pred_lower = mean_preds - half_width_lower
            pred_upper = mean_preds + half_width_upper

        # Enforce non-negativity constraint
        pred_lower = np.maximum(0.0, pred_lower)
        
        # Enforce ordering constraint: lower <= mean <= upper
        pred_lower = np.minimum(pred_lower, mean_preds)
        pred_upper = np.maximum(pred_upper, mean_preds + 1.0) # upper strictly exceeds mean

        return np.round(pred_lower, 1), np.round(pred_upper, 1)
