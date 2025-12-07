"""
Job-related Pydantic schemas
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class InputDataItem(BaseModel):
    """Key-value pair for input data (MIP-003 format)"""
    key: str = Field(..., description="Input key (e.g., 'document', 'pdf')")
    value: str = Field(..., description="PDF document as base64 data URI (data:application/pdf;base64,...) or URL string")


class StartJobRequest(BaseModel):
    """Request model for starting a job (MIP-003 compliant)"""
    identifier_from_purchaser: Optional[str] = Field(None, description="Optional identifier from purchaser")
    input_data: List[InputDataItem] = Field(..., description="Array of key-value pairs")


class StartJobResponse(BaseModel):
    """Response model for job creation"""
    job_id: str = Field(..., description="Unique job identifier")
    payment_id: Optional[str] = Field(None, description="Payment ID if provided")


class StatusResponse(BaseModel):
    """Job status response (MIP-003 compliant)"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    result: Optional[str] = Field(None, description="Job result as string if completed (MIP-003)")
    error: Optional[str] = Field(None, description="Error message if failed")
