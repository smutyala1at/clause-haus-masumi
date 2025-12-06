"""
BGB Embedding endpoint
"""

import logging

from fastapi import APIRouter, HTTPException, Security, Depends
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.base import get_db
from app.services.bgb_embedding_service import BGBEmbeddingService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/embed")
async def embed_bgb_sections(
    api_key: str = Security(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Embed BGB sections from bgb_mapped.json and store in database.
    
    Features:
    - Only embeds sections that have changed (checksum-based)
    - Formats German text with metadata for better embeddings
    - Batch processing for efficiency
    
    Requires API key authentication via X-API-Key header.
    """
    try:
        service = BGBEmbeddingService()
        
        # Load BGB mapped JSON
        data = service.load_bgb_mapped_json()
        sections = data.get('sections', [])
        
        if not sections:
            raise HTTPException(
                status_code=400, 
                detail="No sections found in bgb_mapped.json"
            )
        
        # Embed sections (with checksum-based deduplication)
        result = await service.embed_sections(db, sections)
        
        return {
            "message": "BGB sections embedded successfully",
            "total_sections": result['total_sections'],
            "embedded": result['embedded'],
            "skipped": result['skipped'],
            "errors": result['errors']
        }
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error embedding BGB sections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error embedding BGB sections: {str(e)}")

