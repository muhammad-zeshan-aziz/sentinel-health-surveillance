"""
Mock Hospital/Laboratory API Synchronization Module.
Simulates automated scheduled API synchronization, delayed batch ingestion,
and idempotent re-polling with provenance tracking (source_type='mock_api_sync').
"""

from typing import Dict, Any, List, Optional, Tuple, Set
import uuid
from datetime import datetime, date, timedelta
import pandas as pd

from src.ingestion.crosswalk import CANONICAL_KP_DISTRICTS
from src.ingestion.pseudonymizer import hash_patient_id
from src.ingestion.validator import IngestionValidator
from src.ingestion.episode_engine import EpisodeEngine


class MockHospitalAPIService:
    """
    Mock external hospital/laboratory server endpoint.
    Serves batches of laboratory test results on demand.
    """

    def __init__(self, facility_name: str, district_pcode: str):
        self.facility_name = facility_name
        self.district_pcode = district_pcode
        self.records_store: List[Dict[str, Any]] = []
        self._populate_mock_records()

    def _populate_mock_records(self):
        """Pre-populates sample diagnostic laboratory submissions."""
        base_date = date(2025, 5, 10)
        # 1. Standard batch of tests
        for i in range(1, 11):
            disease = "Malaria" if i % 2 == 0 else "Typhoid"
            res = "Positive" if i in [2, 5, 8] else "Negative"
            pat_hash = hash_patient_id(f"API-PAT-{i:04d}", district_salt=self.district_pcode)
            self.records_store.append({
                "external_record_id": f"API-SYNC-{self.district_pcode}-{i:04d}",
                "test_date": (base_date + timedelta(days=i % 5)).isoformat(),
                "facility_name": self.facility_name,
                "district": self.district_pcode,
                "disease": disease,
                "test_type": "Automated Immunoassay" if disease == "Typhoid" else "Rapid Diagnostic Test",
                "test_result": res,
                "age_band": "25-44",
                "gender": "Female" if i % 2 == 0 else "Male",
                "patient_hash": pat_hash,
                "is_corrected": False,
                "corrected_at": None,
                "source_type": "mock_api_sync"
            })

    def fetch_records(self, since_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns records from the mock hospital endpoint."""
        return list(self.records_store)


class MockHospitalSyncPoller:
    """
    Scheduled poller client that connects to hospital API sources,
    validates payloads, prevents duplicate re-ingestion, and logs batches.
    """

    def __init__(self):
        self.synced_external_ids: Set[str] = set()
        self.sync_batch_history: List[Dict[str, Any]] = []
        self.validator = IngestionValidator()
        self.episode_engine = EpisodeEngine()

    def sync_from_source(self, api_records: List[Dict[str, Any]], batch_label: str = "scheduled_sync") -> Dict[str, Any]:
        """
        Ingests a batch of records from a mock hospital API source.
        Enforces idempotency: skips already ingested external_record_ids unless is_corrected=True.
        """
        batch_uuid = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        if not api_records:
            result = {
                "batch_uuid": batch_uuid,
                "batch_label": batch_label,
                "timestamp": timestamp,
                "source_type": "mock_api_sync",
                "status": "COMPLETED",
                "records_received": 0,
                "new_records_ingested": 0,
                "duplicates_skipped": 0,
                "corrected_records_updated": 0,
                "validation_status": "PASSED"
            }
            self.sync_batch_history.append(result)
            return result

        raw_df = pd.DataFrame(api_records)
        raw_df["source_type"] = "mock_api_sync"

        # 1. Validate payload
        valid_df, val_summary = self.validator.validate_file(raw_df)
        if valid_df.empty:
            result = {
                "batch_uuid": batch_uuid,
                "batch_label": batch_label,
                "timestamp": timestamp,
                "source_type": "mock_api_sync",
                "status": "FAILED",
                "validation_summary": val_summary,
                "records_received": len(api_records),
                "new_records_ingested": 0,
                "duplicates_skipped": 0
            }
            self.sync_batch_history.append(result)
            return result

        # 2. Check Idempotency against synced_external_ids
        new_records = []
        duplicates_skipped = 0
        corrected_count = 0

        for _, row in valid_df.iterrows():
            ext_id = str(row["external_record_id"])
            is_corr = bool(row.get("is_corrected", False))

            if ext_id in self.synced_external_ids:
                if is_corr:
                    # Allow corrected record through to supersede
                    new_records.append(row.to_dict())
                    corrected_count += 1
                else:
                    # Idempotent skip: already ingested
                    duplicates_skipped += 1
            else:
                new_records.append(row.to_dict())
                self.synced_external_ids.add(ext_id)

        # 3. Deduplicate episodes and tag repeat tests
        if new_records:
            ingested_df = self.episode_engine.process_records(new_records)
            new_ingested_count = len(ingested_df)
        else:
            new_ingested_count = 0

        result = {
            "batch_uuid": batch_uuid,
            "batch_label": batch_label,
            "timestamp": timestamp,
            "source_type": "mock_api_sync",
            "status": "COMPLETED",
            "records_received": len(api_records),
            "new_records_ingested": new_ingested_count,
            "duplicates_skipped": duplicates_skipped,
            "corrected_records_updated": corrected_count,
            "validation_summary": val_summary
        }

        self.sync_batch_history.append(result)
        return result
