"""
CDC Early Aberration Reporting System (EARS) Outbreak Detection Engine (Phase 5).
Implements weekly C1, C2, and C3 aberration statistics with zero-division guards,
robust baseline windows, and strict separation of unsubmitted/missing reporting weeks.
"""

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class EARSScore:
    z1: float
    z2: float
    c3: float
    baseline_mean_c1: float
    baseline_std_c1: float
    baseline_mean_c2: float
    baseline_std_c2: float
    c1_flag: bool
    c2_flag: bool
    c3_flag: bool
    is_missing: bool


class EARSDetector:
    """
    Weekly CDC EARS Aberration Detector (Blueprint Section 5.7).
    - C1 (Mild): 7 preceding weeks (t-7 to t-1). Alert threshold Z1 >= 2.0
    - C2 (Medium): 7 preceding weeks with 2-week guardband (t-9 to t-3). Alert threshold Z2 >= 3.0
    - C3 (Severe): Cumulative 3-week excess sum(max(0, Z2(t-k) - 1)). Alert threshold C3 >= 2.0
    """
    C1_WINDOW: int = 7
    C2_WINDOW: int = 7
    C2_GUARDBAND: int = 2
    C1_THRESHOLD: float = 2.0
    C2_THRESHOLD: float = 3.0
    C3_THRESHOLD: float = 2.0
    MIN_VALID_WEEKS: int = 4

    @staticmethod
    def _safe_z(current_val: float, baseline_vals: np.ndarray) -> Tuple[float, float, float]:
        """
        Computes safe Z-score with Poisson standard error floor.
        Guarantees zero NaN or inf values even if baseline variance is 0.
        Returns: (z_score, mean, std)
        """
        valid = baseline_vals[~np.isnan(baseline_vals)]
        if len(valid) == 0:
            return 0.0, 0.0, 1.0

        mean = float(np.mean(valid))
        std = float(np.std(valid, ddof=1)) if len(valid) > 1 else 0.0

        # Safe dispersion floor: max(sample std, Poisson root mean, 1.0)
        safe_std = max(std, np.sqrt(max(mean, 1.0)), 1.0)
        z = (current_val - mean) / safe_std
        return float(z), mean, std

    def compute_single_point(
        self,
        current_case_count: Optional[float],
        history_cases: List[Optional[float]],
        is_missing: bool = False,
        prior_z2_scores: Optional[List[float]] = None
    ) -> EARSScore:
        """
        Calculates C1, C2, and C3 scores for a single surveillance time step t.
        history_cases must be ordered [y_{t-N}, ..., y_{t-2}, y_{t-1}].
        """
        if is_missing or current_case_count is None:
            return EARSScore(
                z1=0.0, z2=0.0, c3=0.0,
                baseline_mean_c1=0.0, baseline_std_c1=0.0,
                baseline_mean_c2=0.0, baseline_std_c2=0.0,
                c1_flag=False, c2_flag=False, c3_flag=False,
                is_missing=True
            )

        n_hist = len(history_cases)
        # Convert to numpy array with NaNs for missing history
        hist_arr = np.array([np.nan if x is None else float(x) for x in history_cases], dtype=float)

        # 1. C1 Window: past 7 weeks (t-7 to t-1)
        if n_hist >= self.C1_WINDOW:
            c1_slice = hist_arr[-self.C1_WINDOW:]
            z1, m1, s1 = self._safe_z(current_case_count, c1_slice)
        elif n_hist >= self.MIN_VALID_WEEKS:
            c1_slice = hist_arr
            z1, m1, s1 = self._safe_z(current_case_count, c1_slice)
        else:
            z1, m1, s1 = 0.0, float(current_case_count), 1.0

        # 2. C2 Window: past 7 weeks with 2-week guardband (t-9 to t-3)
        c2_needed = self.C2_WINDOW + self.C2_GUARDBAND # 9 weeks
        if n_hist >= c2_needed:
            c2_slice = hist_arr[-c2_needed : -self.C2_GUARDBAND]
            z2, m2, s2 = self._safe_z(current_case_count, c2_slice)
        elif n_hist >= self.MIN_VALID_WEEKS + self.C2_GUARDBAND:
            c2_slice = hist_arr[:-self.C2_GUARDBAND]
            z2, m2, s2 = self._safe_z(current_case_count, c2_slice)
        else:
            z2, m2, s2 = z1, m1, s1

        # 3. C3 Cumulative Excess: sum_{k=0..2} max(0, Z2(t-k) - 1.0)
        c3_sum = max(0.0, z2 - 1.0)
        if prior_z2_scores:
            for p_z2 in prior_z2_scores[-2:]:
                c3_sum += max(0.0, float(p_z2) - 1.0)

        # Flags
        c1_flag = bool(z1 >= self.C1_THRESHOLD)
        c2_flag = bool(z2 >= self.C2_THRESHOLD)
        c3_flag = bool(c3_sum >= self.C3_THRESHOLD)

        return EARSScore(
            z1=round(z1, 2),
            z2=round(z2, 2),
            c3=round(c3_sum, 2),
            baseline_mean_c1=round(m1, 2),
            baseline_std_c1=round(s1, 2),
            baseline_mean_c2=round(m2, 2),
            baseline_std_c2=round(s2, 2),
            c1_flag=c1_flag,
            c2_flag=c2_flag,
            c3_flag=c3_flag,
            is_missing=False
        )


def calculate_ears_scores_for_series(
    case_counts: List[Optional[float]],
    is_missing_list: List[bool]
) -> List[EARSScore]:
    """Calculates chronological EARS C1, C2, C3 scores across an entire district-disease series."""
    detector = EARSDetector()
    results: List[EARSScore] = []
    prior_z2_history: List[float] = []

    for t in range(len(case_counts)):
        val = case_counts[t]
        is_miss = is_missing_list[t] or (val is None)

        history = case_counts[:t]
        prior_z2 = prior_z2_history[-2:] if len(prior_z2_history) >= 2 else prior_z2_history

        score = detector.compute_single_point(
            current_case_count=val,
            history_cases=history,
            is_missing=is_miss,
            prior_z2_scores=prior_z2
        )
        results.append(score)
        prior_z2_history.append(score.z2)

    return results
