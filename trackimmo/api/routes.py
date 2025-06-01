"""
API routes for TrackImmo.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any

from trackimmo.config import settings
from trackimmo.api.client_processing import router as client_router
from trackimmo.api.admin import router as admin_router
from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

# Create main API router
router = APIRouter()

# Include sub-routers
router.include_router(client_router)
router.include_router(admin_router)

@router.get("/health", response_model=Dict[str, str])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "service": "TrackImmo API",
        "version": "1.0.1"
    }

@router.get("/version", response_model=Dict[str, str])
async def version():
    """Get API version."""
    return {
        "version": "1.0.1",
        "service": "TrackImmo API"
    }