"""
Routers Package Export
"""

from backend.routers.auth import router as auth_router
from backend.routers.overview import router as overview_router
from backend.routers.hotspots import router as hotspots_router
from backend.routers.ingestion import router as ingestion_router
from backend.routers.alerts import router as alerts_router
from backend.routers.models import router as models_router
from backend.routers.reports import router as reports_router

__all__ = [
    "auth_router",
    "overview_router",
    "hotspots_router",
    "ingestion_router",
    "alerts_router",
    "models_router",
    "reports_router"
]
