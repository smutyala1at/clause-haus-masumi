"""
Masumi MIP-003 compliant API router
Only includes Masumi standard endpoints
"""

from fastapi import APIRouter
from app.api.v1 import start_job
from app.api.v1 import status
from app.api.v1 import availability
from app.api.v1 import input_schema
from app.api.v1 import health
from app.api.v1 import examples

api_router = APIRouter()

# Masumi MIP-003 standard endpoints
api_router.include_router(start_job.router, prefix="/start_job", tags=["jobs"])
api_router.include_router(status.router, prefix="/status", tags=["jobs"])
api_router.include_router(availability.router, prefix="/availability", tags=["service"])
api_router.include_router(input_schema.router, prefix="/input_schema", tags=["service"])
api_router.include_router(health.router, prefix="/health", tags=["service"])

# Example output endpoints (for Masumi agent registration)
api_router.include_router(examples.router, prefix="/example", tags=["examples"])
