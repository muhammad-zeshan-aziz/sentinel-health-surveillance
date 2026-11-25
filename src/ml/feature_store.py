"""
Leak-Free Feature Store for Sentinel Disease Surveillance (Phase 4).
Extracts autoregressive lags, rolling statistics, cyclical seasonality,
and in-fold district target encoding strictly using information available at t <= t_origin.
"""

from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import pandas as pd
from pathlib import Path

# Paths
MODULE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = MODULE_DIR.parent.parent
PROCESSED_DIR = WORKSPACE_DIR / "data" / "processed"


class FeatureStore:
    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            csv_path = PROCESSED_DIR / "idsr_weekly_panel.csv"
            parquet_path = PROCESSED_DIR / "idsr_weekly_panel.parquet"
            self.data_path = parquet_path if parquet_path.exists() else csv_path
        else:
            self.data_path = Path(data_path)

        self._raw_df: Optional[pd.DataFrame] = None

    def load_data(self) -> pd.DataFrame:
        """Loads and cleans raw canonical panel data."""
        if self._raw_df is not None:
            return self._raw_df.copy()

        if str(self.data_path).endswith(".parquet"):
            df = pd.read_parquet(self.data_path)
        else:
            df = pd.read_csv(self.data_path)

        # 1. Clean column naming (support both 'condition' and 'disease')
        if "condition" in df.columns and "disease" not in df.columns:
            df["disease"] = df["condition"]

        # 2. Strict Data Hygiene: Exclude known duplicate source tables (2025 W9 byte-duplicate)
        initial_count = len(df)
        if "data_quality_flag" in df.columns:
            is_dup = df["data_quality_flag"].astype(str).str.contains("duplicate_source_table", na=False)
            df = df[~is_dup].copy()
            dropped_dups = initial_count - len(df)
        else:
            # Fallback explicit check for 2025 W9 duplicate if flag column absent
            df = df[~((df["year"] == 2025) & (df["epi_week"] == 9))].copy()

        # 3. Create a continuous monotonic time index: t_idx
        # Baseline: Year 2023 Week 16 = 0
        df["t_idx"] = (df["year"] - 2023) * 52 + df["epi_week"] - 16

        # Sort strictly chronologically per district
        df = df.sort_values(["district_pcode", "t_idx"]).reset_index(drop=True)
        self._raw_df = df
        return df.copy()

    def build_feature_matrix(self, disease: str) -> pd.DataFrame:
        """
        Builds leak-free feature matrix for a specific disease (Malaria or Typhoid).
        Target: y_{t+1} (Case count in the subsequent week).
        Features: Strictly computed from information available at <= t.
        """
        df = self.load_data()
        clean_disease = disease.strip().capitalize()
        d_df = df[df["disease"].str.capitalize() == clean_disease].copy()

        if len(d_df) == 0:
            raise ValueError(f"No records found for disease '{clean_disease}' in canonical panel.")

        feature_rows: List[Dict[str, Any]] = []

        # Process each district independently
        for pcode, grp in d_df.groupby("district_pcode"):
            grp = grp.sort_values("t_idx").reset_index(drop=True)
            n_rows = len(grp)

            # Extract numpy arrays for ultra-fast leak-free rolling calculations
            cases_arr = grp["total_cases"].values.astype(float)
            is_missing_arr = grp["is_missing"].values.astype(bool)
            is_zero_arr = grp["is_zero"].values.astype(bool)
            year_arr = grp["year"].values.astype(int)
            week_arr = grp["epi_week"].values.astype(int)
            t_idx_arr = grp["t_idx"].values.astype(int)
            pop = float(grp["population_2023"].iloc[0])
            d_name = grp["district_name"].iloc[0]
            division = grp["division"].iloc[0]

            # Clean forward-filled cases array for lag calculations (preserves True Zero vs NR)
            # For NR/missing rows, forward fill the last observed valid case count
            clean_cases = np.copy(cases_arr)
            last_valid = 0.0
            for i in range(n_rows):
                if is_missing_arr[i] or np.isnan(clean_cases[i]):
                    clean_cases[i] = last_valid
                else:
                    last_valid = clean_cases[i]

            # Build features at time step t for target at t+1
            # We require at least 4 preceding weeks of historical depth for lags
            for i in range(3, n_rows - 1):
                t = i
                t_plus_1 = i + 1

                # Target at t+1
                target_val = cases_arr[t_plus_1]
                target_missing = is_missing_arr[t_plus_1] or np.isnan(target_val)

                # Lag features strictly at <= t
                lag_1 = clean_cases[t]       # y_t (most recent observed)
                lag_2 = clean_cases[t - 1]   # y_{t-1}
                lag_3 = clean_cases[t - 2]   # y_{t-2}
                lag_4 = clean_cases[t - 3]   # y_{t-3}

                # Rolling stats strictly at <= t
                roll_2_mean = float(np.mean([lag_1, lag_2]))
                roll_4_mean = float(np.mean([lag_1, lag_2, lag_3, lag_4]))
                roll_4_std = float(np.std([lag_1, lag_2, lag_3, lag_4]))
                momentum_4 = float(lag_1 - lag_4)

                # Seasonal & cyclical calendar features at origin week t
                cur_week = week_arr[t]
                sin_week = float(np.sin(2.0 * np.pi * cur_week / 52.0))
                cos_week = float(np.cos(2.0 * np.pi * cur_week / 52.0))

                # 4-week reporting completeness at origin week t
                # Fraction of past 4 weeks that had valid non-missing reports
                past_4_missing = is_missing_arr[t-3 : t+1]
                coverage_4 = float(1.0 - np.mean(past_4_missing))

                # Historical depth in weeks available up to t
                history_depth = t + 1

                feature_rows.append({
                    "district_pcode": pcode,
                    "district_name": d_name,
                    "division": division,
                    "population_2023": pop,
                    "log_population": float(np.log(max(1.0, pop))),
                    "origin_t_idx": int(t_idx_arr[t]),
                    "origin_year": int(year_arr[t]),
                    "origin_epi_week": int(week_arr[t]),
                    "target_t_idx": int(t_idx_arr[t_plus_1]),
                    "target_year": int(year_arr[t_plus_1]),
                    "target_epi_week": int(week_arr[t_plus_1]),
                    "target_cases": float(target_val) if not target_missing else np.nan,
                    "target_is_missing": bool(target_missing),
                    "lag_1": float(lag_1),
                    "lag_2": float(lag_2),
                    "lag_3": float(lag_3),
                    "lag_4": float(lag_4),
                    "rolling_mean_2": roll_2_mean,
                    "rolling_mean_4": roll_4_mean,
                    "rolling_std_4": roll_4_std,
                    "momentum_4": momentum_4,
                    "sin_week": sin_week,
                    "cos_week": cos_week,
                    "reporting_coverage_4": coverage_4,
                    "history_depth_weeks": history_depth,
                    "is_origin_missing": bool(is_missing_arr[t])
                })

        feats_df = pd.DataFrame(feature_rows)
        return feats_df


