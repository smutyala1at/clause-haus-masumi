"""
Contract Analysis Pipeline
Complete pipeline: PDF → OCR → Chunking → Embedding → Similarity Search → Analysis
"""

import json
import logging
from typing import List, Dict, Any, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.mistral_ocr_service import MistralOCRService
from app.services.contract_chunking_service import ContractChunkingService
from app.services.openai_service import OpenAIService
from app.services.bgb_similarity_service import BGBSimilarityService
from app.schemas.contract_analysis import BatchClauseAnalysisResponse

logger = logging.getLogger(__name__)


class ContractAnalysisPipeline:
    """
    Complete pipeline for analyzing contracts against BGB laws.
    
    Steps:
    1. PDF → OCR (Mistral) → Text
    2. Text → Chunking by headings
    3. Chunks → Embeddings (OpenAI)
    4. Embeddings → Similarity search against BGB laws
    5. Relevant BGB sections → OpenAI chat analysis → Find clauses
    """
    
    def __init__(
        self,
        mistral_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        similarity_top_k: int = 5,
        similarity_threshold: float = 0.5
    ):
        """
        Initialize pipeline.
        
        Args:
            mistral_api_key: Mistral API key (optional, uses settings if not provided)
            openai_api_key: OpenAI API key (optional, uses settings if not provided)
            similarity_top_k: Number of similar BGB sections per chunk
            similarity_threshold: Minimum cosine similarity score (0-1, default 0.5 for moderate similarity)
        """
        self.ocr_service = MistralOCRService(api_key=mistral_api_key)
        self.chunking_service = ContractChunkingService()
        self.openai_service = OpenAIService(api_key=openai_api_key)
        self.similarity_service = BGBSimilarityService(
            top_k=similarity_top_k,
            similarity_threshold=similarity_threshold
        )
    
    async def process_contract(
        self,
        db: AsyncSession,
        pdf_input: Union[str, bytes],
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a contract PDF through the complete pipeline.
        
        Args:
            db: Database session
            pdf_input: PDF as base64 string, URL string, or bytes
            file_name: Optional file name (required if pdf_input is bytes)
            
        Returns:
            Dict with 'output' (string), 'chunks', 'embeddings', and 'openai_result' for caching
        """
        logger.info("Starting contract analysis pipeline...")
        
        # Step 1: PDF → OCR → Text
        logger.info("Step 1: Extracting text from PDF with OCR...")
        ocr_result = await self.ocr_service.process_pdf(pdf_input, file_name)
        
        # Extract text from OCR result
        text = self._extract_text_from_ocr(ocr_result)
        if not text:
            raise ValueError("No text extracted from PDF")
        
        logger.info(f"Extracted {len(text)} characters from PDF")
        
        # Step 2: Text → Chunking by headings
        logger.info("Step 2: Chunking contract by headings...")
        chunks = self.chunking_service.chunk_by_headings(text)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 3: Chunks → Embeddings
        logger.info("Step 3: Generating embeddings for chunks...")
        chunk_texts = [chunk['text'] for chunk in chunks]
        embeddings = await self.openai_service.create_embeddings(
            texts=chunk_texts,
            model="text-embedding-3-small",
            batch_size=100
        )
        
        # Step 4: Embeddings → Similarity search against BGB
        logger.info("Step 4: Searching for similar BGB sections...")
        chunk_results = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            similar_bgb = await self.similarity_service.search_similar(
                db,
                embedding.embedding,
                top_k=5
            )
            
            chunk_results.append({
                'chunk_index': i,
                'chunk_text': chunk['text'],
                'chunk_heading': chunk.get('heading'),
                'similar_bgb_sections': similar_bgb
            })
        
        # Step 5: Analyze with OpenAI chat to find clauses (batch all chunks in one request)
        logger.info("Step 5: Analyzing all chunks with OpenAI in one batch request...")
        
        # Filter chunks that have similar BGB sections
        chunks_with_bgb = [
            chunk_result for chunk_result in chunk_results 
            if chunk_result['similar_bgb_sections']
        ]
        
        if not chunks_with_bgb:
            logger.info("No chunks with similar BGB sections found")
            found_clauses = []
        else:
            # Analyze all chunks in one batch request
            analysis_result = await self._analyze_clauses_batch(chunks_with_bgb)
            found_clauses = analysis_result.get('found_clauses', [])
        
        logger.info(f"Pipeline complete. Found {len(found_clauses)} clauses")
        
        # Format output as string for Masumi - Markdown-friendly formatting
        if found_clauses:
            output_lines = []
            output_lines.append("# Contract Analysis Report")
            output_lines.append("")
            output_lines.append(f"**Analysis completed.** Found **{len(found_clauses)} problematic clause(s)** that violate German tenant protections.")
            output_lines.append("")
            output_lines.append("---")
            output_lines.append("")
            
            for i, clause in enumerate(found_clauses, 1):
                output_lines.append(f"## Issue #{i}")
                output_lines.append("")
                output_lines.append("### Contract Clause")
                output_lines.append("")
                # Format contract content as blockquote for better readability
                contract_content = clause.get('contract_content', 'N/A').strip()
                # Use blockquote formatting for contract content
                if contract_content:
                    # Split into lines and add blockquote marker
                    content_lines = contract_content.split('\n')
                    for line in content_lines:
                        if line.strip():
                            output_lines.append(f"> {line.strip()}")
                        else:
                            output_lines.append(">")
                else:
                    output_lines.append("> N/A")
                output_lines.append("")
                output_lines.append("### Legal Analysis")
                output_lines.append("")
                analysis = clause.get('analysis', 'N/A').strip()
                # Format analysis as regular markdown text
                if analysis:
                    output_lines.append(analysis)
                else:
                    output_lines.append("N/A")
                output_lines.append("")
                if i < len(found_clauses):
                    output_lines.append("---")
                    output_lines.append("")
            
            output_string = "\n".join(output_lines).strip()
        else:
            output_string = (
                "# Contract Analysis Report\n\n"
                "**Analysis completed.** No problematic clauses found.\n\n"
                "The contract appears to comply with German rental law (BGB) and does not contain "
                "any clauses that violate mandatory tenant protections, are unfair under BGB §307, "
                "or are exploitative in nature."
            )
        
        # Return both string output and data for caching
        return {
            'output': output_string,
            'chunks': chunks,
            'embeddings': [emb.embedding for emb in embeddings],
            'openai_result': found_clauses
        }
    
    def _extract_text_from_ocr(self, ocr_result: Any) -> str:
        """
        Extract text from Mistral OCR result.
        
        Mistral OCR response structure:
        - ocr_result.pages: List of OCRPageObject
        - Each OCRPageObject has .markdown attribute with the extracted text
        
        Args:
            ocr_result: OCR response from Mistral (OCRResponse object)
            
        Returns:
            Extracted text from all pages
        """
        text_parts = []
        
        # Mistral OCR returns pages with markdown attribute
        pages = None
        if hasattr(ocr_result, 'pages'):
            pages = ocr_result.pages
        elif isinstance(ocr_result, dict) and 'pages' in ocr_result:
            pages = ocr_result['pages']
        
        if pages:
            for page in pages:
                page_text = None
                # Mistral OCR uses 'markdown' attribute (not 'text')
                if hasattr(page, 'markdown'):
                    page_text = page.markdown
                elif hasattr(page, 'text'):
                    page_text = page.text
                elif hasattr(page, 'content'):
                    page_text = page.content
                elif isinstance(page, dict):
                    page_text = page.get('markdown') or page.get('text') or page.get('content')
                
                if page_text:
                    text_parts.append(str(page_text))
        
        # Fallback: Try direct attributes on ocr_result
        if not text_parts:
            if hasattr(ocr_result, 'markdown') and ocr_result.markdown:
                return str(ocr_result.markdown).strip()
            elif hasattr(ocr_result, 'text') and ocr_result.text:
                return str(ocr_result.text).strip()
            elif hasattr(ocr_result, 'content') and ocr_result.content:
                return str(ocr_result.content).strip()
            elif isinstance(ocr_result, dict):
                return str(ocr_result.get('markdown') or ocr_result.get('text') or ocr_result.get('content', '')).strip()
        
        result = '\n\n'.join(text_parts).strip()
        
        if not result:
            logger.error(f"Failed to extract text from Mistral OCR result")
            logger.error(f"Type: {type(ocr_result)}")
            if hasattr(ocr_result, '__dict__'):
                logger.error(f"Attributes: {list(ocr_result.__dict__.keys())}")
        
        return result
    
    async def _analyze_clauses_batch(
        self,
        chunks_with_bgb: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use OpenAI chat to analyze all chunks in one batch request.
        
        Args:
            chunks_with_bgb: List of chunk results with similar BGB sections
            
        Returns:
            Batch analysis result with found_clauses list
        """
        # Build comprehensive prompt with all chunks and their BGB sections
        chunks_text = []
        for i, chunk_result in enumerate(chunks_with_bgb, 1):
            chunk_text = chunk_result['chunk_text']
            heading = chunk_result.get('chunk_heading', f'Section {i}')
            similar_bgb = chunk_result['similar_bgb_sections']
            
            # Format BGB sections for this chunk
            bgb_sections_text = "\n".join([
                f"  - BGB {section.get('section_number', 'N/A')}: {section.get('contextual_text', '')[:300]}..."
                for section in similar_bgb[:3]  # Top 3 per chunk
            ])
            
            chunks_text.append(f"""
Chunk {i} - {heading}:
Contract Text:
{chunk_text}

Relevant BGB Sections:
{bgb_sections_text}
""")
        
        all_chunks_text = "\n" + "="*80 + "\n".join(chunks_text)
        
        system_message = (
            "You are a legal expert in German rental contract law (BGB) specializing in tenant protection. "
            "Your task is to identify ONLY genuinely problematic clauses that violate German tenant protections or are unfair/illegal. "
            "\n\n"
            "IMPORTANT CRITERIA - Only flag clauses that are:\n"
            "1. ILLEGAL: Violate mandatory BGB provisions (e.g., deposits >3 months, waivers of inalienable rights, void clauses under BGB §134)\n"
            "2. UNFAIR: Exploitative terms that disadvantage tenants unreasonably (BGB §307)\n"
            "3. SCAM-LIKE: Clearly designed to extract money or rights from tenants through deception\n"
            "\n"
            "DO NOT flag:\n"
            "- Standard legal clauses that comply with BGB\n"
            "- Reasonable restrictions (e.g., normal pet policies, standard maintenance responsibilities)\n"
            "- Standard rental terms (rent amount, duration, notice periods within legal limits)\n"
            "- Clauses that are merely unfavorable but still legal\n"
            "- Standard boilerplate language\n"
            "\n"
            "Be conservative: Only flag clauses that are clearly problematic under German law. "
            "When in doubt, do not flag the clause."
        )
        
        user_prompt = f"""Analyze these contract chunks against the relevant BGB sections provided:

{all_chunks_text}

For each chunk, carefully evaluate whether it contains genuinely problematic clauses that violate German tenant protections.

ONLY include clauses that meet these strict criteria:
- The clause clearly violates a mandatory BGB provision (e.g., illegal deposit amounts, waivers of inalienable rights)
- The clause is exploitative and unfair under BGB §307 (unfair contract terms)
- The clause is designed to circumvent tenant protections in a scam-like manner

For each problematic clause found, provide:
1. Contract content: The exact text from the contract that is problematic
2. Analysis: A clear, professional explanation that includes:
   - Which specific BGB provision(s) are violated
   - Why the clause is illegal/unfair/exploitative
   - The legal basis for why this clause would be void or unenforceable
   - What the correct legal standard should be

If a chunk contains only standard, legal clauses that comply with BGB, do NOT include it in your response.

Return an empty array if no genuinely problematic clauses are found."""
        
        try:
            completion = await self.openai_service.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ],
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=None,
                response_model=BatchClauseAnalysisResponse
            )
            
            # Extract structured response from OpenAI
            try:
                response_text = completion.choices[0].message.content
                if not response_text:
                    raise ValueError("Empty response from OpenAI")
                
                # Parse JSON (might be wrapped in markdown code blocks)
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]  # Remove ```json
                if response_text.startswith("```"):
                    response_text = response_text[3:]  # Remove ```
                if response_text.endswith("```"):
                    response_text = response_text[:-3]  # Remove closing ```
                response_text = response_text.strip()
                
                # Parse and validate with Pydantic model
                parsed_json = json.loads(response_text)
                response = BatchClauseAnalysisResponse(**parsed_json)
                
                return {
                    'found_clauses': [
                        {
                            'contract_content': clause.contract_content,
                            'analysis': clause.analysis
                        }
                        for clause in response.found_clauses
                    ]
                }
            except (json.JSONDecodeError, ValueError, Exception) as e:
                logger.warning(f"Failed to parse structured output: {e}. Falling back to empty result.")
                return {'found_clauses': []}
        except Exception as e:
            logger.error(f"Error analyzing clauses in batch: {str(e)}")
            return {'found_clauses': []}

