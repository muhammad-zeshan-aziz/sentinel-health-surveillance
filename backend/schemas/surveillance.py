"""
Pydantic Schemas for Overview Screen, KPIs, Trends, and Drilldowns.
Strictly distinguishes True Zero cases from Unavailable / Missing data.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class KPISummary(BaseModel):
    confirmed_cases: int
    suspected_cases: int
    total_cases: int
    total_tests: int
    positivity_rate: float
    active_warnings: int
    reporting_coverage_pct: float
    outdated_districts_count: int
    confirmed_delta_pct: Optional[float] = None
    suspected_delta_pct: Optional[float] = None
    total_delta_pct: Optional[float] = None
    coverage_delta_pct: Optional[float] = None


class TrendPoint(BaseModel):
    year: int
    epi_week: int
    label: str # e.g. "2025-W24"
    reported_cases: Optional[float] = None # None represents Unavailable / Missing data; 0.0 is True Zero
    suspected_cases: Optional[float] = None
    confirmed_cases: Optional[float] = None
    predicted_mean: Optional[float] = None
    ci_lower_95: Optional[float] = None
    ci_upper_95: Optional[float] = None
    is_forecast_withheld: bool = False
    is_missing: bool = False
    is_zero: bool = False


class DistrictWatchItem(BaseModel):
    district_pcode: str
    district_name: str
    division: str
    cases_latest: Optional[int] = None
    cases_previous: Optional[int] = None
    percent_change: Optional[float] = None
    incidence_per_100k: Optional[float] = None
    alert_tier: str # 'priority_review', 'watch', 'routine', 'data_incomplete'
    reporting_status: str # 'Active', 'Missing Report'


class FacilityReportingItem(BaseModel):
    facility_id: int
    facility_name: str
    district_name: str
    district_pcode: str
    reports_submitted: int
    reports_expected: int
    completeness_pct: float
    last_report_date: Optional[str] = None
    has_missing_report: bool = False


class OverviewResponse(BaseModel):
    kpis: KPISummary
    trends: List[TrendPoint]
    district_watch: List[DistrictWatchItem]
    hospital_reporting: List[FacilityReportingItem]
    filters_applied: Dict[str, Any]
    demo_data_present: bool = True
    last_refreshed_at: str


class DrilldownRecordSummary(BaseModel):
    category: str
    count: int
    percentage: float
    details: Optional[str] = None


class DrilldownResponse(BaseModel):
    indicator: str
    total_records: int
    privacy_notice: str = "PII Redacted: Zero patient names or national identity numbers stored."
    breakdowns: Dict[str, List[DrilldownRecordSummary]]
