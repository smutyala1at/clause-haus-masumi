"""
Job service for processing jobs
"""

import logging
from typing import Dict, Any, Optional
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.schemas.job import StartJobResponse, StatusResponse
from app.services.contract_analysis_pipeline import ContractAnalysisPipeline
from app.db.models.contract_analysis_cache import ContractAnalysisCache
from app.db.models.job import Job
from app.utils.checksum import calculate_pdf_checksum

logger = logging.getLogger(__name__)


class JobService:
    """Service for processing jobs"""
    
    async def create_job(
        self, 
        input_data: Any, 
        identifier_from_purchaser: str = None,
        db: Optional[AsyncSession] = None
    ) -> StartJobResponse:
        """
        Create a new job and return its ID (MIP-003 compliant)
        
        Args:
            input_data: List of key-value pairs for the job (from Pydantic model)
            identifier_from_purchaser: Optional identifier from purchaser
            db: Database session (required)
            
        Returns:
            StartJobResponse with job_id and payment_id
        """
        if not db:
            raise ValueError("Database session is required")
        
        job_id = str(uuid4())
        # Generate payment_id (same as job_id for simplicity, or use identifier_from_purchaser if provided)
        payment_id = identifier_from_purchaser if identifier_from_purchaser else job_id
        
        # Convert input_data list to dictionary for easier access
        input_dict = {item.key: item.value for item in input_data}
        
        # Extract PDF to check cache before creating job
        pdf_value = None
        for key, value in input_dict.items():
            if key.lower() in ["document", "pdf"]:
                pdf_value = value
                break
        
        # Fallback: find any PDF-like value
        if not pdf_value:
            for key, value in input_dict.items():
                if isinstance(value, str) and (
                    value.startswith("data:application/pdf") or
                    value.startswith("http") or
                    len(value) > 1000
                ):
                    pdf_value = value
                    break
        
        # Check cache before creating job (optimization)
        cache_entry = None
        if pdf_value:
            checksum = calculate_pdf_checksum(pdf_value)
            cached_result = await db.execute(
                select(ContractAnalysisCache).where(ContractAnalysisCache.id == checksum)
            )
            cache_entry = cached_result.scalar_one_or_none()
        
        # Create job in database
        # If cache exists, set status to "completed" immediately
        initial_status = "completed" if cache_entry else "processing"
        initial_result = cache_entry.result_string if cache_entry else None
        
        job = Job(
            job_id=job_id,
            payment_id=payment_id,
            identifier_from_purchaser=identifier_from_purchaser,
            input_data=input_dict,
            status=initial_status,
            result=initial_result,
            error=None
        )
        db.add(job)
        
        # Update cache last_accessed_at if using cached result
        if cache_entry:
            cache_entry.last_accessed_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        if cache_entry:
            logger.info(f"Created job {job_id} with cached result (checksum: {checksum[:16]}...)")
        else:
            logger.info(f"Created job {job_id} with payment_id {payment_id}")
        
        return StartJobResponse(job_id=job_id, payment_id=payment_id)
    
    async def process_job(self, job_id: str, db: Optional[AsyncSession] = None) -> None:
        """
        Process the job - analyze contract PDF against BGB laws.
        
        Args:
            job_id: Job identifier
            db: Database session (optional, will create new session if not provided)
        """
        from app.db.base import get_session_factory
        
        # Create new session if not provided (for background tasks)
        if not db:
            session_factory = get_session_factory()
            async with session_factory() as session:
                try:
                    await self._process_job_with_session(job_id, session)
                finally:
                    await session.close()
        else:
            await self._process_job_with_session(job_id, db)
    
    async def _process_job_with_session(self, job_id: str, db: AsyncSession) -> None:
        """
        Internal method to process job with a database session.
        
        Args:
            job_id: Job identifier
            db: Database session
        """
        try:
            # Get job from database
            result = await db.execute(select(Job).where(Job.job_id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            input_data = job.input_data
            
            logger.info(f"Processing job {job_id}")
            
            # Extract PDF from input_data
            pdf_value = None
            for key, value in input_data.items():
                if key.lower() in ["document", "pdf"]:
                    pdf_value = value
                    break
            
            # Fallback: find any PDF-like value
            if not pdf_value:
                for key, value in input_data.items():
                    if isinstance(value, str) and (
                        value.startswith("data:application/pdf") or
                        value.startswith("http") or
                        len(value) > 1000
                    ):
                        pdf_value = value
                        break
            
            if not pdf_value:
                raise ValueError("No PDF found in input_data. Expected 'document' or 'pdf' key with base64 or URL value.")
            
            # Calculate checksum for caching
            checksum = calculate_pdf_checksum(pdf_value)
            
            # Check cache first (in case job was created before cache check)
            cached_result = await db.execute(
                select(ContractAnalysisCache).where(ContractAnalysisCache.id == checksum)
            )
            cache_entry = cached_result.scalar_one_or_none()
            
            if cache_entry:
                logger.info(f"Job {job_id}: Using cached result for checksum {checksum[:16]}...")
                job.status = "completed"
                job.result = cache_entry.result_string
                # Update last_accessed_at
                cache_entry.last_accessed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"Job {job_id} completed from cache")
                return
            
            # Process contract analysis (not in cache)
            logger.info(f"Job {job_id}: Processing new PDF (checksum: {checksum[:16]}...)")
            pipeline = ContractAnalysisPipeline()
            result = await pipeline.process_contract(db=db, pdf_input=pdf_value)
            
            output_string = result['output']
            job.status = "completed"
            job.result = output_string  # MIP-003: result must be a string
            await db.commit()  # Commit job status update
            
            # Store in cache (only if not already exists - race condition protection)
            if db:
                try:
                    # Check again in case another job just cached it
                    existing = await db.execute(
                        select(ContractAnalysisCache).where(ContractAnalysisCache.id == checksum)
                    )
                    if existing.scalar_one_or_none():
                        logger.info(f"Job {job_id}: Cache entry already exists (race condition), skipping insert")
                    else:
                        cache_entry = ContractAnalysisCache(
                            id=checksum,
                            job_id=job_id,  # Store the first job that processed this PDF
                            chunks=result['chunks'],
                            chunk_embeddings=result['embeddings'],
                            openai_result=result['openai_result'],
                            result_string=output_string
                        )
                        db.add(cache_entry)
                        await db.commit()
                        logger.info(f"Job {job_id}: Cached result for future use")
                except Exception as e:
                    logger.warning(f"Job {job_id}: Failed to cache result: {e}")
                    await db.rollback()
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            # Update job status in database
            try:
                result = await db.execute(select(Job).where(Job.job_id == job_id))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    await db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update job status in database: {db_error}")
                await db.rollback()
    
    async def get_job(self, job_id: str, db: Optional[AsyncSession] = None) -> Job:
        """
        Get job by ID from database
        
        Args:
            job_id: Job identifier
            db: Database session (required)
            
        Returns:
            Job database model
            
        Raises:
            ValueError: If job not found
        """
        if not db:
            raise ValueError("Database session is required")
        
        result = await db.execute(select(Job).where(Job.job_id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        return job
    
    async def get_job_status(self, job_id: str, db: Optional[AsyncSession] = None) -> StatusResponse:
        """
        Get job status (MIP-003 compliant - result must be a string)
        
        Args:
            job_id: Job identifier
            db: Database session (required)
            
        Returns:
            Job status response
            
        Raises:
            ValueError: If job not found
        """
        if not db:
            raise ValueError("Database session is required")
        
        job = await self.get_job(job_id, db)
        
        # MIP-003: result must be a string
        result_str = job.result if isinstance(job.result, str) else None
        
        return StatusResponse(
            job_id=job_id,
            status=job.status,
            result=result_str,
            error=job.error
        )
