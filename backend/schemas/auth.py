"""
Pydantic Schemas for Authentication and Role Profiles.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    facility_id: Optional[int] = None
    assigned_district_pcode: Optional[str] = None


class UserProfile(BaseModel):
    id: int
    username: str
    email: str
    role: str
    facility_id: Optional[int] = None
    assigned_district_pcode: Optional[str] = None
    is_active: bool

    class Config:
        orm_mode = True
        from_attributes = True


class DemoRoleInfo(BaseModel):
    role: str
    username: str
    title: str
    description: str
    assigned_location: str
