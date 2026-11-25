"""
District and Facility Spatial Models.
Stores HDX P-Codes, 2023 Census Populations, and GeoJSON boundaries.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from backend.database import Base


class District(Base):
    __tablename__ = "districts"

    pcode = Column(String(10), primary_key=True) # e.g. 'PK501'
    name = Column(String(100), nullable=False)
    name_clean = Column(String(100), nullable=False)
    division = Column(String(100), nullable=False)
    population_2023 = Column(Integer, nullable=False)
    population_male = Column(Integer, nullable=True)
    population_female = Column(Integer, nullable=True)
    area_sqkm = Column(Float, nullable=False)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    # Stored as GeoJSON string for seamless cross-database compatibility (SQLite + PostgreSQL)
    geojson_geometry = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    facilities = relationship("Facility", back_populates="district")
    surveillance_records = relationship("WeeklySurveillance", back_populates="district")
    alerts = relationship("Alert", back_populates="district")


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    district_pcode = Column(String(10), ForeignKey("districts.pcode"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    facility_type = Column(String(50), nullable=False) # 'tertiary_hospital', 'dhq', 'thq', 'lab'
    tehsil = Column(String(100), nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    is_spotlight = Column(Boolean, default=False)
    is_mock = Column(Boolean, default=False)
    api_sync_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    district = relationship("District", back_populates="facilities")
