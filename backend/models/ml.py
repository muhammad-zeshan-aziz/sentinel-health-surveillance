"""
Machine Learning Model Registry and Time-Series Forecasts Store.
Stores versioned model metadata, held-out evaluation metrics, and t+1 forecast intervals.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, BigInteger, UniqueConstraint
)
from sqlalchemy.orm import relationship

from backend.database import Base


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disease = Column(String(50), nullable=False, index=True) # 'Malaria', 'Typhoid'
    model_name = Column(String(100), nullable=False) # e.g. 'LightGBM_Lag4', 'SARIMAX_Seasonal'
    model_type = Column(String(50), nullable=False) # 'time_series', 'gradient_boosting', 'baseline'
    version = Column(String(20), nullable=False) # e.g. 'v1.0'
    feature_names = Column(Text, nullable=False) # JSON serialized list of feature names
    hyperparams = Column(Text, nullable=False) # JSON serialized dict of hyperparams
    metrics = Column(Text, nullable=False) # JSON serialized dict: {"mae": 12.4, "rmse": 18.2, "picp_95": 0.94}
    artifact_path = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    forecasts = relationship("Forecast", back_populates="model", cascade="all, delete-orphan")


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("model_registry.id"), nullable=True, index=True)
    district_pcode = Column(String(10), ForeignKey("districts.pcode"), nullable=False, index=True)
    target_year = Column(Integer, nullable=False)
    target_week = Column(Integer, nullable=False)
    disease = Column(String(50), nullable=False, index=True)
    predicted_mean = Column(Float, nullable=True)
    ci_lower_95 = Column(Float, nullable=True)
    ci_upper_95 = Column(Float, nullable=True)
    is_withheld = Column(Boolean, default=False)
    withholding_reason = Column(String(100), nullable=True) # 'INSUFFICIENT_HISTORY', 'LOW_REPORTING_COVERAGE'
    created_at = Column(DateTime, default=datetime.utcnow)

    model = relationship("ModelRegistry", back_populates="forecasts")

    __table_args__ = (
        UniqueConstraint("model_id", "district_pcode", "target_year", "target_week", "disease", name="uq_forecast_entry"),
    )
