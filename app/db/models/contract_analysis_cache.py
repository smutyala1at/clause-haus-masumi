"""
Contract Analysis Cache database model
Stores processed contract analysis results with checksum for deduplication
"""

from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class ContractAnalysisCache(Base):
    """
    Model for caching contract analysis results.
    
    Stores chunks, embeddings, and results to avoid reprocessing the same PDF.
    """
    __tablename__ = "contract_analysis_cache"
    
    # Primary key
    id = Column(String(64), primary_key=True)  # Using checksum as primary key
    
    # Job tracking
    job_id = Column(String(36), nullable=False, index=True)  # UUID
    
    # Cached data
    chunks = Column(JSONB, nullable=False)  # List of chunk dicts with text and heading
    chunk_embeddings = Column(JSONB, nullable=False)  # List of embeddings (as lists)
    openai_result = Column(JSONB, nullable=False)  # Structured result from OpenAI
    result_string = Column(Text, nullable=False)  # Final string output
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_contract_cache_job_id', 'job_id'),
        Index('idx_contract_cache_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ContractAnalysisCache(checksum='{self.id[:16]}...', job_id='{self.job_id}')>"

