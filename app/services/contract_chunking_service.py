"""
Contract Chunking Service
Chunks German contracts by headings following German contract structure.
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ContractChunkingService:
    """
    Service for chunking German contracts by headings.
    
    German contracts typically have:
    - Main sections (numbered: 1., 2., 3.)
    - Subsections (numbered: 1.1, 1.2, 2.1)
    - Paragraphs (numbered: (1), (2), (3))
    - Headings in various formats
    """
    
    # Patterns for German contract headings
    HEADING_PATTERNS = [
        # Main sections: "1.", "2.", "§ 1", "Artikel 1"
        re.compile(r'^(\d+)\.\s+(.+)$', re.MULTILINE),
        re.compile(r'^§\s*(\d+)\s+(.+)$', re.MULTILINE),
        re.compile(r'^Artikel\s+(\d+)\s+(.+)$', re.MULTILINE),
        # Subsections: "1.1", "2.3", etc.
        re.compile(r'^(\d+\.\d+)\s+(.+)$', re.MULTILINE),
        # Paragraphs: "(1)", "(2)", etc.
        re.compile(r'^\((\d+)\)\s+(.+)$', re.MULTILINE),
        # Common German headings: "Abschnitt", "Titel", "Kapitel"
        re.compile(r'^(Abschnitt|Titel|Kapitel)\s+([IVX\d]+)\s*[:\-]?\s*(.+)$', re.MULTILINE),
        # Bold/strong headings (markdown or HTML)
        re.compile(r'^(?:#+\s*|(?:\*\*|__))(.+?)(?:\*\*|__)?$', re.MULTILINE),
    ]
    
    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 2000):
        """
        Initialize chunking service.
        
        Args:
            min_chunk_size: Minimum characters per chunk
            max_chunk_size: Maximum characters per chunk
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
    
    def chunk_by_headings(self, text: str) -> List[Dict[str, Any]]:
        """
        Chunk text by headings following German contract structure.
        
        Args:
            text: Full contract text from OCR
            
        Returns:
            List of chunks with metadata
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_heading = None
        current_section = None
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if line is a heading
            heading_match = self._is_heading(line)
            
            if heading_match:
                # Save previous chunk if it exists
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk).strip()
                    if len(chunk_text) >= self.min_chunk_size:
                        chunks.append({
                            'text': chunk_text,
                            'heading': current_heading,
                            'section': current_section,
                            'start_line': len(chunks),
                            'char_count': len(chunk_text)
                        })
                
                # Start new chunk
                current_heading = heading_match.get('heading', line)
                current_section = heading_match.get('section', None)
                current_chunk = [line]
            else:
                # Add line to current chunk
                if line:  # Skip empty lines
                    current_chunk.append(line)
                    
                    # If chunk is getting too large, split it
                    chunk_text = '\n'.join(current_chunk).strip()
                    if len(chunk_text) > self.max_chunk_size:
                        # Save current chunk
                        chunks.append({
                            'text': chunk_text[:self.max_chunk_size],
                            'heading': current_heading,
                            'section': current_section,
                            'start_line': len(chunks),
                            'char_count': self.max_chunk_size
                        })
                        # Start new chunk with remaining text
                        remaining = chunk_text[self.max_chunk_size:]
                        current_chunk = [remaining] if remaining else []
            
            i += 1
        
        # Save last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append({
                    'text': chunk_text,
                    'heading': current_heading,
                    'section': current_section,
                    'start_line': len(chunks),
                    'char_count': len(chunk_text)
                })
        
        # If no chunks were created (no headings found), create one large chunk
        if not chunks:
            chunks.append({
                'text': text.strip(),
                'heading': None,
                'section': None,
                'start_line': 0,
                'char_count': len(text.strip())
            })
        
        logger.info(f"Created {len(chunks)} chunks from contract text")
        return chunks
    
    def _is_heading(self, line: str) -> Dict[str, Any] | None:
        """
        Check if a line is a heading and extract metadata.
        
        Args:
            line: Line to check
            
        Returns:
            Dict with heading info or None
        """
        if not line or len(line) < 3:
            return None
        
        # Check against patterns
        for pattern in self.HEADING_PATTERNS:
            match = pattern.match(line)
            if match:
                groups = match.groups()
                return {
                    'heading': line,
                    'section': groups[0] if groups else None,
                    'full_match': match.group(0)
                }
        
        # Check for all-caps short lines (common in contracts)
        if line.isupper() and len(line) < 100 and not line.endswith('.'):
            return {
                'heading': line,
                'section': None,
                'full_match': line
            }
        
        return None

