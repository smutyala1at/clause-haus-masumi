"""
Start job endpoint (MIP-003: /start_job)
Exact match to Masumi example pattern
"""

import logging
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job import StartJobRequest
from app.services.job_service import JobService
from app.db.base import get_db
from app.core.config import settings

# Import Masumi SDK
try:
    from masumi.config import Config
    from masumi.payment import Payment, Amount
    MASUMI_SDK_AVAILABLE = True
except ImportError:
    MASUMI_SDK_AVAILABLE = False
    Config = None
    Payment = None
    Amount = None

logger = logging.getLogger(__name__)
router = APIRouter()


def get_job_service() -> JobService:
    """Dependency to get job service instance"""
    return JobService()


# Initialize Masumi Payment Config (exact match to example)
config = None
if MASUMI_SDK_AVAILABLE and settings.PAYMENT_SERVICE_URL and settings.PAYMENT_API_KEY:
    config = Config(
        payment_service_url=settings.PAYMENT_SERVICE_URL,
        payment_api_key=settings.PAYMENT_API_KEY
    )


@router.post("")
async def start_job(
    data: StartJobRequest,
    job_service: JobService = Depends(get_job_service),
    db: AsyncSession = Depends(get_db)
):
    """ Initiates a job and creates a payment request (exact match to example) """
    print(f"Received data: {data}")
    print(f"Received data.input_data: {data.input_data}")
    try:
        job_id = str(uuid.uuid4())
        agent_identifier = settings.AGENT_IDENTIFIER
        
        # Log the input (truncate if too long)
        input_value = list(data.input_data.values())[0] if data.input_data else ""
        truncated_input = input_value[:100] + "..." if len(input_value) > 100 else input_value
        logger.info(f"Received job request with input: '{truncated_input}'")
        logger.info(f"Starting job {job_id} with agent {agent_identifier}")

        # Define payment amounts (exact match to example)
        payment_amount = settings.PAYMENT_AMOUNT or "10000000"  # Default 10 ADA
        payment_unit = settings.PAYMENT_UNIT or "lovelace"  # Default lovelace

        amounts = []
        if MASUMI_SDK_AVAILABLE and Amount:
            amounts = [Amount(amount=payment_amount, unit=payment_unit)]
        logger.info(f"Using payment amount: {payment_amount} {payment_unit}")
        
        # Create a payment request using Masumi (exact match to example)
        payment = None
        payment_request = None
        blockchain_identifier = None
        
        if config and agent_identifier:
            payment = Payment(
                agent_identifier=agent_identifier,
                #amounts=amounts,  # Commented out like example
                config=config,
                identifier_from_purchaser=data.identifier_from_purchaser,
                input_data=data.input_data,
                network=settings.NETWORK
            )
            
            logger.info("Creating payment request...")
            payment_request = await payment.create_payment_request()
            blockchain_identifier = payment_request["data"]["blockchainIdentifier"]
            payment.payment_ids.add(blockchain_identifier)
            logger.info(f"Created payment request with ID: {blockchain_identifier}")

        # Store job info in database (instead of in-memory dict)
        await job_service.create_job_in_db(
            job_id=job_id,
            blockchain_identifier=blockchain_identifier,
            identifier_from_purchaser=data.identifier_from_purchaser,
            input_data=data.input_data,
            status="awaiting_payment",
            db=db
        )

        async def payment_callback(blockchain_identifier: str):
            from app.db.base import get_session_factory
            session_factory = get_session_factory()
            async with session_factory() as new_db:
                await job_service.handle_payment_status(job_id, blockchain_identifier, new_db)

        # Start monitoring the payment status (exact match to example)
        if payment and blockchain_identifier:
            job_service.payment_instances[job_id] = payment
            logger.info(f"Starting payment status monitoring for job {job_id}")
            await payment.start_status_monitoring(payment_callback)

        # Return the response in the required format (exact match to example)
        return {
            "status": "success",
            "job_id": job_id,
            "blockchainIdentifier": blockchain_identifier,
            "submitResultTime": payment_request["data"]["submitResultTime"] if payment_request else None,
            "unlockTime": payment_request["data"]["unlockTime"] if payment_request else None,
            "externalDisputeUnlockTime": payment_request["data"]["externalDisputeUnlockTime"] if payment_request else None,
            "agentIdentifier": agent_identifier,
            "sellerVKey": settings.SELLER_VKEY,
            "identifierFromPurchaser": data.identifier_from_purchaser,
            "amounts": amounts,  # Return Amount objects directly like example
            "input_hash": payment.input_hash if payment else None,
            "payByTime": payment_request["data"]["payByTime"] if payment_request else None,
        }
    except KeyError as e:
        logger.error(f"Missing required field in request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Bad Request: If input_data or identifier_from_purchaser is missing, invalid, or does not adhere to the schema."
        )
    except Exception as e:
        logger.error(f"Error in start_job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Input_data or identifier_from_purchaser is missing, invalid, or does not adhere to the schema."
        )

