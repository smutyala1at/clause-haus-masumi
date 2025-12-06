"""
BGB Embedding Service
Handles embedding generation and storage for BGB sections with checksum-based deduplication.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.checksum import calculate_checksum
from app.db.models.bgb_embedding import BGBEmbedding
from app.services.openai_service import OpenAIService, OpenAIError

logger = logging.getLogger(__name__)


class BGBEmbeddingService:
    """Service for generating and storing BGB section embeddings"""
    
    def __init__(self):
        self.openai_service = OpenAIService()
    
    def _format_contextual_text(self, section: Dict) -> str:
        """
        Format section with metadata for better embeddings.
        Uses German content if available, falls back to English if not.
        
        Format:
        Buch {book}: {book_title}
        Abschnitt {division}: {division_title}
        §{number}: {title}
        {content}
        
        Note: Only includes Title (section_title) if it exists in the structure.
        """
        german = section.get('german') or {}
        english = section.get('english') or {}
        
        # Prefer German, fall back to English
        source = german if german else english
        if not source:
            return ""
        
        parts = []
        
        # Book - use German if available, otherwise English
        book = source.get('book')
        book_title = source.get('book_title')
        if book and book_title:
            if german and german.get('book_title'):
                parts.append(f"Buch {book}: {book_title}")
            else:
                parts.append(f"Book {book}: {book_title}")
        
        # Division - use German if available, otherwise English
        division = source.get('division')
        division_title = source.get('division_title')
        if division and division_title:
            if german and german.get('division_title'):
                parts.append(f"Abschnitt {division}: {division_title}")
            else:
                parts.append(f"Division {division}: {division_title}")
        
        # Title (section_title) - only if it exists
        section_title = source.get('section_title')
        section_title_text = source.get('section_title_text')
        if section_title and section_title_text:
            if german and german.get('section_title_text'):
                parts.append(f"Titel {section_title}: {section_title_text}")
            else:
                parts.append(f"Title {section_title}: {section_title_text}")
        
        # Section number and title
        section_num = section.get('number', '')
        title = source.get('title', '')
        if section_num:
            parts.append(f"§{section_num}: {title}")
        
        # Content
        content = source.get('content', '')
        if content:
            parts.append(content)
        
        return '\n'.join(parts)
    
    
    async def _get_existing_embeddings(
        self, 
        db: AsyncSession, 
        section_numbers: List[str]
    ) -> Dict[str, BGBEmbedding]:
        """Get existing embeddings for section numbers"""
        result = await db.execute(
            select(BGBEmbedding).where(
                BGBEmbedding.section_number.in_(section_numbers)
            )
        )
        embeddings = result.scalars().all()
        return {emb.section_number: emb for emb in embeddings}
    
    async def _check_checksums(
        self,
        db: AsyncSession,
        sections_to_embed: List[Dict],
        existing_embeddings: Dict[str, BGBEmbedding]
    ) -> Tuple[List[Dict], List[str], int]:
        """
        Check which sections need embedding based on checksums.
        
        Returns:
            Tuple of (sections_to_embed, section_numbers_to_skip, invalid_count)
        """
        sections_needing_embedding = []
        sections_to_skip = []
        invalid_count = 0
        
        for section in sections_to_embed:
            section_number = section.get('number')
            if not section_number:
                logger.warning(f"Skipping section: missing 'number' field. Section data: {section.get('german', {}).get('title', 'unknown')[:50]}")
                invalid_count += 1
                continue
            
            # Format contextual text (uses German if available, falls back to English)
            contextual_text = self._format_contextual_text(section)
            if not contextual_text:
                logger.warning(f"Skipping section {section_number}: no German or English content")
                invalid_count += 1
                continue
            
            # Calculate checksum
            checksum = calculate_checksum(contextual_text)
            
            # Check if we already have this embedding with same checksum
            existing = existing_embeddings.get(section_number)
            if existing:
                # Check if checksum matches (content hasn't changed)
                # We'll store checksum in additional_metadata
                existing_checksum = None
                if existing.additional_metadata and isinstance(existing.additional_metadata, dict):
                    existing_checksum = existing.additional_metadata.get('content_checksum')
                
                if existing_checksum == checksum:
                    logger.debug(f"Section {section_number} unchanged, skipping embedding")
                    sections_to_skip.append(section_number)
                    continue
            
            # Need to embed this section
            sections_needing_embedding.append({
                'section': section,
                'section_number': section_number,
                'contextual_text': contextual_text,
                'checksum': checksum
            })
        
        return sections_needing_embedding, sections_to_skip, invalid_count
    
    async def embed_sections(
        self,
        db: AsyncSession,
        sections: List[Dict],
        batch_size: int = 100
    ) -> Dict:
        """
        Embed BGB sections and store in database.
        Skips sections that haven't changed based on checksums.
        
        Args:
            db: Database session
            sections: List of section dictionaries from bgb_mapped.json
            batch_size: Number of sections to embed per batch
            
        Returns:
            Dictionary with statistics about the embedding process
        """
        if not sections:
            return {
                'total_sections': 0,
                'embedded': 0,
                'skipped': 0,
                'errors': 0
            }
        
        # Get section numbers
        section_numbers = [s.get('number') for s in sections if s.get('number')]
        
        # Get existing embeddings
        logger.info(f"Checking {len(section_numbers)} sections for existing embeddings...")
        existing_embeddings = await self._get_existing_embeddings(db, section_numbers)
        logger.info(f"Found {len(existing_embeddings)} existing embeddings")
        
        # Check which sections need embedding
        sections_to_embed, sections_to_skip, invalid_count = await self._check_checksums(
            db, sections, existing_embeddings
        )
        
        logger.info(f"Sections to embed: {len(sections_to_embed)}, to skip: {len(sections_to_skip)}, invalid: {invalid_count}")
        
        if not sections_to_embed:
            return {
                'total_sections': len(sections),
                'embedded': 0,
                'skipped': len(sections_to_skip),
                'invalid': invalid_count,
                'errors': 0,
                'message': 'All sections already embedded and up-to-date' if invalid_count == 0 else f'All valid sections embedded. {invalid_count} sections skipped due to missing data.'
            }
        
        # Extract contextual texts for embedding
        contextual_texts = [item['contextual_text'] for item in sections_to_embed]
        
        # Generate embeddings in batches
        logger.info(f"Generating embeddings for {len(contextual_texts)} sections...")
        all_embeddings = []
        errors = 0
        
        try:
            embeddings = await self.openai_service.create_embeddings(
                texts=contextual_texts,
                model="text-embedding-3-small",
                batch_size=batch_size
            )
            all_embeddings = embeddings
        except OpenAIError as e:
            logger.error(f"Error generating embeddings: {e.message}")
            raise
        
        # Store embeddings in database
        logger.info(f"Storing {len(all_embeddings)} embeddings in database...")
        embedded_count = 0
        
        for i, item in enumerate(sections_to_embed):
            try:
                section = item['section']
                section_number = item['section_number']
                contextual_text = item['contextual_text']
                checksum = item['checksum']
                embedding_vector = all_embeddings[i].embedding
                
                # Prefer German, fall back to English
                german = section.get('german') or {}
                english = section.get('english') or {}
                source = german if german else english
                
                # Ensure we have at least title or content (required by model)
                # Use contextual_text as fallback if title/content are missing
                title = source.get('title') or f"Section {section_number}"
                content = source.get('content') or contextual_text[:500] if contextual_text else ''
                
                if not title and not content:
                    logger.warning(f"Skipping section {section_number}: no title or content available")
                    errors += 1
                    continue
                
                # Check if record exists (update) or create new
                existing = existing_embeddings.get(section_number)
                
                if existing:
                    # Update existing record
                    existing.embedding = embedding_vector
                    existing.contextual_text = contextual_text
                    existing.title = title
                    existing.content = content
                    existing.book = source.get('book')
                    existing.book_title = source.get('book_title')
                    existing.division = source.get('division')
                    existing.division_title = source.get('division_title')
                    existing.section_title = source.get('section_title')
                    existing.section_title_text = source.get('section_title_text')
                    existing.additional_metadata = {
                        'content_checksum': checksum,
                        'is_repealed': source.get('is_repealed', False),
                        'language_used': 'german' if german else 'english'
                    }
                else:
                    # Create new record
                    new_embedding = BGBEmbedding(
                        section_number=section_number,
                        title=title,
                        content=content,
                        contextual_text=contextual_text,
                        embedding=embedding_vector,
                        book=source.get('book'),
                        book_title=source.get('book_title'),
                        division=source.get('division'),
                        division_title=source.get('division_title'),
                        section_title=source.get('section_title'),
                        section_title_text=source.get('section_title_text'),
                        additional_metadata={
                            'content_checksum': checksum,
                            'is_repealed': source.get('is_repealed', False),
                            'language_used': 'german' if german else 'english'
                        }
                    )
                    db.add(new_embedding)
                
                embedded_count += 1
                
            except Exception as e:
                logger.error(f"Error storing embedding for section {item.get('section_number')}: {e}")
                errors += 1
        
        # Commit all changes
        await db.commit()
        
        logger.info(f"Successfully embedded {embedded_count} sections, skipped {len(sections_to_skip)}, invalid: {invalid_count}, errors: {errors}")
        
        return {
            'total_sections': len(sections),
            'embedded': embedded_count,
            'skipped': len(sections_to_skip),
            'invalid': invalid_count,
            'errors': errors
        }
    
    def load_bgb_mapped_json(self, file_path: Optional[Path] = None) -> Dict:
        """
        Load bgb_mapped.json file.
        
        Args:
            file_path: Optional path to JSON file. If None, uses default location.
            
        Returns:
            Dictionary with metadata and sections
        """
        if file_path is None:
            file_path = Path(__file__).parent.parent / "data" / "bgb_mapped.json"
        
        if not file_path.exists():
            raise FileNotFoundError(f"BGB mapped JSON file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data

