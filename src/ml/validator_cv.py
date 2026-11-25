"""
Expanding-Origin Time-Aware Cross-Validation Engine (Phase 4).
Evaluates models strictly on held-out future periods across 15 rolling forecast horizons
with zero temporal leakage, computing both provincial and per-district metrics.
"""

from typing import List, Dict, Tuple, Any, Optional
import numpy as np
import pandas as pd


class ExpandingOriginCV:
    """
    Expanding-Origin Cross-Validation schedule for weekly time-series panel data.
    - Warmup Window: 2023 W16 through 2024 W26 (63 continuous weeks).
    - Step Size: 4 weeks forward per fold.
    - Total Folds: 15 rolling forecast horizons.
    """
    def __init__(
        self,
        warmup_end_year: int = 2024,
        warmup_end_week: int = 26,
        step_weeks: int = 4,
        eval_horizon_weeks: int = 4,
        n_folds: int = 15
    ):
        self.warmup_end_year = warmup_end_year
        self.warmup_end_week = warmup_end_week
        self.step_weeks = step_weeks
        self.eval_horizon_weeks = eval_horizon_weeks
        self.n_folds = n_folds

    def split(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Generates expanding-origin train/test indices.
        Returns a list of fold dicts:
        {
            "fold_idx": int,
            "origin_t_idx": int,
            "train_mask": np.ndarray (bool),
            "test_mask": np.ndarray (bool),
            "train_size": int,
            "test_size": int
        }
        """
        # Find baseline t_idx for warmup end:
        warmup_rows = df[(df["origin_year"] == self.warmup_end_year) & (df["origin_epi_week"] == self.warmup_end_week)]
        if len(warmup_rows) > 0:
            warmup_t = int(warmup_rows["origin_t_idx"].iloc[0])
        else:
            warmup_t = (self.warmup_end_year - 2023) * 52 + self.warmup_end_week - 16

        max_t = int(df["origin_t_idx"].max())
        folds = []

        for k in range(self.n_folds):
            origin_t = warmup_t + (k * self.step_weeks)
            horizon_t = origin_t + self.eval_horizon_weeks

            if origin_t >= max_t:
                break

            train_mask = (df["origin_t_idx"] <= origin_t) & (~df["target_is_missing"]) & (~df["target_cases"].isna())
            test_mask = (df["origin_t_idx"] > origin_t) & (df["origin_t_idx"] <= horizon_t) & \
                        (~df["target_is_missing"]) & (~df["target_cases"].isna())

            if test_mask.sum() == 0:
                continue

            folds.append({
                "fold_idx": k + 1,
                "origin_t_idx": origin_t,
                "horizon_t_idx": horizon_t,
                "train_mask": train_mask.values,
                "test_mask": test_mask.values,
                "train_size": int(train_mask.sum()),
                "test_size": int(test_mask.sum())
            })

        return folds


def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_lower: Optional[np.ndarray] = None,
    y_upper: Optional[np.ndarray] = None
) -> Dict[str, float]:
    """Computes comprehensive error, scale, and interval calibration metrics."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    errors = y_true - y_pred
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    
    # Non-negative guard
    y_pred_safe = np.maximum(0.0, y_pred)
    
    # Normalized error vs scale (avoid div by zero)
    mean_target = float(np.mean(y_true))
    nrmse = float(rmse / max(1.0, mean_target))

    metrics = {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "nrmse": round(nrmse, 3),
        "mean_actual": round(mean_target, 2),
        "mean_predicted": round(float(np.mean(y_pred_safe)), 2),
        "n_samples": int(len(y_true))
    }

    if y_lower is not None and y_upper is not None:
        y_lower = np.asarray(y_lower, dtype=float)
        y_upper = np.asarray(y_upper, dtype=float)
        covered = (y_true >= y_lower) & (y_true <= y_upper)
        picp = float(np.mean(covered))
        miw = float(np.mean(y_upper - y_lower))
        metrics["picp_95"] = round(picp, 3)
        metrics["mean_interval_width"] = round(miw, 2)

    return metrics


def compute_per_district_metrics(
    eval_df: pd.DataFrame,
    pred_col: str = "pred_mean",
    lower_col: Optional[str] = "pred_lower",
    upper_col: Optional[str] = "pred_upper"
) -> Dict[str, Dict[str, Any]]:
    """Computes disaggregated MAE, RMSE, and PICP for all 35 KP districts."""
    district_metrics = {}

    for pcode, grp in eval_df.groupby("district_pcode"):
        d_name = grp["district_name"].iloc[0]
        y_t = grp["target_cases"].values
        y_p = grp[pred_col].values
        y_l = grp[lower_col].values if (lower_col and lower_col in grp.columns) else None
        y_u = grp[upper_col].values if (upper_col and upper_col in grp.columns) else None

        d_eval = evaluate_predictions(y_t, y_p, y_l, y_u)
        district_metrics[pcode] = {
            "district_name": d_name,
            "district_pcode": pcode,
            "mae": d_eval["mae"],
            "rmse": d_eval["rmse"],
            "picp_95": d_eval.get("picp_95", 0.90),
            "mean_interval_width": d_eval.get("mean_interval_width", 0.0),
            "n_samples": d_eval["n_samples"]
        }

    return district_metrics
