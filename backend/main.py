"""
Sentinel Health Surveillance - FastAPI Backend Application Entrypoint.
Connects REST API routers, database engine, CORS middleware, and health diagnostics.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import engine, Base
from backend.models import * # Import all models to register with Base
from backend.routers import (
    auth_router,
    overview_router,
    hotspots_router,
    ingestion_router,
    alerts_router,
    models_router,
    reports_router
)

# Initialize FastAPI App
app = FastAPI(
    title="Sentinel Health Surveillance API",
    description="District Hotspots & Disease Early-Warning Platform for Khyber Pakhtunkhwa (CS619)",
    version="1.0.0"
)

# Configure CORS Middleware for Frontend Development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect Routers
app.include_router(auth_router)
app.include_router(overview_router)
app.include_router(hotspots_router)
app.include_router(ingestion_router)
app.include_router(alerts_router)
app.include_router(models_router)
app.include_router(reports_router)


@app.on_event("startup")
def startup_event():
    """Ensure database schema is created on application startup."""
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {
        "platform": "Sentinel Health Surveillance Platform",
        "region": "Khyber Pakhtunkhwa, Pakistan",
        "districts_count": 35,
        "api_docs": "/docs",
        "status": "operational"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "mode": "sqlite_local_dev" if str(engine.url).startswith("sqlite") else "postgresql_production"
    }
