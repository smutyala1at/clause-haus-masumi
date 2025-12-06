"""
Start job endpoint
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from app.schemas.job import StartJobRequest, StartJobResponse
from app.services.job_service import JobService

router = APIRouter()


def get_job_service() -> JobService:
    """Dependency to get job service instance"""
    return JobService()


@router.post("", response_model=StartJobResponse, status_code=201)
async def start_job(
    request: StartJobRequest,
    background_tasks: BackgroundTasks,
    job_service: JobService = Depends(get_job_service)
):
    """
    Start a new job and begin processing it.
    """
    job_id = await job_service.create_job(
        input_data=request.input_data,
        payment_id=request.payment_id
    )
    
    # Start processing in background
    background_tasks.add_task(job_service.process_job, job_id)
    
    return StartJobResponse(
        job_id=job_id,
        payment_id=request.payment_id
    )