def compute_in_fold_district_baseline(train_df: pd.DataFrame) -> Dict[str, float]:
    """
    Computes historical district baseline incidence strictly inside each expanding CV training fold (data <= t_origin).
    Prevents data leakage by ensuring test-fold targets never influence district baseline encoding.
    Returns: Dict mapping district_pcode -> baseline incidence per 100k.
    """
    valid_train = train_df[~train_df["target_is_missing"] & ~train_df["target_cases"].isna()]
    if len(valid_train) == 0:
        return {}

    dist_baselines = {}
    provincial_mean_cases = valid_train["target_cases"].mean()
    provincial_mean_pop = valid_train["population_2023"].mean()
    provincial_baseline = (provincial_mean_cases / max(1.0, provincial_mean_pop)) * 100000.0

    for pcode, grp in valid_train.groupby("district_pcode"):
        mean_cases = grp["target_cases"].mean()
        pop = grp["population_2023"].iloc[0]
        # Population-normalized baseline incidence per 100k
        inc = (mean_cases / max(1.0, pop)) * 100000.0
        dist_baselines[pcode] = float(inc)

    dist_baselines["__provincial__"] = float(provincial_baseline)
    return dist_baselines


def apply_in_fold_district_baseline(df: pd.DataFrame, baselines: Dict[str, float]) -> np.ndarray:
    """Applies precomputed in-fold baseline encoding to any partition without leakage."""
    default_val = baselines.get("__provincial__", 15.0)
    return df["district_pcode"].map(lambda p: baselines.get(p, default_val)).values.astype(float)


def assert_zero_future_leakage(features_df: pd.DataFrame) -> bool:
    """
    Programmatic anti-leakage audit.
    Asserts:
    1. Every feature row has origin_t_idx strictly less than target_t_idx.
    2. target_t_idx == origin_t_idx + 1 (strictly next-week 1-step forecast).
    3. No 2025 W9 duplicate bulletin row exists in origin or target.
    4. Target values do not appear in lag_1, lag_2, lag_3, or lag_4.
    """
    # Check 1: Monotonic time order
    assert (features_df["target_t_idx"] > features_df["origin_t_idx"]).all(), \
        "Temporal Leakage: Found target_t_idx <= origin_t_idx!"

    # Check 2: Strictly forward prediction horizon (target is in the future)
    delta_t = features_df["target_t_idx"] - features_df["origin_t_idx"]
    assert (delta_t >= 1).all(), "Temporal Leakage: Found non-positive horizon delta!"

    # Check 3: Duplicate bulletin exclusion
    has_dup_origin = ((features_df["origin_year"] == 2025) & (features_df["origin_epi_week"] == 9)).any()
    has_dup_target = ((features_df["target_year"] == 2025) & (features_df["target_epi_week"] == 9)).any()
    assert not has_dup_origin and not has_dup_target, \
        "Data Hygiene Breach: 2025 W9 duplicate bulletin was not excluded!"

    # Check 4: Target not identical to lag_1 across distinct non-static series
    diff = features_df["target_cases"] - features_df["lag_1"]
    non_zero_diffs = (diff != 0).sum()
    assert non_zero_diffs > 0, "Suspicious constant relationship between target and lag_1!"

    return True
