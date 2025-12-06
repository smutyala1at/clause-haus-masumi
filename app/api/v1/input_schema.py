"""
Input schema endpoint
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def input_schema():
    """
    Get the input schema for job requests.
    """
    return {
        "type": "object",
        "properties": {
            "input_data": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"}
                    },
                    "required": ["key", "value"]
                }
            },
            "payment_id": {
                "type": "string",
                "description": "Optional payment ID"
            }
        },
        "required": ["input_data"]
    }

