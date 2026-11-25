"""
Strict Ingestion & Schema Validator for Hospital/Laboratory Submissions.
Validates required columns, ISO dates, P-Codes, age bands, and disease values,
detects duplicates and corrections, and outputs privacy-safe quality summaries.
"""

from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from datetime import datetime, date
import re
import pandas as pd
import numpy as np

from src.ingestion.crosswalk import resolve_district_pcode, CANONICAL_KP_DISTRICTS
from src.ingestion.pseudonymizer import scan_for_pii, sanitize_dataframe, hash_patient_id

VALID_AGE_BANDS = {"0-4", "5-14", "15-24", "25-44", "45-64", "65+"}
VALID_TEST_RESULTS = {"positive", "negative", "indeterminate"}
VALID_DISEASES = {
    "malaria", "typhoid", "ad_noncholera", "ili", "sari", "alri_u5",
    "bloody_diarrhoea", "dog_bite", "awd_cholera", "avh", "cut_leishmaniasis",
    "vh_bcd", "chickenpox", "measles", "tb", "dengue"
}
VALID_GENDERS = {"male", "female", "transgender", "other", "unknown"}

REQUIRED_FIELDS = [
    "external_record_id",
    "test_date",
    "district",
    "disease",
    "test_result"
]


def convert_age_to_band(age_val: Any) -> Optional[str]:
    """Converts a numeric age into a privacy-safe categorical age band."""
    if pd.isna(age_val) or age_val is None:
        return None
    
    # If already a valid band string
    s = str(age_val).strip()
    if s in VALID_AGE_BANDS:
        return s
        
    # Attempt numeric extraction
    m = re.search(r"\d+", s)
    if m:
        n = int(m.group(0))
        if n < 5:
            return "0-4"
        elif n < 15:
            return "5-14"
        elif n < 25:
            return "15-24"
        elif n < 45:
            return "25-44"
        elif n < 65:
            return "45-64"
        else:
            return "65+"
    return None


