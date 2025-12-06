"""
Job-related Pydantic schemas
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class InputDataItem(BaseModel):
    """Key-value pair for input data"""
    key: str = Field(..., description="Input key")
    value: str = Field(..., description="Input value")


class StartJobRequest(BaseModel):
    """Request model for starting a job"""
    input_data: List[InputDataItem] = Field(..., description="Array of key-value pairs")
    payment_id: Optional[str] = Field(None, description="Optional payment ID")


class StartJobResponse(BaseModel):
    """Response model for job creation"""
    job_id: str = Field(..., description="Unique job identifier")
    payment_id: Optional[str] = Field(None, description="Payment ID if provided")


class StatusResponse(BaseModel):
    """Job status response"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    result: Optional[Dict] = Field(None, description="Job result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
