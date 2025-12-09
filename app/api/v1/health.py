"""
Health check endpoint
"""

from fastapi import APIRouter
from app.core.config import settings
from app.services.payment_service import PaymentService

router = APIRouter()


@router.get("")
async def health():
    """
    Health check endpoint.
    """
    payment_service = PaymentService()
    
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "payment_service_configured": payment_service.is_configured(),
        "payment_service_url_configured": bool(settings.PAYMENT_SERVICE_URL),
        "payment_api_key_configured": bool(settings.PAYMENT_API_KEY),
        "seller_vkey_configured": bool(settings.SELLER_VKEY),
        "network": settings.NETWORK,
        "agent_identifier_configured": bool(settings.AGENT_IDENTIFIER)
    }
