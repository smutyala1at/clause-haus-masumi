"""
BGB Parser endpoint
"""

from fastapi import APIRouter, HTTPException, Security
from pathlib import Path
import json
from app.services.bgb_parser import BGBParser
from app.core.security import verify_api_key

router = APIRouter()


@router.post("/parse")
async def parse_bgb(api_key: str = Security(verify_api_key)):
    """
    Parse BGB German and English files and generate mapped JSON.
    
    Requires API key authentication via X-API-Key header.
    Set API_KEY in environment variables to enable authorization.
    """
    try:
        # Get file paths
        data_dir = Path(__file__).parent.parent.parent / "data"
        english_path = data_dir / "bgb_english.txt"
        german_path = data_dir / "bgb_german.txt"
        
        if not english_path.exists():
            raise HTTPException(status_code=404, detail=f"English file not found: {english_path}")
        if not german_path.exists():
            raise HTTPException(status_code=404, detail=f"German file not found: {german_path}")
        
        # Parse and map (only Book 3 - Property Law)
        parser = BGBParser()
        result = parser.parse_and_map(str(english_path), str(german_path), book_filter=3)
        
        # Save to JSON file
        output_path = data_dir / "bgb_mapped.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return {
            "message": "BGB files parsed and mapped successfully",
            "sections_count": len(result['sections']),
            "output_file": str(output_path)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing BGB files: {str(e)}")

