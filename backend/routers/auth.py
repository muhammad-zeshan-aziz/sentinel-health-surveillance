"""
Authentication Router.
Provides JWT login, current user profile, and demo accounts metadata.
"""

from typing import List
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.schemas.auth import LoginRequest, TokenResponse, UserProfile, DemoRoleInfo
from backend.security import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with username and password, returning JWT access token."""
    user = db.query(User).filter(User.username == request.username.strip(), User.is_active == True).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({
        "sub": user.username,
        "role": user.role,
        "facility_id": user.facility_id,
        "assigned_district_pcode": user.assigned_district_pcode
    })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        username=user.username,
        role=user.role,
        facility_id=user.facility_id,
        assigned_district_pcode=user.assigned_district_pcode
    )


@router.get("/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns profile of currently authenticated user."""
    return current_user


@router.get("/demo-roles", response_model=List[DemoRoleInfo])
def get_demo_roles():
    """Returns ready-to-use demo accounts for quick role-switching in the UI."""
    return [
        DemoRoleInfo(
            role="district_health_officer",
            username="dho_kp",
            title="District Health Officer (DHO)",
            description="Full surveillance authority: review hotspots, acknowledge early warning alerts, export aggregate reports.",
            assigned_location="Provincial Headquarters / All KP Districts"
        ),
        DemoRoleInfo(
            role="data_analyst",
            username="analyst_kp",
            title="Public Health Data Analyst",
            description="Data quality auditing, ML model performance tracking, drift diagnostics, aggregate analytical exports.",
            assigned_location="Directorate General Health Services KP"
        ),
        DemoRoleInfo(
            role="hospital_staff",
            username="staff_ath",
            title="Hospital Laboratory Staff",
            description="Facility-level portal: upload lab CSVs, monitor facility synchronization status, track own laboratory volume.",
            assigned_location="Ayub Teaching Hospital (ATH), Abbottabad (PK501)"
        )
    ]
