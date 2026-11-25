"""
Backend Application Configuration.
Supports dual-mode database (local SQLite and production PostgreSQL/PostGIS)
and JWT authentication settings.
"""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BACKEND_DIR.parent

# Database Connection URL (defaults to local SQLite database in workspace root)
DEFAULT_SQLITE_PATH = WORKSPACE_DIR / "sentinel.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}")

# Security & Authentication Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "Sentinel-Health-KP-Surveillance-JWT-Secret-Key-2026")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

# Data Asset Paths
PROCESSED_DIR = WORKSPACE_DIR / "data" / "processed"
DEMO_DIR = WORKSPACE_DIR / "data" / "demo_hospitals"

# Server Pepper for HMAC-SHA256 patient pseudonymization
SERVER_PEPPER = os.getenv("SERVER_PEPPER", "SentinelSurveillance-KP-PublicHealth-Pepper-2026-Secret")
