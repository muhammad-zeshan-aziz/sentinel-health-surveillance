"""
Ingestion & Synchronization Router.
Handles CSV uploads, strict schema validation, cryptographic pseudonymization,
episode deduplication, late corrected results, and mock hospital API sync.
"""

from typing import List, Optional, Dict, Any
import io
import json
import uuid
from datetime import datetime, date
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from sqlalchemy.orm import Session
import pandas as pd

from backend.database import get_db
from backend.models.surveillance import IngestionBatch, LabRecord
from backend.models.user import User
from backend.models.district import Facility
from backend.schemas.ingestion import ValidationSummaryResponse, BatchItemResponse, SyncMockResponse
from backend.security import get_current_user, require_role
from backend.config import PROCESSED_DIR

from src.ingestion.validator import IngestionValidator
from src.ingestion.episode_engine import EpisodeEngine
from src.ingestion.mock_lab_sync import MockHospitalAPIService, MockHospitalSyncPoller

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion & Sync"])

validator = IngestionValidator()
episode_engine = EpisodeEngine()
mock_poller = MockHospitalSyncPoller()


@router.post("/upload-csv", response_model=ValidationSummaryResponse)
async def upload_laboratory_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["hospital_staff", "data_analyst", "district_health_officer"]))
):
    """
    Hospital Lab CSV Upload endpoint.
    Performs schema validation, pseudonymization, episode deduplication,
    reconciles corrections, and commits to lab_records with provenance.
    """
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a standard CSV file."
        )

    content = await file.read()
    try:
        df_raw = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to parse CSV file: {str(e)}"
        )

    # 1. Validate Schema & PII
    valid_df, val_summary = validator.validate_file(df_raw)
    batch_uuid = str(uuid.uuid4())
    total_evaluated = val_summary.get("total_rows_evaluated", len(df_raw))
    rejected_count = val_summary.get("rejected_rows_count", 0)

    if valid_df.empty:
        # Commit failed batch record
        batch_log = IngestionBatch(
            batch_uuid=batch_uuid,
            source_type="hospital_upload",
            uploaded_by_user_id=current_user.id,
            filename=file.filename,
            record_count=total_evaluated,
            valid_count=0,
            error_count=rejected_count,
            status="failed",
            error_log=json.dumps(val_summary.get("errors", [])[:50])
        )
        db.add(batch_log)
        db.commit()

        return ValidationSummaryResponse(
            batch_uuid=batch_uuid,
            status="FAILED",
            filename=file.filename,
            total_rows_evaluated=total_evaluated,
            valid_rows_accepted=0,
            rejected_rows_count=rejected_count,
            direct_pii_detected=val_summary.get("direct_pii_detected", False),
            data_quality_metrics={},
            errors_sample=val_summary.get("errors", [])[:20],
            message="Upload rejected: all rows failed schema validation."
        )

    # 2. Episode Deduplication & Late Corrections
    processed_df = episode_engine.process_records(valid_df)

    # 3. Create Ingestion Batch
    batch_status = "completed" if rejected_count == 0 else "partial"
    batch_log = IngestionBatch(
        batch_uuid=batch_uuid,
        source_type="hospital_upload",
        uploaded_by_user_id=current_user.id,
        filename=file.filename,
        record_count=total_evaluated,
        valid_count=len(processed_df),
        error_count=rejected_count,
        status=batch_status,
        error_log=json.dumps(val_summary.get("errors", [])[:50])
    )
    db.add(batch_log)
    db.flush()

    # 4. Insert Lab Records
    lab_records_to_insert = []
    for _, r in processed_df.iterrows():
        # Handle late-arriving corrections by updating previous record if present
        ext_id = r.get("external_record_id")
        is_corr = bool(r.get("is_corrected", False))

        if is_corr and ext_id:
            prior = db.query(LabRecord).filter(LabRecord.external_record_id == ext_id).first()
            if prior:
                prior.test_result = r["test_result"]
                prior.case_status = r["case_status"]
                prior.is_corrected = True
                prior.corrected_at = datetime.utcnow()
                continue

        lab_records_to_insert.append(LabRecord(
            batch_id=batch_log.id,
            facility_id=int(r.get("facility_id", 1)) if r.get("facility_id") else None,
            district_pcode=r["district_pcode"],
            patient_hash=r["patient_hash"],
            external_record_id=r.get("external_record_id"),
            test_date=date.fromisoformat(str(r["test_date"])),
            epi_week=int(r["epi_week"]),
            epi_year=int(r["epi_year"]),
            disease=r["disease"],
            test_type=r.get("test_type"),
            test_result=r["test_result"],
            case_status=r["case_status"],
            age_band=r.get("age_band"),
            gender=r.get("gender"),
            is_suspected=True,
            is_confirmed=(r["test_result"] == "Positive" and not r.get("is_duplicate_test", False)),
            is_corrected=is_corr,
            corrected_at=datetime.utcnow() if is_corr else None,
            episode_id=r.get("episode_id"),
            is_duplicate_test=bool(r.get("is_duplicate_test", False)),
            source_type="hospital_upload"
        ))

    if lab_records_to_insert:
        db.bulk_save_objects(lab_records_to_insert)

    db.commit()

    return ValidationSummaryResponse(
        batch_uuid=batch_uuid,
        status=batch_status.upper(),
        filename=file.filename,
        total_rows_evaluated=total_evaluated,
        valid_rows_accepted=len(processed_df),
        rejected_rows_count=rejected_count,
        direct_pii_detected=val_summary.get("direct_pii_detected", False),
        data_quality_metrics=val_summary.get("data_quality_metrics", {}),
        errors_sample=val_summary.get("errors", [])[:20],
        message=f"Successfully ingested {len(processed_df)} validated records ({rejected_count} rejected)."
    )