class IngestionValidator:
    """
    Validates uploaded hospital CSVs or API payloads against strict public health schemas.
    """

    def __init__(self, max_allowed_date: Optional[date] = None, reject_on_raw_pii: bool = False):
        # Allow dates up to end of 2026 (matching study horizon) or supplied date
        self.max_allowed_date = max_allowed_date or date(2026, 12, 31)
        self.reject_on_raw_pii = reject_on_raw_pii

    def validate_file(self, file_path_or_df: Any) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Validates a file path or DataFrame.
        Returns: (clean_valid_dataframe, validation_report_dict)
        """
        if isinstance(file_path_or_df, (str, Path)):
            df = pd.read_csv(file_path_or_df)
        elif isinstance(file_path_or_df, pd.DataFrame):
            df = file_path_or_df.copy()
        else:
            raise TypeError("Expected file path or pandas DataFrame")

        total_rows = len(df)
        errors: List[Dict[str, Any]] = []
        valid_indices: List[int] = []

        # 1. Direct PII Check
        has_pii, pii_issues = scan_for_pii(df)
        if has_pii:
            if self.reject_on_raw_pii:
                return pd.DataFrame(), {
                    "status": "REJECTED",
                    "reason": "Direct PII detected in payload",
                    "issues": pii_issues,
                    "total_rows": total_rows,
                    "valid_rows": 0,
                    "rejected_rows": total_rows
                }
            else:
                # Sanitize in-place
                df = sanitize_dataframe(df)

        # 2. Check Required Columns
        missing_cols = [c for c in REQUIRED_FIELDS if c not in df.columns]
        if missing_cols:
            return pd.DataFrame(), {
                "status": "FAILED",
                "reason": f"Missing required column(s): {missing_cols}",
                "total_rows": total_rows,
                "valid_rows": 0,
                "rejected_rows": total_rows,
                "errors": [{"row": 0, "error": f"Missing column: {c}"} for c in missing_cols]
            }

        # 3. Row-by-Row Deep Validation
        cleaned_rows = []

        for idx, row in df.iterrows():
            row_num = int(idx) + 1
            row_errors = []

            # A. Check empty required values
            ext_id = str(row.get("external_record_id", "")).strip()
            if not ext_id or ext_id.lower() == "nan":
                row_errors.append("MISSING_EXTERNAL_RECORD_ID")

            # B. Test Date Validation
            raw_date = row.get("test_date")
            parsed_date = None
            try:
                dt = pd.to_datetime(raw_date, errors="raise")
                parsed_date = dt.date()
                if parsed_date > self.max_allowed_date:
                    row_errors.append(f"FUTURE_DATE: {parsed_date} exceeds {self.max_allowed_date}")
                if parsed_date < date(2020, 1, 1):
                    row_errors.append(f"INVALID_HISTORICAL_DATE: {parsed_date} before 2020")
            except Exception:
                row_errors.append(f"INVALID_DATE_FORMAT: '{raw_date}'")

            # C. District P-Code Resolution
            raw_district = row.get("district") or row.get("district_pcode")
            pcode = resolve_district_pcode(raw_district)
            if not pcode:
                row_errors.append(f"UNRESOLVABLE_DISTRICT: '{raw_district}'")

            # D. Disease Validation
            raw_disease = str(row.get("disease", "")).strip()
            if raw_disease.lower() not in VALID_DISEASES:
                row_errors.append(f"UNSUPPORTED_DISEASE: '{raw_disease}'")

            # E. Test Result Validation
            raw_res = str(row.get("test_result", "")).strip().lower()
            if raw_res not in VALID_TEST_RESULTS:
                row_errors.append(f"INVALID_TEST_RESULT: '{raw_res}'")

            # F. Age Band Sanitization
            raw_age = row.get("age_band") or row.get("age")
            age_band = convert_age_to_band(raw_age)
            if not age_band:
                row_errors.append(f"INVALID_AGE_BAND: '{raw_age}'")

            # G. Patient Hash Check
            p_hash = str(row.get("patient_hash", "")).strip()
            if not p_hash or len(p_hash) != 64:
                # If raw ID exists, generate hash
                raw_pat_id = row.get("mrno") or row.get("cnic") or ext_id
                if raw_pat_id:
                    p_hash = hash_patient_id(str(raw_pat_id), district_salt=pcode or "")
                else:
                    row_errors.append("MISSING_PATIENT_HASH")

            if row_errors:
                for err in row_errors:
                    errors.append({"row": row_num, "error": err, "external_record_id": ext_id})
            else:
                # Valid Row: assemble clean record
                district_meta = CANONICAL_KP_DISTRICTS[pcode]
                cleaned_rows.append({
                    "external_record_id": ext_id,
                    "test_date": parsed_date.isoformat(),
                    "epi_week": int(parsed_date.isocalendar()[1]),
                    "epi_year": int(parsed_date.isocalendar()[0]),
                    "facility_name": str(row.get("facility_name", row.get("facility_id", "General Hospital"))).strip(),
                    "facility_id": row.get("facility_id", 1),
                    "district_pcode": pcode,
                    "district_name": district_meta["name"],
                    "division": district_meta["division"],
                    "disease": raw_disease.title(),
                    "test_type": str(row.get("test_type", "Standard Diagnostic")).strip(),
                    "test_result": raw_res.capitalize(),
                    "case_status": "confirmed" if raw_res == "positive" else "suspected",
                    "age_band": age_band,
                    "gender": str(row.get("gender", "Unknown")).strip().capitalize(),
                    "patient_hash": p_hash,
                    "is_corrected": bool(row.get("is_corrected", False)),
                    "corrected_at": row.get("corrected_at", None),
                    "source_type": str(row.get("source_type", "hospital_upload")).strip()
                })

        valid_df = pd.DataFrame(cleaned_rows)
        rejected_count = len(errors)

        # 4. Generate Privacy-Safe Data Quality Summary
        summary: Dict[str, Any] = {
            "status": "PASSED" if rejected_count == 0 else "PARTIAL" if len(valid_df) > 0 else "FAILED",
            "total_rows_evaluated": total_rows,
            "valid_rows_accepted": len(valid_df),
            "rejected_rows_count": rejected_count,
            "errors": errors[:50], # Sample first 50 errors
            "pii_scanned": True,
            "direct_pii_detected": has_pii,
            "data_quality_metrics": {}
        }

        if not valid_df.empty:
            total_tests = len(valid_df)
            positives = (valid_df["test_result"] == "Positive").sum()
            negatives = (valid_df["test_result"] == "Negative").sum()
            indeterminates = (valid_df["test_result"] == "Indeterminate").sum()
            
            summary["data_quality_metrics"] = {
                "total_laboratory_tests": total_tests,
                "confirmed_positive_tests": int(positives),
                "negative_tests": int(negatives),
                "indeterminate_tests": int(indeterminates),
                "positivity_rate_percent": round((positives / total_tests) * 100.0, 2) if total_tests > 0 else 0.0,
                "suspected_cases_count": int(total_tests - positives),
                "unique_districts_covered": int(valid_df["district_pcode"].nunique()),
                "unique_facilities_reporting": int(valid_df["facility_name"].nunique()),
                "diseases_reported": valid_df["disease"].value_counts().to_dict(),
                "age_band_distribution": valid_df["age_band"].value_counts().to_dict()
            }

        return valid_df, summary
