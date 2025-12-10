"""
Job database model
Stores job information and status
"""

from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class Job(Base):
    """
    Model for storing job information and status.
    
    Stores job metadata, input data, results, and status for MIP-003 compliance.
    """
    __tablename__ = "jobs"
    
    # Primary key
    job_id = Column(String(36), primary_key=True)  # UUID
    
    # Job metadata
    payment_id = Column(String(36), nullable=True, index=True)  # Legacy payment ID
    blockchain_identifier = Column(Text, nullable=True, index=True)  # Masumi blockchain payment ID (can be very long)
    payment_status = Column(String(20), nullable=True, index=True)  # awaiting_payment, paid, pending, etc.
    identifier_from_purchaser = Column(String(255), nullable=True)
    
    # Job data
    input_data = Column(JSONB, nullable=False)  # Input data as key-value pairs
    status = Column(String(20), nullable=False, index=True)  # awaiting_payment, running, processing, completed, failed
    
    # Results
    result = Column(Text, nullable=True)  # MIP-003: result must be a string
    error = Column(Text, nullable=True)  # Error message if failed
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_jobs_status', 'status'),
        Index('idx_jobs_payment_id', 'payment_id'),
        Index('idx_jobs_blockchain_id', 'blockchain_identifier'),
        Index('idx_jobs_payment_status', 'payment_status'),
        Index('idx_jobs_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Job(job_id='{self.job_id}', status='{self.status}')>"

