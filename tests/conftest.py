"""
Pytest Fixtures and Global Configuration for Sentinel Health Surveillance Suite.
Provides isolated test clients, database sessions, and pre-authenticated tokens
for all 3 CS619 RBAC roles (DHO, Data Analyst, Hospital Staff).
"""

import sys
import os
import pytest
from pathlib import Path

# Add project root to Python module search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.security import create_access_token

@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function")
def db_session():
    """Isolated SQLAlchemy database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="session")
def dho_token():
    """JWT Access Token for District Health Officer (DHO)."""
    return create_access_token({
        "sub": "dho_kp",
        "role": "district_health_officer",
        "facility_id": None,
        "assigned_district_pcode": None
    })

@pytest.fixture(scope="session")
def dho_headers(dho_token):
    return {"Authorization": f"Bearer {dho_token}"}

@pytest.fixture(scope="session")
def analyst_token():
    """JWT Access Token for Public Health Data Analyst."""
    return create_access_token({
        "sub": "analyst_kp",
        "role": "data_analyst",
        "facility_id": None,
        "assigned_district_pcode": None
    })

@pytest.fixture(scope="session")
def analyst_headers(analyst_token):
    return {"Authorization": f"Bearer {analyst_token}"}

@pytest.fixture(scope="session")
def staff_token():
    """JWT Access Token for Sentinel Hospital Staff."""
    return create_access_token({
        "sub": "staff_ath",
        "role": "hospital_staff",
        "facility_id": 1,
        "assigned_district_pcode": "PK501"
    })

@pytest.fixture(scope="session")
def staff_headers(staff_token):
    return {"Authorization": f"Bearer {staff_token}"}

@pytest.fixture(scope="session")
def paths():
    """Project directory paths fixture."""
    return {
        "root": PROJECT_ROOT,
        "data_raw": PROJECT_ROOT / "data" / "raw",
        "data_processed": PROJECT_ROOT / "data" / "processed",
        "models": PROJECT_ROOT / "models",
        "frontend": PROJECT_ROOT / "frontend",
        "dist": PROJECT_ROOT / "frontend" / "dist",
    }
