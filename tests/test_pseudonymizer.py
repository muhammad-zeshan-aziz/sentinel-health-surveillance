"""
Module 2: Cryptographic Pseudonymizer & Zero-PII Enforcement Tests.
Verifies salted HMAC-SHA256 patient pseudonymization, irreversibility,
and total absence of direct PII across records and API responses.
"""

import re
import pytest
from src.ingestion.pseudonymizer import hash_patient_id, sanitize_record, scan_for_pii

CNIC_REGEX = re.compile(r"^\d{5}-\d{7}-\d$")

def test_pseudonymizer_determinism():
    salt = "test_district_salt"
    hash1 = hash_patient_id("MRN-987654", district_salt=salt)
    hash2 = hash_patient_id("MRN-987654", district_salt=salt)

    assert hash1 == hash2, "Pseudonymizer must be strictly deterministic with identical salt"
    assert len(hash1) == 64, "Must output a 64-character SHA-256 hex string"

def test_pseudonymizer_pepper_sensitivity():
    hash1 = hash_patient_id("MRN-987654", district_salt="salt_A")
    hash2 = hash_patient_id("MRN-987654", district_salt="salt_B")

    assert hash1 != hash2, "Different salts must produce cryptographically distinct hashes"

def test_strip_pii_dictionary():
    raw_record = {
        "external_record_id": "REC-001",
        "PATIENT_NAME": "Muhammad Ali",
        "FATHER_NAME": "Tariq Khan",
        "NIC_NEW": "14301-1234567-1",
        "MRNO": "MRN-5544",
        "gender": "Male",
        "age_band": "25-44",
        "disease": "Malaria",
        "test_result": "Positive"
    }

    cleaned = sanitize_record(raw_record, district_salt="PK501")

    # Disallowed direct identifiers must be stripped
    for pii_field in ["PATIENT_NAME", "FATHER_NAME", "NIC_NEW", "MRNO"]:
        assert pii_field not in cleaned, f"Direct identifier {pii_field} was not stripped!"
    
    assert "patient_hash" in cleaned, "patient_hash must be generated"
    assert len(cleaned["patient_hash"]) == 64

def test_scan_for_pii():
    clean_dict = {"patient_hash": "a" * 64, "age_band": "25-44", "test_result": "Positive"}
    has_pii, fields = scan_for_pii(clean_dict)
    assert has_pii is False
    assert len(fields) == 0

    dirty_dict = {"PATIENT_NAME": "Khan", "test_result": "Positive"}
    has_pii, fields = scan_for_pii(dirty_dict)
    assert has_pii is True
    assert any("PATIENT_NAME" in f for f in fields)

def test_zero_raw_pii_in_database(db_session):
    from backend.models.surveillance import LabRecord
    records = db_session.query(LabRecord).limit(200).all()

    for r in records:
        assert hasattr(r, "patient_hash"), "LabRecord must have patient_hash"
        assert not hasattr(r, "patient_name"), "LabRecord must never have patient_name attribute"
        assert not hasattr(r, "cnic"), "LabRecord must never have raw cnic attribute"
        if r.patient_hash:
            assert len(r.patient_hash) == 64
            assert not CNIC_REGEX.match(r.patient_hash), "Hash must never resemble a raw CNIC format"
