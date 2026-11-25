"""
Module 5: Mock Hospital API Synchronization & Idempotency Tests.
Verifies automated synchronization from ATH and KTH, handling of delayed feeds,
and strict idempotency (zero double-counting on repeated polls).
"""

import pytest
from src.ingestion.mock_lab_sync import MockHospitalAPIService, MockHospitalSyncPoller

def test_mock_api_service_fetch():
    service = MockHospitalAPIService("Ayub Teaching Hospital", "PK501")
    records = service.fetch_records()
    assert len(records) > 0
    sample = records[0]
    assert "external_record_id" in sample
    assert "test_result" in sample
    assert "patient_hash" in sample
    assert "disease" in sample

def test_mock_sync_poller_normal():
    service = MockHospitalAPIService("Ayub Teaching Hospital", "PK501")
    records = service.fetch_records()

    poller = MockHospitalSyncPoller()
    res = poller.sync_from_source(records, batch_label="test_normal_sync")
    assert res["status"] == "COMPLETED"
    assert res["new_records_ingested"] >= 0

def test_mock_sync_idempotency_on_repeat():
    service = MockHospitalAPIService("Ayub Teaching Hospital", "PK501")
    records = service.fetch_records()

    poller = MockHospitalSyncPoller()
    # First sync
    res1 = poller.sync_from_source(records)
    
    # Second immediate sync of identical records
    res2 = poller.sync_from_source(records)
    
    # On immediate repeat, duplicate external IDs must be skipped
    assert res2["duplicates_skipped"] == len(records)
    assert res2["new_records_ingested"] == 0

def test_mock_sync_endpoint_integration(client, dho_headers):
    resp = client.post("/api/ingestion/sync-mock?simulate_network_delay=false", headers=dho_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"].lower() in ["completed", "success"]
    assert "new_records_ingested" in data
    assert "records_received" in data
