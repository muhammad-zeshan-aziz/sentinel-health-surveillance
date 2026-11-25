"""
Cryptographic Salted HMAC-SHA256 Patient Pseudonymization Module.
Enforces Zero-PII Policy by converting direct identifiers (CNIC, MRNO, Name)
into irreversible, salted patient hashes, and stripping all raw PII before storage.
"""

import hmac
import hashlib
import re
from typing import Dict, Any, List, Tuple, Union
import pandas as pd

# Default Server Pepper (can be overridden via environment in production)
DEFAULT_SERVER_PEPPER = "SentinelSurveillance-KP-PublicHealth-Pepper-2026-Secret"

# Known direct PII column names (case-insensitive)
DIRECT_PII_FIELDS = {
    "patient_name", "father_name", "husband_name", "nic_new", "cnic",
    "mrno", "patient_id_raw", "phone", "contact", "address", "cell_no",
    "guardian_name", "first_name", "last_name", "full_name"
}

# Regex for Pakistani CNIC: 13 digits (with or without hyphens: 12345-1234567-1 or 1234512345671)
CNIC_PATTERN = re.compile(r"\b\d{5}-?\d{7}-?\d\b")


def hash_patient_id(raw_identifier: str, district_salt: str = "", pepper: str = DEFAULT_SERVER_PEPPER) -> str:
    """
    Computes an HMAC-SHA256 hash of the patient identifier, salted with district
    information and keyed with the server pepper.
    Returns 64-character hex digest.
    """
    if not raw_identifier:
        raise ValueError("Cannot hash empty patient identifier")
    
    clean_id = str(raw_identifier).strip().replace("-", "")
    salt = str(district_salt).strip().lower()
    message = f"{clean_id}|{salt}".encode("utf-8")
    key = pepper.encode("utf-8")
    
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def scan_for_pii(data: Union[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]) -> Tuple[bool, List[str]]:
    """
    Scans a DataFrame, dictionary, or list of dicts for direct PII column headers
    or cell values matching CNIC patterns.
    Returns (has_pii, list_of_detected_issues).
    """
    issues = []
    
    if isinstance(data, pd.DataFrame):
        # 1. Check column names
        for col in data.columns:
            if col.strip().lower() in DIRECT_PII_FIELDS:
                issues.append(f"Direct PII column detected: '{col}'")
        
        # 2. Check sample string values for CNIC pattern
        for col in data.select_dtypes(include=["object"]).columns:
            sample_str = data[col].dropna().astype(str).head(100).str.cat(sep=" ")
            if CNIC_PATTERN.search(sample_str):
                issues.append(f"CNIC pattern detected in column: '{col}'")
                
    elif isinstance(data, dict):
        for k, v in data.items():
            if k.strip().lower() in DIRECT_PII_FIELDS:
                issues.append(f"Direct PII key detected: '{k}'")
            if isinstance(v, str) and CNIC_PATTERN.search(v):
                issues.append(f"CNIC pattern detected in key: '{k}'")
                
    elif isinstance(data, list):
        for idx, item in enumerate(data[:100]):
            if isinstance(item, dict):
                for k, v in item.items():
                    if k.strip().lower() in DIRECT_PII_FIELDS:
                        issues.append(f"Direct PII key in record {idx}: '{k}'")
                    if isinstance(v, str) and CNIC_PATTERN.search(v):
                        issues.append(f"CNIC pattern in record {idx}, key '{k}'")
                        
    return (len(issues) > 0, list(set(issues)))


def sanitize_record(record: Dict[str, Any], district_salt: str = "") -> Dict[str, Any]:
    """
    Strips all direct PII fields from a record and ensures a pseudonymous
    'patient_hash' exists. If raw ID is provided, it is hashed and removed.
    """
    clean = dict(record)
    
    # Extract raw ID if present to compute hash
    raw_id = None
    for field in ["nic_new", "cnic", "mrno", "patient_id_raw", "NIC_NEW", "CNIC", "MRNO"]:
        if field in clean and clean[field]:
            raw_id = str(clean[field])
            break
            
    if raw_id and "patient_hash" not in clean:
        clean["patient_hash"] = hash_patient_id(raw_id, district_salt=district_salt)
        
    # Strip all known direct PII keys
    keys_to_remove = [k for k in clean.keys() if k.strip().lower() in DIRECT_PII_FIELDS]
    for k in keys_to_remove:
        del clean[k]
        
    return clean


def sanitize_dataframe(df: pd.DataFrame, district_col: str = "district_pcode") -> pd.DataFrame:
    """
    Sanitizes an entire DataFrame by hashing raw identifiers and dropping PII columns.
    """
    out_df = df.copy()
    
    # 1. Compute hash if raw identifier column exists
    for id_col in ["nic_new", "cnic", "mrno", "NIC_NEW", "CNIC", "MRNO"]:
        if id_col in out_df.columns and "patient_hash" not in out_df.columns:
            salt_series = out_df[district_col] if district_col in out_df.columns else ""
            out_df["patient_hash"] = [
                hash_patient_id(str(val), str(salt)) if pd.notna(val) else None
                for val, salt in zip(out_df[id_col], salt_series)
            ]
            break
            
    # 2. Drop direct PII columns
    cols_to_drop = [c for c in out_df.columns if c.strip().lower() in DIRECT_PII_FIELDS]
    if cols_to_drop:
        out_df.drop(columns=cols_to_drop, inplace=True)
        
    return out_df
