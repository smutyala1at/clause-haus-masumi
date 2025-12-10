"""
Payment service for Masumi Payment Service integration using Masumi SDK
"""

import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import Masumi SDK, fallback to HTTP if not available
try:
    from masumi.config import Config
    from masumi.payment import Payment, Amount
    MASUMI_SDK_AVAILABLE = True
except ImportError:
    MASUMI_SDK_AVAILABLE = False
    logger.warning("Masumi SDK not available. Install with: pip install masumi")
    Config = None
    Payment = None
    Amount = None


class PaymentService:
    """Service for handling Masumi payment operations using Masumi SDK"""
    
    def __init__(self):
        self.payment_service_url = settings.PAYMENT_SERVICE_URL
        self.payment_api_key = settings.PAYMENT_API_KEY
        self.seller_vkey = settings.SELLER_VKEY
        self.network = settings.NETWORK
        self.agent_identifier = settings.AGENT_IDENTIFIER
        self.payment_amount = settings.PAYMENT_AMOUNT
        self.payment_unit = settings.PAYMENT_UNIT
        
        # Initialize Masumi Config if SDK is available
        self.config = None
        if MASUMI_SDK_AVAILABLE and self.payment_service_url and self.payment_api_key:
            try:
                self.config = Config(
                    payment_service_url=self.payment_service_url,
                    payment_api_key=self.payment_api_key
                )
            except Exception as e:
                logger.error(f"Failed to initialize Masumi Config: {e}")
    
    def is_configured(self) -> bool:
        """Check if payment service is properly configured"""
        return bool(self.payment_service_url and self.payment_api_key and self.agent_identifier)
    
    def get_agent_info(self) -> dict:
        """Get agent information for Masumi Network"""
        return {
            "network": self.network,
            "agent_identifier": self.agent_identifier,
            "seller_vkey": self.seller_vkey
        }
    
    async def create_payment_request(
        self,
        identifier_from_purchaser: str,
        input_data: Dict[str, Any],
        amounts: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Create a payment request using Masumi SDK.
        
        Args:
            identifier_from_purchaser: Identifier from purchaser
            input_data: Input data for the job
            amounts: Optional list of Amount objects (defaults to no payment if None)
            
        Returns:
            Payment request response with blockchainIdentifier and other details
            
        Raises:
            ValueError: If payment service is not configured or SDK not available
        """
        if not MASUMI_SDK_AVAILABLE:
            raise ValueError("Masumi SDK not available. Install with: pip install masumi")
        
        if not self.is_configured():
            raise ValueError("Payment service not fully configured (missing required settings)")
        
        if not self.config:
            raise ValueError("Masumi Config not initialized")
        
        try:
            # Create Payment object (Masumi pattern - no amounts in constructor)
            payment = Payment(
                agent_identifier=self.agent_identifier,
                config=self.config,
                identifier_from_purchaser=identifier_from_purchaser,
                input_data=input_data,
                network=self.network
            )
            
            # Create payment request (Masumi pattern)
            logger.info("Creating payment request...")
            payment_request = await payment.create_payment_request()
            
            blockchain_identifier = payment_request["data"]["blockchainIdentifier"]
            
            # Add blockchain identifier to payment (Masumi pattern)
            payment.payment_ids.add(blockchain_identifier)
            
            logger.info(f"Created payment request with ID: {blockchain_identifier}")
            
            return {
                "payment": payment,
                "payment_request": payment_request,
                "blockchain_identifier": blockchain_identifier
            }
        except Exception as e:
            logger.error(f"Error creating payment request: {e}")
            raise
    
    async def start_payment_monitoring(
        self,
        payment: Payment,
        callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """
        Start monitoring payment status.
        
        Args:
            payment: Payment object from create_payment_request
            callback: Async callback function that receives blockchain_identifier
        """
        if not MASUMI_SDK_AVAILABLE:
            raise ValueError("Masumi SDK not available")
        
        try:
            await payment.start_status_monitoring(callback)
        except Exception as e:
            logger.error(f"Error starting payment monitoring: {e}")
            raise
    
    async def complete_payment(
        self,
        payment: Payment,
        blockchain_identifier: str,
        result_string: str
    ) -> None:
        """
        Complete a payment after job processing.
        
        Args:
            payment: Payment object
            blockchain_identifier: Blockchain identifier from payment request
            result_string: Job result as string
        """
        if not MASUMI_SDK_AVAILABLE:
            raise ValueError("Masumi SDK not available")
        
        try:
            await payment.complete_payment(blockchain_identifier, result_string)
            logger.info(f"Payment {blockchain_identifier} completed successfully")
        except Exception as e:
            logger.error(f"Error completing payment: {e}")
            raise
    
    async def check_payment_status(
        self,
        payment: Payment
    ) -> Dict[str, Any]:
        """
        Check the current status of a payment.
        
        Args:
            payment: Payment object
            
        Returns:
            Payment status dictionary
        """
        if not MASUMI_SDK_AVAILABLE:
            raise ValueError("Masumi SDK not available")
        
        try:
            status = await payment.check_payment_status()
            return status
        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
            raise

