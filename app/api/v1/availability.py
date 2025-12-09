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
    response = {
        "status": "available",
        "type": "masumi-agent",
        "network": settings.NETWORK
    }
    
    # Include agent identifier if configured
    if settings.AGENT_IDENTIFIER:
        response["agent_identifier"] = settings.AGENT_IDENTIFIER
    
    return response

