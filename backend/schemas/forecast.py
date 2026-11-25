"""
Pydantic Schemas for Model Registry, Evaluations, and Forecast Inquiries.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class ModelEvaluationSummary(BaseModel):
    id: int
    disease: str
    model_name: str
    model_type: str
    version: str
    is_active: bool
    metrics: Dict[str, Any]
    feature_names: List[str]
    created_at: datetime
    test_mae: Optional[float] = None
    test_rmse: Optional[float] = None
    test_picp: Optional[float] = None
    baseline_mae: Optional[float] = None


class ForecastItem(BaseModel):
    district_pcode: str
    target_year: int
    target_week: int
    disease: str
    predicted_mean: Optional[float]
    ci_lower_95: Optional[float]
    ci_upper_95: Optional[float]
    is_withheld: bool
    withholding_reason: Optional[str]
