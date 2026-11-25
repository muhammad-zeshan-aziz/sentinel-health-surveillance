"""
Alert & Outbreak Warning Model.
Stores CDC EARS C1/C2/C3 scores, composite hotspot metrics, and DHO review audit workflows.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text
)
from sqlalchemy.orm import relationship

from backend.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    district_pcode = Column(String(10), ForeignKey("districts.pcode"), nullable=False, index=True)
    disease = Column(String(50), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    epi_week = Column(Integer, nullable=False)
    alert_level = Column(String(20), nullable=False, index=True) # 'routine', 'watch', 'priority_review'
    composite_score = Column(Float, nullable=False)
    ears_c1_score = Column(Float, default=0.0)
    ears_c2_score = Column(Float, default=0.0)
    ears_c3_score = Column(Float, default=0.0)
    forecast_breach = Column(Boolean, default=False)
    incidence_per_100k = Column(Float, default=0.0)
    headline = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    district = relationship("District", back_populates="alerts")
