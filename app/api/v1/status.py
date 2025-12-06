"""
Job status endpoint
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from app.schemas.job import StatusResponse
from app.services.job_service import JobService

router = APIRouter()


def get_job_service() -> JobService:
    """Dependency to get job service instance"""
    return JobService()


@router.get("", response_model=StatusResponse)
async def get_status(
    job_id: str = Query(..., description="Job identifier"),
    job_service: JobService = Depends(get_job_service)
):
    """
    Get the status of a job.
    """
    try:
        return await job_service.get_job_status(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