@router.post("/sync-mock", response_model=SyncMockResponse)
def trigger_mock_api_sync(
    facility_name: str = Query("Ayub Teaching Hospital (ATH)"),
    district_pcode: str = Query("PK501"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["hospital_staff", "data_analyst", "district_health_officer"]))
):
    """
    Triggers automated hospital laboratory API synchronization.
    Fetches diagnostic records, verifies idempotency (zero duplicate inserts),
    and logs provenance as 'mock_api_sync'.
    """
    mock_service = MockHospitalAPIService(facility_name=facility_name, district_pcode=district_pcode.upper())
    records = mock_service.fetch_records()

    sync_res = mock_poller.sync_from_source(records, batch_label="manual_trigger")

    # Commit batch record to DB
    batch_uuid = sync_res["batch_uuid"]
    batch_entry = IngestionBatch(
        batch_uuid=batch_uuid,
        source_type="mock_api_sync",
        uploaded_by_user_id=current_user.id,
        filename=f"API_SYNC_{district_pcode.upper()}",
        record_count=sync_res["records_received"],
        valid_count=sync_res["new_records_ingested"],
        error_count=0,
        status="completed"
    )
    db.add(batch_entry)
    db.commit()

    return SyncMockResponse(
        batch_uuid=batch_uuid,
        status=sync_res["status"],
        source_type="mock_api_sync",
        records_received=sync_res["records_received"],
        new_records_ingested=sync_res["new_records_ingested"],
        duplicates_skipped=sync_res["duplicates_skipped"],
        corrected_records_updated=sync_res.get("corrected_records_updated", 0),
        timestamp=sync_res["timestamp"]
    )


@router.get("/batches", response_model=List[BatchItemResponse])
def get_ingestion_batches(limit: int = 20, db: Session = Depends(get_db)):
    """Returns recent file uploads and API synchronization history."""
    batches = db.query(IngestionBatch).order_by(IngestionBatch.created_at.desc()).limit(limit).all()
    return batches


@router.get("/quality-summary")
def get_quality_summary():
    """Returns official NIH IDSR data quality flags and known source anomalies."""
    dq_file = PROCESSED_DIR / "data_quality_summary.json"
    if dq_file.exists():
        with open(dq_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"total_anomalies_flagged": 0, "flags": []}
