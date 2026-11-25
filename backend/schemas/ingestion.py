"""
Pydantic Schemas for CSV Ingestion, Upload Feedback, and Mock API Sync.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class ValidationSummaryResponse(BaseModel):
    batch_uuid: str
    status: str # 'PASSED', 'PARTIAL', 'FAILED'
    filename: Optional[str] = None
    total_rows_evaluated: int
    valid_rows_accepted: int
    rejected_rows_count: int
    direct_pii_detected: bool
    data_quality_metrics: Dict[str, Any]
    errors_sample: List[Dict[str, Any]]
    message: str


class BatchItemResponse(BaseModel):
    id: int
    batch_uuid: str
    source_type: str
    filename: Optional[str]
    record_count: int
    valid_count: int
    error_count: int
    status: str
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class SyncMockRequest(BaseModel):
    facility_id: Optional[int] = 1
    district_pcode: Optional[str] = "PK501"
    simulate_delay: bool = False


class SyncMockResponse(BaseModel):
    batch_uuid: str
    status: str
    source_type: str = "mock_api_sync"
    records_received: int
    new_records_ingested: int
    duplicates_skipped: int
    corrected_records_updated: int
    timestamp: str
