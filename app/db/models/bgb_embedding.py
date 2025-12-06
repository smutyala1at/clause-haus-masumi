"""
BGB Embedding database model
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class BGBEmbedding(Base):
    """
    Model for storing BGB section embeddings with metadata.
    
    Each row represents a German BGB section with its embedding vector.
    """
    __tablename__ = "bgb_embeddings"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Section identification
    section_number = Column(String(20), nullable=False, index=True, unique=True)
    
    # Section metadata
    book = Column(Integer, nullable=True, index=True)
    book_title = Column(String(255), nullable=True)
    division = Column(Integer, nullable=True, index=True)
    division_title = Column(String(255), nullable=True)
    section_title = Column(Integer, nullable=True)
    section_title_text = Column(String(255), nullable=True)
    
    # Section content
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    
    # Contextual text (formatted for embedding)
    contextual_text = Column(Text, nullable=False)
    
    # Embedding vector (1536 dimensions for text-embedding-3-small)
    embedding = Column(Vector(1536), nullable=False)
    
    # Additional metadata as JSON
    additional_metadata = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_bgb_embeddings_book_division', 'book', 'division'),
        # Note: section_number doesn't need explicit Index here because 
        # unique=True on the column already creates a unique index
    )
    
    def __repr__(self):
        return f"<BGBEmbedding(section_number='{self.section_number}', book={self.book})>"

