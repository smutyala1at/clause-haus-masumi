"""
BGB Section Mapper
Analyzes German Civil Code (BGB) files in English and German,
extracts all sections, and creates a comprehensive JSON mapping.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel
from pathlib import Path

logger = logging.getLogger(__name__)


class SectionContent(BaseModel):
    """Content for a single language version of a section."""
    title: str
    content: str
    book: Optional[int] = None
    book_title: Optional[str] = None
    division: Optional[int] = None
    division_title: Optional[str] = None
    section_title: Optional[int] = None
    section_title_text: Optional[str] = None
    exists: bool = True
    is_repealed: bool = False


class BGBSection(BaseModel):
    """Complete BGB section with both languages."""
    number: str
    english: Optional[SectionContent] = None
    german: Optional[SectionContent] = None


class BGBParser:
    """Parser for BGB text files."""
    
    # Patterns for section identification
    ENGLISH_SECTION_PATTERN = re.compile(r'^Section (\d+[a-z]?)$', re.IGNORECASE)
    GERMAN_SECTION_PATTERN = re.compile(r'^§ (\d+[a-z]?)$')
    
    # Patterns for structure identification
    BOOK_PATTERN_EN = re.compile(r'^Book (\d+)$', re.IGNORECASE)
    BOOK_PATTERN_DE = re.compile(r'^Buch (\d+)$')
    DIVISION_PATTERN_EN = re.compile(r'^Division (\d+)$', re.IGNORECASE)
    DIVISION_PATTERN_DE = re.compile(r'^Abschnitt (\d+)$')
    TITLE_PATTERN_EN = re.compile(r'^Title (\d+)$', re.IGNORECASE)
    TITLE_PATTERN_DE = re.compile(r'^Titel (\d+)$')
    
    # Repealed section patterns
    REPEALED_EN = re.compile(r'\(repealed\)', re.IGNORECASE)
    REPEALED_DE = re.compile(r'\(weggefallen\)', re.IGNORECASE)
    
    def __init__(self, english_path: str = None, german_path: str = None):
        self.english_path = Path(english_path) if english_path else None
        self.german_path = Path(german_path) if german_path else None
        self.sections: Dict[str, BGBSection] = {}
    
    def parse_file(self, file_path: Path, is_german: bool = False) -> Dict[str, SectionContent]:
        """Parse a BGB file and extract all sections."""
        sections = {}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Current context
        current_book = None
        current_book_title = None
        current_division = None
        current_division_title = None
        current_section_num = None
        current_section_title = None
        
        # Section detection
        current_section = None
        current_content = []
        in_section = False
        
        section_pattern = self.GERMAN_SECTION_PATTERN if is_german else self.ENGLISH_SECTION_PATTERN
        book_pattern = self.BOOK_PATTERN_DE if is_german else self.BOOK_PATTERN_EN
        division_pattern = self.DIVISION_PATTERN_DE if is_german else self.DIVISION_PATTERN_EN
        title_pattern = self.TITLE_PATTERN_DE if is_german else self.TITLE_PATTERN_EN
        repealed_pattern = self.REPEALED_DE if is_german else self.REPEALED_EN
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Track structural elements
            book_match = book_pattern.match(line)
            if book_match:
                current_book = int(book_match.group(1))
                # Next non-empty line is book title
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line:
                        current_book_title = next_line
                        break
                continue
            
            division_match = division_pattern.match(line)
            if division_match:
                current_division = int(division_match.group(1))
                # Next non-empty line is division title
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line:
                        current_division_title = next_line
                        break
                continue
            
            title_match = title_pattern.match(line)
            if title_match:
                current_section_num = int(title_match.group(1))
                # Next non-empty line is section title
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line:
                        current_section_title = next_line
                        break
                continue
            
            # Check for section start
            section_match = section_pattern.match(line)
            if section_match:
                # Save previous section if exists
                if current_section and in_section:
                    is_repealed = any(repealed_pattern.search(c) for c in current_content)
                    # Join content list into single string
                    joined_content = ' '.join(current_content)
                    
                    sections[current_section] = SectionContent(
                        title=section_title,
                        content=joined_content,
                        book=current_book,
                        book_title=current_book_title,
                        division=current_division,
                        division_title=current_division_title,
                        section_title=current_section_num,
                        section_title_text=current_section_title,
                        is_repealed=is_repealed
                    )
                
                # Start new section
                current_section = section_match.group(1)
                section_title = ""
                current_content = []
                in_section = True
                
                # Next non-empty line is section title
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line:
                        section_title = next_line
                        break
                continue
            
            # Collect section content
            if in_section and line:
                # Skip the section title line
                if line != section_title or len(current_content) > 0:
                    current_content.append(line)
        
        # Save last section
        if current_section and in_section:
            is_repealed = any(repealed_pattern.search(c) for c in current_content)
            # Join content list into single string
            joined_content = ' '.join(current_content)
            
            sections[current_section] = SectionContent(
                title=section_title,
                content=joined_content,
                book=current_book,
                book_title=current_book_title,
                division=current_division,
                division_title=current_division_title,
                section_title=current_section_num,
                section_title_text=current_section_title,
                is_repealed=is_repealed
            )
        
        return sections
    
    def _section_sort_key(self, section_num: str) -> Tuple[int, str]:
        """Create sort key for section numbers (handles 31a, 31b, etc.)."""
        match = re.match(r'(\d+)([a-z]?)', section_num)
        if match:
            num, suffix = match.groups()
            return (int(num), suffix or '')
        return (0, section_num)
    
    def create_mapping(self, english_path: str = None, german_path: str = None) -> Dict[str, BGBSection]:
        """Create complete mapping of English and German sections."""
        eng_path = Path(english_path) if english_path else self.english_path
        ger_path = Path(german_path) if german_path else self.german_path
        
        logger.info("Parsing English BGB file...")
        english_sections = self.parse_file(eng_path, is_german=False)
        logger.info(f"Found {len(english_sections)} English sections")
        
        logger.info("Parsing German BGB file...")
        german_sections = self.parse_file(ger_path, is_german=True)
        logger.info(f"Found {len(german_sections)} German sections")
        
        # Get all unique section numbers
        all_section_numbers = set(english_sections.keys()) | set(german_sections.keys())
        logger.info(f"Total unique sections: {len(all_section_numbers)}")
        
        # Create mapping
        mapping = {}
        for section_num in sorted(all_section_numbers, key=lambda x: self._section_sort_key(x)):
            mapping[section_num] = BGBSection(
                number=section_num,
                english=english_sections.get(section_num),
                german=german_sections.get(section_num)
            )
        
        self.sections = mapping
        
        # Statistics
        both = sum(1 for s in mapping.values() if s.english and s.german)
        only_english = sum(1 for s in mapping.values() if s.english and not s.german)
        only_german = sum(1 for s in mapping.values() if s.german and not s.english)
        
        logger.info(f"Mapping Statistics:")
        logger.info(f"  Sections in both languages: {both}")
        logger.info(f"  Only in English: {only_english}")
        logger.info(f"  Only in German: {only_german}")
        
        return mapping
    
    def extract_property_law(self) -> List[Dict]:
        """Extract all Book 3 (Property Law) sections."""
        property_sections = []
        
        for section_num in sorted(self.sections.keys(), key=self._section_sort_key):
            section = self.sections[section_num]
            
            # Check if section belongs to Book 3 in either language
            is_book3 = False
            if section.english and section.english.book == 3:
                is_book3 = True
            elif section.german and section.german.book == 3:
                is_book3 = True
            
            if is_book3:
                section_data = {
                    "number": section.number,
                    "english": section.english.model_dump() if section.english else None,
                    "german": section.german.model_dump() if section.german else None
                }
                property_sections.append(section_data)
        
        return property_sections
    
    def export_to_json(self, output_path: str, pretty: bool = True) -> None:
        """Export mapping to JSON file."""
        output = {
            "metadata": {
                "total_sections": len(self.sections),
                "sections_in_both": sum(1 for s in self.sections.values() if s.english and s.german),
                "sections_only_english": sum(1 for s in self.sections.values() if s.english and not s.german),
                "sections_only_german": sum(1 for s in self.sections.values() if s.german and not s.english),
            },
            "sections": []
        }
        
        for section_num in sorted(self.sections.keys(), key=self._section_sort_key):
            section = self.sections[section_num]
            section_data = {
                "number": section.number,
                "english": section.english.model_dump() if section.english else None,
                "german": section.german.model_dump() if section.german else None
            }
            output["sections"].append(section_data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(output, f, ensure_ascii=False, indent=2)
            else:
                json.dump(output, f, ensure_ascii=False)
        
        logger.info(f"Exported {len(self.sections)} sections to {output_path}")
        logger.info(f"File size: {Path(output_path).stat().st_size / 1024 / 1024:.2f} MB")
    
    def parse_and_map(self, english_path: str, german_path: str, book_filter: int = 3) -> Dict:
        """Parse both files, create full mapping, then extract Property Law (Book 3)."""
        # Step 1: Create full mapping
        self.create_mapping(english_path, german_path)
        
        # Step 2: Extract Book 3 sections
        logger.info(f"Extracting Book {book_filter} (Property Law) sections...")
        property_sections = self.extract_property_law()
        logger.info(f"Found {len(property_sections)} Property Law sections")
        
        # Statistics
        both = sum(1 for s in property_sections if s['english'] and s['german'])
        only_english = sum(1 for s in property_sections if s['english'] and not s['german'])
        only_german = sum(1 for s in property_sections if s['german'] and not s['english'])
        repealed = sum(1 for s in property_sections if (
            (s.get('english') and s['english'].get('is_repealed')) or 
            (s.get('german') and s['german'].get('is_repealed'))
        ))
        
        return {
            'metadata': {
                'book': book_filter,
                'title_english': 'Law of property',
                'title_german': 'Sachenrecht',
                'section_range': '§§ 854-1296',
                'total_sections': len(property_sections),
                'sections_in_both': both,
                'sections_only_english': only_english,
                'sections_only_german': only_german,
                'repealed_sections': repealed
            },
            'sections': property_sections
        }
