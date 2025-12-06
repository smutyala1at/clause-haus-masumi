"""
Availability endpoint
"""

from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("")
async def availability():
    """
    Check if the service is available and ready to accept jobs.
    """
    return {
        "available": True,
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

