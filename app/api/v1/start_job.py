"""
Start job endpoint (MIP-003: /start_job)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job import StartJobRequest, StartJobResponse
from app.services.job_service import JobService
from app.db.base import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def get_job_service() -> JobService:
    """Dependency to get job service instance"""
    return JobService()


@router.post("", response_model=StartJobResponse, status_code=201)
async def start_job(
    request: StartJobRequest,
    job_service: JobService = Depends(get_job_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new contract analysis job (MIP-003 compliant).
    
    Initiates a job and creates a payment request. Returns immediately.
    Job processing starts automatically after payment is confirmed.
    
    Request format (MIP-003):
    {
        "identifier_from_purchaser": "optional_identifier",
        "input_data": {
            "document_upload": "https://..."  // Masumi uploads file and sends URL string
        }
    }
    """
    try:
        # Create job, payment request, and start monitoring (Masumi pattern)
        response = await job_service.create_job_with_payment_and_monitoring(
            input_data=request.input_data,
            identifier_from_purchaser=request.identifier_from_purchaser,
            db=db
        )
        
        return response
    except KeyError as e:
        logger.error(f"Missing required field in request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Bad Request: If input_data or identifier_from_purchaser is missing, invalid, or does not adhere to the schema."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in start_job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Input_data or identifier_from_purchaser is missing, invalid, or does not adhere to the schema."
        )

