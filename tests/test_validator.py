"""
Module 4: Ingestion Validation & Processing Error Recovery Tests.
Verifies strict CSV schema validation, rejection of invalid/corrupt dates,
unknown districts/diseases, and graceful error handling on corrupt input.
"""

import io
import pytest
import pandas as pd
from src.ingestion.validator import IngestionValidator

def test_validator_valid_dataframe():
    validator = IngestionValidator()
    df = pd.DataFrame([
        {
            "external_record_id": "EXT-001",
            "test_date": "2026-05-10",
            "facility_id": 1,
            "facility_name": "Ayub Teaching Hospital",
            "district": "Abbottabad",
            "disease": "Malaria",
            "test_type": "Microscopy",
            "test_result": "Positive",
            "age_band": "25-44",
            "gender": "Male"
        },
        {
            "external_record_id": "EXT-002",
            "test_date": "2026-05-10",
            "facility_id": 1,
            "facility_name": "Ayub Teaching Hospital",
            "district": "Abbottabad",
            "disease": "Typhoid",
            "test_type": "Blood Culture",
            "test_result": "Negative",
            "age_band": "15-24",
            "gender": "Female"
        }
    ])
    valid_df, report = validator.validate_file(df)
    assert report["status"] == "PASSED"
    assert report["valid_rows_accepted"] == 2
    assert report["rejected_rows_count"] == 0

def test_validator_missing_required_columns():
    validator = IngestionValidator()
    df_missing = pd.DataFrame([{"test_date": "2026-05-10", "district": "Abbottabad"}])
    valid_df, report = validator.validate_file(df_missing)
    assert report["status"] == "FAILED"
    rejected = report.get("rejected_rows", report.get("rejected_rows_count", 0))
    assert rejected >= 1
    assert any("Missing column" in str(e) or "Missing" in report.get("reason", "") for e in report.get("errors", []))

def test_validator_future_dates_rejected():
    validator = IngestionValidator()
    df_future = pd.DataFrame([{
        "external_record_id": "EXT-099",
        "test_date": "2035-01-01",
        "facility_id": 1,
        "facility_name": "Ayub Teaching Hospital",
        "district": "Abbottabad",
        "disease": "Malaria",
        "test_type": "Microscopy",
        "test_result": "Positive",
        "age_band": "25-44",
        "gender": "Male"
    }])
    valid_df, report = validator.validate_file(df_future)
    assert report["rejected_rows_count"] >= 1
    assert any("FUTURE_DATE" in str(e) for e in report["errors"])

def test_validator_unknown_district_pcode():
    validator = IngestionValidator()
    df_bad_dist = pd.DataFrame([{
        "external_record_id": "EXT-100",
        "test_date": "2026-05-10",
        "facility_id": 1,
        "facility_name": "Ayub Teaching Hospital",
        "district": "BadDistrict",
        "disease": "Malaria",
        "test_type": "Microscopy",
        "test_result": "Positive",
        "age_band": "25-44",
        "gender": "Male"
    }])
    valid_df, report = validator.validate_file(df_bad_dist)
    assert report["rejected_rows_count"] >= 1
    assert any("UNRESOLVABLE_DISTRICT" in str(e) for e in report["errors"])

def test_processing_error_recovery_endpoint(client, dho_headers):
    # Corrupt/Binary upload must return clean 400/422 without crashing server
    corrupt_data = b"\x00\xff\xfe\x00\x12\x34\x56GARBAGE_BINARY_STREAM"
    response = client.post(
        "/api/ingestion/upload-csv",
        files={"file": ("corrupt.csv", io.BytesIO(corrupt_data), "text/csv")},
        headers=dho_headers
    )
    assert response.status_code in [400, 422], f"Expected 400 or 422, got {response.status_code}"
    err_json = response.json()
    assert "detail" in err_json or "error" in err_json

def test_empty_csv_upload_recovery(client, dho_headers):
    empty_data = b""
    response = client.post(
        "/api/ingestion/upload-csv",
        files={"file": ("empty.csv", io.BytesIO(empty_data), "text/csv")},
        headers=dho_headers
    )
    assert response.status_code in [400, 422]
