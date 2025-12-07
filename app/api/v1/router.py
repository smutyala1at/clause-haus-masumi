"""
API v1 router configuration
"""

from fastapi import APIRouter
from app.api.v1 import start_job
from app.api.v1 import status
from app.api.v1 import availability
from app.api.v1 import input_schema
from app.api.v1 import health
from app.api.v1 import bgb_parse
from app.api.v1 import bgb_embed
from app.api.v1 import contract_analysis

api_router = APIRouter()

api_router.include_router(start_job.router, prefix="/start_job", tags=["jobs"])
api_router.include_router(status.router, prefix="/status", tags=["jobs"])
api_router.include_router(availability.router, prefix="/availability", tags=["service"])
api_router.include_router(input_schema.router, prefix="/input_schema", tags=["service"])
api_router.include_router(health.router, prefix="/health", tags=["service"])
api_router.include_router(bgb_parse.router, prefix="/bgb", tags=["bgb"])
api_router.include_router(bgb_embed.router, prefix="/bgb", tags=["bgb"])
api_router.include_router(contract_analysis.router, prefix="/contract", tags=["contract"])
