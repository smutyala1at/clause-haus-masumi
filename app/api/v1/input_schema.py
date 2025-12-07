"""
Input schema endpoint
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def input_schema():
    """
    Get the input schema for job requests.
    
    This service analyzes rental contracts (PDF) against German BGB laws.
    """
    return {
        "type": "object",
        "properties": {
            "input_data": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Input key (e.g., 'document', 'pdf')"
                        },
                        "value": {
                            "type": "string",
                            "description": "PDF document as base64 data URI (data:application/pdf;base64,...) or URL"
                        }
                    },
                    "required": ["key", "value"]
                },
                "description": "Array of key-value pairs. Must include a PDF document with key 'document' or 'pdf'"
            },
            "payment_id": {
                "type": "string",
                "description": "Optional payment ID"
            }
        },
        "required": ["input_data"]
    }

