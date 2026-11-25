"""
Pydantic Schemas for Early Warning Alerts and Acknowledgment Workflows.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class AlertItem(BaseModel):
    id: int
    district_pcode: str
    district_name: str
    division: str
    disease: str
    year: int
    epi_week: int
    alert_level: str # 'priority_review', 'watch', 'routine'
    composite_score: float
    ears_c1_score: float
    ears_c2_score: float
    ears_c3_score: float
    forecast_breach: bool
    incidence_per_100k: float
    headline: str
    details: Optional[str] = None
    acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    cases_observed: Optional[float] = None
    baseline_mean: Optional[float] = None

    class Config:
        orm_mode = True
        from_attributes = True


class AlertQueueResponse(BaseModel):
    total_active_warnings: int
    priority_review_count: int
    watch_count: int
    acknowledged_count: int
    alerts: List[AlertItem]


class AcknowledgeAlertRequest(BaseModel):
    review_notes: str


class AcknowledgeAlertResponse(BaseModel):
    status: str
    alert_id: int
    acknowledged_by: str
    acknowledged_at: datetime
    message: str
