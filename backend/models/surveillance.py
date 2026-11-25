"""
Surveillance Panel, Lab Records, and Ingestion Batch Models.
Implements the patched schema with nullable missing (NR) surveillance fields
and privacy-safe age-banded lab records.
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date,
    ForeignKey, Text, BigInteger, UniqueConstraint
)
from sqlalchemy.orm import relationship

from backend.database import Base


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_uuid = Column(String(64), unique=True, nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True) # 'real_idsr', 'hospital_upload', 'mock_api_sync', 'synthetic_demo'
    uploaded_by_user_id = Column(Integer, nullable=True)
    filename = Column(String(255), nullable=True)
    record_count = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    status = Column(String(50), default="completed") # 'processing', 'completed', 'failed'
    error_log = Column(Text, nullable=True) # JSON serialized
    created_at = Column(DateTime, default=datetime.utcnow)

    lab_records = relationship("LabRecord", back_populates="batch", cascade="all, delete-orphan")


class LabRecord(Base):
    __tablename__ = "lab_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("ingestion_batches.id"), nullable=True, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True, index=True)
    district_pcode = Column(String(10), ForeignKey("districts.pcode"), nullable=False, index=True)
    patient_hash = Column(String(64), nullable=False, index=True) # Salted HMAC-SHA256
    external_record_id = Column(String(64), nullable=True, index=True)
    test_date = Column(Date, nullable=False, index=True)
    epi_week = Column(Integer, nullable=False)
    epi_year = Column(Integer, nullable=False)
    disease = Column(String(50), nullable=False, index=True)
    test_type = Column(String(100), nullable=True)
    test_result = Column(String(20), nullable=False) # 'Positive', 'Negative', 'Indeterminate'
    case_status = Column(String(20), default="suspected") # 'suspected', 'confirmed'
    age_band = Column(String(20), nullable=True) # '0-4', '5-14', '15-24', '25-44', '45-64', '65+'
    gender = Column(String(20), nullable=True)
    is_suspected = Column(Boolean, default=True)
    is_confirmed = Column(Boolean, default=False)
    is_corrected = Column(Boolean, default=False)
    corrected_at = Column(DateTime, nullable=True)
    episode_id = Column(String(64), nullable=True, index=True)
    is_duplicate_test = Column(Boolean, default=False)
    source_type = Column(String(50), default="hospital_upload")
    created_at = Column(DateTime, default=datetime.utcnow)

    batch = relationship("IngestionBatch", back_populates="lab_records")


class WeeklySurveillance(Base):
    __tablename__ = "weekly_surveillance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    district_pcode = Column(String(10), ForeignKey("districts.pcode"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    epi_week = Column(Integer, nullable=False)
    disease = Column(String(50), nullable=False, index=True)
    
    # Nullable fields to allow legitimate NULL representation for unsubmitted (NR) reports
    suspected_cases = Column(Integer, nullable=True)
    confirmed_cases = Column(Integer, nullable=True)
    total_cases = Column(Integer, nullable=True) # NULL when is_missing = True
    
    total_tests = Column(Integer, default=0, nullable=False)
    positive_tests = Column(Integer, default=0, nullable=False)
    positivity_rate = Column(Float, nullable=True)
    incidence_per_100k = Column(Float, nullable=True) # NULL when is_missing = True
    
    is_missing = Column(Boolean, default=False, nullable=False) # TRUE if unsubmitted/NR
    is_zero = Column(Boolean, default=False, nullable=False) # TRUE if confirmed 0 cases
    reporting_coverage = Column(Float, default=1.0, nullable=False)
    data_quality_flag = Column(String(255), nullable=True)
    source_provenance = Column(String(50), default="real_idsr", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    district = relationship("District", back_populates="surveillance_records")

    __table_args__ = (
        UniqueConstraint("district_pcode", "year", "epi_week", "disease", name="uq_district_week_disease"),
    )


class WeatherWeekly(Base):
    __tablename__ = "weather_weekly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    district_pcode = Column(String(10), ForeignKey("districts.pcode"), nullable=False)
    year = Column(Integer, nullable=False)
    epi_week = Column(Integer, nullable=False)
    temp_c_mean = Column(Float, nullable=True)
    rainfall_mm_total = Column(Float, nullable=True)
    humidity_percent_mean = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("district_pcode", "year", "epi_week", name="uq_weather_district_week"),
    )
