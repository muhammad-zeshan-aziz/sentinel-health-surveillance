"""
Module 11: Export Engine & Zero-PII Aggregates Tests.
Verifies synchronized CSV & JSON export generation adhering to active filters,
total absence of direct identifiers, and graceful handling of empty filter states.
"""

import io
import csv
import json
import pytest

def test_authenticated_csv_export(client, dho_headers):
    resp = client.get(
        "/api/reports/export?format=csv&disease=Malaria&district_pcode=PK501",
        headers=dho_headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    
    # Parse CSV content
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) > 0

    first_row = rows[0]
    assert "district_pcode" in first_row
    assert first_row["district_pcode"] == "PK501"
    assert "disease" in first_row
    assert first_row["disease"] == "Malaria"

    # Verify zero PII in export
    disallowed = ["PATIENT_NAME", "FATHER_NAME", "NIC_NEW", "MRNO", "cnic", "patient_name", "mrno"]
    for bad in disallowed:
        assert bad not in first_row, f"PII column '{bad}' found in CSV export!"

def test_authenticated_json_export(client, analyst_headers):
    resp = client.get(
        "/api/reports/export?format=json&disease=Typhoid",
        headers=analyst_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "metadata" in data
    assert "records" in data
    assert data["metadata"]["disease"] == "Typhoid"
    assert len(data["records"]) > 0

def test_empty_state_filter_handling(client, dho_headers):
    # Query with non-existent district P-code
    resp = client.get(
        "/api/reports/export?format=csv&disease=Malaria&district_pcode=PK999",
        headers=dho_headers
    )
    assert resp.status_code == 404, "Empty filter selection must return clean 404 JSON response"
    assert "detail" in resp.json()
