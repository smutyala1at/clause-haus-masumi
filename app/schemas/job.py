"""
Job-related Pydantic schemas
"""

from typing import Optional, List, Dict, Any
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
    """Response model for job creation (MIP-003 compliant)"""
    status: str = Field(default="success", description="Status of job creation")
    job_id: str = Field(..., description="Unique job identifier")
    blockchainIdentifier: Optional[str] = Field(None, alias="blockchain_identifier", description="Blockchain payment identifier")
    payment_id: Optional[str] = Field(None, description="Payment ID (legacy, use blockchainIdentifier)")
    submitResultTime: Optional[int] = Field(None, alias="submit_result_time", description="Time to submit result")
    unlockTime: Optional[int] = Field(None, alias="unlock_time", description="Time when payment unlocks")
    externalDisputeUnlockTime: Optional[int] = Field(None, alias="external_dispute_unlock_time", description="External dispute unlock time")
    agentIdentifier: Optional[str] = Field(None, alias="agent_identifier", description="Agent identifier")
    sellerVKey: Optional[str] = Field(None, alias="seller_vkey", description="Seller verification key")
    identifierFromPurchaser: Optional[str] = Field(None, alias="identifier_from_purchaser", description="Identifier from purchaser")
    amounts: Optional[List[Dict[str, Any]]] = Field(None, description="Payment amounts")
    input_hash: Optional[str] = Field(None, description="Hash of input data")
    payByTime: Optional[int] = Field(None, alias="pay_by_time", description="Time by which payment must be made")
    
    class Config:
        populate_by_name = True


class StatusResponse(BaseModel):
    """Job status response (MIP-003 compliant)"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    result: Optional[str] = Field(None, description="Job result as string if completed (MIP-003)")
    error: Optional[str] = Field(None, description="Error message if failed")
