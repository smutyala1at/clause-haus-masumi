"""
Availability endpoint
"""

from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("")
async def availability():
    """
    Check if the service is available and ready to accept jobs (MIP-003 compliant).
    """
    return {
        "status": "available",
        "type": "masumi-agent"
    }

