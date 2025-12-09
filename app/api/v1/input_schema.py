"""
Input schema endpoint (MIP-003: /input_schema)
Returns the expected input schema for the /start_job endpoint.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def input_schema():
    """
    Returns the expected input schema for the /start_job endpoint.
    Fulfills MIP-003 /input_schema endpoint.
    
    This service analyzes rental contracts (PDF) against German BGB laws.
    """
    return {
        "input_data": [
            {
                "type": "file",
                "name": "Document Upload",
                "data": {
                    "accept": ".pdf",
                    "maxSize": "10485760",
                    "description": "Upload a German rental contract PDF document for analysis against BGB laws to identify problematic, unfair, or illegal clauses (max 10MB)",
                    "outputFormat": "base64"
                }
            }
        ]
    }

