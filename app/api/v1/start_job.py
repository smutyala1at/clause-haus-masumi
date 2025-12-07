"""
Start job endpoint
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job import StartJobRequest, StartJobResponse
from app.services.job_service import JobService
from app.db.base import get_db

router = APIRouter()


def get_job_service() -> JobService:
    """Dependency to get job service instance"""
    return JobService()


@router.post("", response_model=StartJobResponse, status_code=201)
async def start_job(
    request: StartJobRequest,
    background_tasks: BackgroundTasks,
    job_service: JobService = Depends(get_job_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new contract analysis job (MIP-003 compliant).
    
    Accepts a PDF document (base64 or URL) and analyzes it against German BGB laws
    to identify problematic, unfair, or illegal clauses.
    
    Request format (MIP-003):
    {
        "identifier_from_purchaser": "optional_identifier",
        "input_data": [
            {"key": "document", "value": "data:application/pdf;base64,..."}
        ]
    }
    """
    # Generate payment_id from job_id (MIP-003: payment_id is returned in response)
    response = await job_service.create_job(
        input_data=request.input_data,
        identifier_from_purchaser=request.identifier_from_purchaser
    )
    
    # Start processing in background with database session
    background_tasks.add_task(job_service.process_job, response.job_id, db)
    
    return response

