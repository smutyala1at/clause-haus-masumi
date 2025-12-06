"""
Payment service for Masumi Payment Service integration
"""

import logging
import httpx
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for handling Masumi payment operations"""
    
    def __init__(self):
        self.payment_service_url = settings.PAYMENT_SERVICE_URL
        self.payment_api_key = settings.PAYMENT_API_KEY
    
    async def purchase_job_output(self, job_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle payment for a completed job.
        This endpoint should be called by the Masumi Payment Service.
        
        Args:
            job_output: Job output to purchase
            
        Returns:
            Payment response from Masumi Payment Service
            
        Raises:
            ValueError: If payment service is not configured
            httpx.HTTPError: If payment request fails
        """
        if not self.payment_service_url:
            raise ValueError("Payment service not configured")
        
        if not self.payment_api_key:
            raise ValueError("Payment API key not configured")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.payment_service_url}/purchase",
                    json=job_output,
                    headers={
                        "Authorization": f"Bearer {self.payment_api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Payment service error: {str(e)}")
            raise
    
    def is_configured(self) -> bool:
        """Check if payment service is properly configured"""
        return bool(self.payment_service_url and self.payment_api_key)

