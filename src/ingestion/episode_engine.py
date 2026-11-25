"""
Disease Episode and Repeat-Test Deduplication Engine.
Implements clinical episode windows (30d Malaria, 42d Typhoid) and handles
late-arriving corrected laboratory results without double-counting.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
import uuid
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np

# Clinical episode windows per disease
EPISODE_WINDOWS_DAYS: Dict[str, int] = {
    "Malaria": 30,
    "Typhoid": 42,
    "Dengue": 21,
    "AWD_cholera": 14,
    "default": 30
}


def get_episode_window(disease: str) -> int:
    """Returns episode window in days for a given condition."""
    for k, v in EPISODE_WINDOWS_DAYS.items():
        if k.lower() == str(disease).strip().lower():
            return v
    return EPISODE_WINDOWS_DAYS["default"]


class EpisodeEngine:
    """
    Stateful or batch episode deduplicator and correction reconciler.
    Tracks active disease episodes per patient hash and updates preliminary results.
    """

    def __init__(self):
        # Key: (patient_hash, disease_lower) -> List of dicts with episode info:
        # [{ 'episode_id': UUID, 'start_date': date, 'latest_date': date }]
        self.patient_episodes: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        # Key: external_record_id -> latest record dict
        self.known_external_records: Dict[str, Dict[str, Any]] = {}

    def reset(self):
        """Clears in-memory episode tracking state."""
        self.patient_episodes.clear()
        self.known_external_records.clear()

    def process_records(self, df_or_records: Any) -> pd.DataFrame:
        """
        Processes a collection of laboratory records:
        1. Deduplicates exact duplicate submissions.
        2. Reconciles late-arriving corrected lab results (superseding preliminaries).
        3. Assigns episode_id and flags is_duplicate_test based on clinical episode windows.
        """
        if isinstance(df_or_records, pd.DataFrame):
            df = df_or_records.copy()
        elif isinstance(df_or_records, list):
            df = pd.DataFrame(df_or_records)
        else:
            raise TypeError("Expected pandas DataFrame or list of dicts.")

        if df.empty:
            return df

        # Ensure date columns are parsed
        if "test_date" in df.columns:
            df["test_date_parsed"] = pd.to_datetime(df["test_date"]).dt.date
        else:
            raise ValueError("Records must contain 'test_date'.")

        if "corrected_at" in df.columns:
            df["corrected_at_parsed"] = pd.to_datetime(df["corrected_at"], errors="coerce")
        else:
            df["corrected_at_parsed"] = None

        if "is_corrected" not in df.columns:
            df["is_corrected"] = False

        # Sort chronologically so preliminary records precede corrections,
        # and earlier test dates precede later repeats.
        df["_sort_key"] = df["test_date_parsed"]
        df = df.sort_values(by=["_sort_key", "is_corrected"], ascending=[True, True]).reset_index(drop=True)

        # ----------------------------------------------------
        # 1. Reconcile Late Corrected Records
        # ----------------------------------------------------
        # If external_record_id is present and a corrected record arrives for it,
        # the corrected record supersedes the earlier record.
        reconciled_rows = []
        ext_id_map: Dict[str, int] = {} # external_record_id -> index in reconciled_rows

        for _, row in df.iterrows():
            ext_id = str(row.get("external_record_id", "")).strip()
            is_corr = bool(row.get("is_corrected", False))

            if ext_id and ext_id in ext_id_map:
                prev_idx = ext_id_map[ext_id]
                prev_row = reconciled_rows[prev_idx]
                
                # Check if this row is a correction
                if is_corr or (row.get("corrected_at_parsed") is not None):
                    # Replace earlier preliminary record with corrected record
                    row_dict = row.to_dict()
                    row_dict["is_corrected"] = True
                    row_dict["_supersedes_id"] = prev_row.get("id", None)
                    reconciled_rows[prev_idx] = row_dict
                    continue
                else:
                    # Exact duplicate submission with same external_record_id: drop duplicate
                    continue
            else:
                row_dict = row.to_dict()
                if ext_id:
                    ext_id_map[ext_id] = len(reconciled_rows)
                reconciled_rows.append(row_dict)

        df_reconciled = pd.DataFrame(reconciled_rows)

        # ----------------------------------------------------
        # 2. Episode Grouping & Repeat-Test Deduplication
        # ----------------------------------------------------
        episode_ids = []
        is_duplicate_tests = []
        is_new_episodes = []

        for _, row in df_reconciled.iterrows():
            patient_hash = str(row.get("patient_hash", "")).strip()
            disease = str(row.get("disease", "")).strip()
            disease_lower = disease.lower()
            test_res = str(row.get("test_result", "")).strip().capitalize()
            test_date_val: date = row["test_date_parsed"]
            window_days = get_episode_window(disease)

            is_positive = test_res == "Positive"
            key = (patient_hash, disease_lower)

            if is_positive and patient_hash:
                # Check for active existing episode
                matched_episode_id = None
                if key in self.patient_episodes:
                    for ep in self.patient_episodes[key]:
                        # Days since episode start
                        days_diff = (test_date_val - ep["start_date"]).days
                        if 0 <= days_diff < window_days:
                            matched_episode_id = ep["episode_id"]
                            ep["latest_date"] = max(ep["latest_date"], test_date_val)
                            break

                if matched_episode_id:
                    # Repeat positive test within window: belongs to existing episode
                    episode_ids.append(matched_episode_id)
                    is_duplicate_tests.append(True) # Flagged: stay in lab tests, not new incident case
                    is_new_episodes.append(False)
                else:
                    # New clinical disease episode
                    new_ep_id = str(uuid.uuid4())
                    if key not in self.patient_episodes:
                        self.patient_episodes[key] = []
                    self.patient_episodes[key].append({
                        "episode_id": new_ep_id,
                        "start_date": test_date_val,
                        "latest_date": test_date_val
                    })
                    episode_ids.append(new_ep_id)
                    is_duplicate_tests.append(False)
                    is_new_episodes.append(True)
            else:
                # Negative / Indeterminate tests get an independent record episode ID
                episode_ids.append(str(uuid.uuid4()))
                is_duplicate_tests.append(False)
                is_new_episodes.append(False)

        df_reconciled["episode_id"] = episode_ids
        df_reconciled["is_duplicate_test"] = is_duplicate_tests
        df_reconciled["is_new_episode"] = is_new_episodes

        # Set case_status based on clinical test result and repeat status
        # Positive & not duplicate -> Confirmed Case
        # Suspected / Indeterminate -> Suspected Case
        # Duplicate test -> Repeat test (retains lab test volume)
        def derive_case_status(r):
            res = str(r.get("test_result", "")).strip().capitalize()
            if res == "Positive":
                return "confirmed"
            return "suspected"

        df_reconciled["case_status"] = df_reconciled.apply(derive_case_status, axis=1)

        # Cleanup internal sort columns
        drop_cols = [c for c in ["_sort_key", "test_date_parsed", "corrected_at_parsed"] if c in df_reconciled.columns]
        df_reconciled.drop(columns=drop_cols, inplace=True)

        return df_reconciled


def deduplicate_and_tag_episodes(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience functional wrapper for EpisodeEngine."""
    engine = EpisodeEngine()
    return engine.process_records(df)
