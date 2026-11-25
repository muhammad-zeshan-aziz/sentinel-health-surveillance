"""
User & Role-Based Access Control (RBAC) Model.
Supports Hospital Staff, Data Analyst, and District Health Officer personas.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey
)
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, index=True) # 'hospital_staff', 'data_analyst', 'district_health_officer'
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True)
    assigned_district_pcode = Column(String(10), ForeignKey("districts.pcode"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
