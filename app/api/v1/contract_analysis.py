"""
Contract Analysis endpoint
Analyzes contracts against BGB laws using the complete pipeline.
"""

import logging
from fastapi import APIRouter, HTTPException, Security, Depends, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.base import get_db
from app.services.contract_analysis_pipeline import ContractAnalysisPipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze")
async def analyze_contract(
    input_data: dict = Body(...),
    api_key: str = Security(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Direct contract analysis endpoint (non-blocking, returns immediately).
    
    For Masumi Network standard flow, use POST /api/v1/start_job instead.
    
    Expects input_data with a PDF value (base64 or URL):
    {
        "input_data": [
            {"key": "document", "value": "data:application/pdf;base64,..."}
        ]
    }
    
    Returns:
        Analysis results with found clauses
    """
    try:
        if "input_data" not in input_data:
            raise HTTPException(status_code=400, detail="input_data field required")
        
        pdf_value = None
        for item in input_data["input_data"]:
            if item.get("key") in ["document", "pdf"]:
                pdf_value = item.get("value")
                break
        
        if not pdf_value:
            for item in input_data["input_data"]:
                value = item.get("value", "")
                if isinstance(value, str) and (
                    value.startswith("data:application/pdf") or
                    value.startswith("http") or
                    len(value) > 1000
                ):
                    pdf_value = value
                    break
        
        if not pdf_value:
            raise HTTPException(
                status_code=400,
                detail="No PDF found in input_data. Expected 'document' or 'pdf' key with base64 or URL value."
            )
        
        pipeline = ContractAnalysisPipeline()
        result = await pipeline.process_contract(db=db, pdf_input=pdf_value)
        
        return {"output": result['output']}
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing contract: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing contract: {str(e)}")


@router.post("/test")
async def analyze_contract_test(
    file: UploadFile = File(..., description="PDF file to analyze"),
    api_key: str = Security(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Test endpoint for local development - upload PDF file directly.
    
    Use this endpoint from Swagger UI (/docs) for easy testing.
    """
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        file_content = await file.read()
        pipeline = ContractAnalysisPipeline()
        result = await pipeline.process_contract(
            db=db,
            pdf_input=file_content,
            file_name=file.filename
        )
        
        return {"output": result['output']}
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing contract: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing contract: {str(e)}")

