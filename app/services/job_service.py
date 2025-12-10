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
from app.services.payment_service import PaymentService, MASUMI_SDK_AVAILABLE
from app.db.models.contract_analysis_cache import ContractAnalysisCache
from app.db.models.job import Job
from app.utils.checksum import calculate_pdf_checksum
from app.core.config import settings

# Import Masumi SDK if available
if MASUMI_SDK_AVAILABLE:
    from masumi.config import Config
    from masumi.payment import Payment, Amount

logger = logging.getLogger(__name__)


class JobService:
    """Service for processing jobs"""
    
    def __init__(self):
        """Initialize job service with payment service"""
        self.payment_service = PaymentService()
        # Store payment instances for monitoring (Masumi pattern)
        self.payment_instances = {}
        
        # Initialize Masumi Config if available (Masumi pattern)
        self.masumi_config = None
        if MASUMI_SDK_AVAILABLE and self.payment_service.is_configured():
            try:
                self.masumi_config = Config(
                    payment_service_url=settings.PAYMENT_SERVICE_URL,
                    payment_api_key=settings.PAYMENT_API_KEY
                )
            except Exception as e:
                logger.error(f"Failed to initialize Masumi Config: {e}")
    
    async def create_job_with_payment_and_monitoring(
        self,
        input_data: Any,
        identifier_from_purchaser: str = None,
        db: Optional[AsyncSession] = None
    ) -> StartJobResponse:
        """
        Create a new job with Masumi payment request and start monitoring (Masumi pattern).
        This matches the Masumi example exactly - creates payment, starts monitoring, returns immediately.
        
        Args:
            input_data: Dictionary of input data (MIP-003 format from Masumi, keys match input_schema field IDs)
            identifier_from_purchaser: Optional identifier from purchaser
            db: Database session (required)
            
        Returns:
            StartJobResponse with job_id, blockchainIdentifier, and payment details
        """
        if not db:
            raise ValueError("Database session is required")
        
        job_id = str(uuid4())
        
        # input_data is now a dictionary (MIP-003 format from Masumi)
        # Keys match the 'id' field from input_schema (e.g., "document_upload")
        # Masumi uploads the file and sends a URL string (not base64)
        input_dict = input_data if isinstance(input_data, dict) else {}
        
        # Extract PDF URL to check cache before creating job
        # Look for the field ID from input_schema ("document_upload") or common keys
        pdf_value = None
        for key in ["document_upload", "document", "pdf"]:
            if key in input_dict:
                pdf_value = input_dict[key]
                break
        
        # Fallback: find any URL string (Masumi sends URL strings, not base64)
        if not pdf_value:
            for key, value in input_dict.items():
                if isinstance(value, str) and (
                    value.startswith("http://") or
                    value.startswith("https://")
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
        
        # Create payment request if payment service is configured and not cached
        blockchain_identifier = None
        payment_request = None
        payment_status = "awaiting_payment"
        initial_status = "awaiting_payment"
        payment = None
        
        if cache_entry:
            # If cached, skip payment and mark as completed
            initial_status = "completed"
            payment_status = None
        elif self.payment_service.is_configured() and self.masumi_config:
            try:
                # Create Payment object directly (Masumi pattern - exact match to example)
                payment = Payment(
                    agent_identifier=settings.AGENT_IDENTIFIER,
                    config=self.masumi_config,
                    identifier_from_purchaser=identifier_from_purchaser or job_id,
                    input_data=input_dict,
                    network=settings.NETWORK
                )
                
                # Create payment request (Masumi pattern)
                logger.info("Creating payment request...")
                payment_request = await payment.create_payment_request()
                blockchain_identifier = payment_request["data"]["blockchainIdentifier"]
                payment.payment_ids.add(blockchain_identifier)
                logger.info(f"Created payment request with ID: {blockchain_identifier}")
            except Exception as e:
                logger.error(f"Failed to create payment request: {e}")
                # Continue without payment if payment service fails
                initial_status = "processing"
                payment_status = None
        
        # Create job in database
        job = Job(
            job_id=job_id,
            payment_id=identifier_from_purchaser if identifier_from_purchaser else job_id,
            blockchain_identifier=blockchain_identifier,
            payment_status=payment_status,
            identifier_from_purchaser=identifier_from_purchaser,
            input_data=input_dict,
            status=initial_status,
            result=cache_entry.result_string if cache_entry else None,
            error=None
        )
        db.add(job)
        
        # Update cache last_accessed_at if using cached result
        if cache_entry:
            cache_entry.last_accessed_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        # Define payment callback (Masumi pattern)
        async def payment_callback(blockchain_id: str):
            """Callback when payment is confirmed - executes contract analysis"""
            await self._handle_payment_status(job_id, blockchain_id)
        
        # Start payment monitoring immediately (Masumi pattern)
        if payment and blockchain_identifier and not cache_entry:
            self.payment_instances[job_id] = payment
            logger.info(f"Starting payment status monitoring for job {job_id}")
            # Start monitoring directly on payment instance (Masumi pattern)
            await payment.start_status_monitoring(payment_callback)
        
        # Build response
        response_data = {
            "status": "success",
            "job_id": job_id,
            "payment_id": identifier_from_purchaser if identifier_from_purchaser else job_id
        }
        
        if payment and blockchain_identifier:
            data = payment_request.get("data", {})
            
            # Define payment amounts (Masumi pattern - exact match to example)
            payment_amount = settings.PAYMENT_AMOUNT or "10000000"  # Default 10 ADA
            payment_unit = settings.PAYMENT_UNIT or "lovelace"  # Default lovelace
            
            amounts = []
            if MASUMI_SDK_AVAILABLE and Amount:
                amounts = [Amount(amount=payment_amount, unit=payment_unit)]
                logger.info(f"Using payment amount: {payment_amount} {payment_unit}")
            
            # Convert Amount objects to dict format for Pydantic (Masumi pattern)
            amounts_list = []
            if amounts:
                for amount in amounts:
                    amounts_list.append({
                        "amount": str(amount.amount),
                        "unit": amount.unit
                    })
            
            response_data.update({
                "blockchainIdentifier": blockchain_identifier,
                "submitResultTime": data.get("submitResultTime"),
                "unlockTime": data.get("unlockTime"),
                "externalDisputeUnlockTime": data.get("externalDisputeUnlockTime"),
                "agentIdentifier": settings.AGENT_IDENTIFIER,
                "sellerVKey": settings.SELLER_VKEY,
                "identifierFromPurchaser": identifier_from_purchaser,
                "amounts": amounts_list,
                "input_hash": payment.input_hash,
                "payByTime": data.get("payByTime")
            })
        
        if cache_entry:
            logger.info(f"Created job {job_id} with cached result")
        else:
            logger.info(f"Created job {job_id} with blockchain_identifier {blockchain_identifier}")
        
        return StartJobResponse(**response_data)
    
    async def _handle_payment_status(self, job_id: str, blockchain_identifier: str) -> None:
        """
        Handle payment confirmation - executes contract analysis (Masumi pattern).
        This is called by the payment callback when payment is confirmed.
        
        Args:
            job_id: Job identifier
            blockchain_identifier: Blockchain payment identifier
        """
        from app.db.base import get_session_factory
        
        try:
            logger.info(f"Payment {blockchain_identifier} completed for job {job_id}, executing contract analysis...")
            
            # Create new session for processing
            session_factory = get_session_factory()
            async with session_factory() as session:
                try:
                    # Update job status to running
                    result = await session.execute(select(Job).where(Job.job_id == job_id))
                    job = result.scalar_one_or_none()
                    
                    if not job:
                        logger.error(f"Job {job_id} not found when payment confirmed")
                        return
                    
                    job.status = "running"
                    job.payment_status = "paid"
                    await session.commit()
                    logger.info(f"Job {job_id} status updated to running")
                    
                    # Process the job (contract analysis)
                    await self._process_job_with_session(job_id, session)
                    
                    # Complete payment with result (Masumi pattern - call directly on payment instance)
                    if job_id in self.payment_instances:
                        payment = self.payment_instances[job_id]
                        result = await session.execute(select(Job).where(Job.job_id == job_id))
                        job = result.scalar_one_or_none()
                        
                        if job and job.result:
                            # Convert result to string (Masumi pattern)
                            result_string = job.result
                            await payment.complete_payment(blockchain_identifier, result_string)
                            logger.info(f"Payment completed for job {job_id}")
                    
                    # Stop monitoring and cleanup (Masumi pattern)
                    if job_id in self.payment_instances:
                        payment = self.payment_instances[job_id]
                        payment.stop_status_monitoring()
                        del self.payment_instances[job_id]
                        
                except Exception as e:
                    logger.error(f"Error processing job after payment confirmation: {e}")
                    # Update job status to failed
                    try:
                        result = await session.execute(select(Job).where(Job.job_id == job_id))
                        job = result.scalar_one_or_none()
                        if job:
                            job.status = "failed"
                            job.error = f"Error after payment confirmation: {str(e)}"
                            await session.commit()
                    except Exception as db_error:
                        logger.error(f"Failed to update job status: {db_error}")
                finally:
                    await session.close()
        except Exception as e:
            logger.error(f"Error in payment callback for job {job_id}: {e}")
    
    async def create_job_with_payment(
        self,
        input_data: Any,
        identifier_from_purchaser: str = None,
        db: Optional[AsyncSession] = None
    ) -> StartJobResponse:
        """
        Create a new job with Masumi payment request (MIP-003 compliant).
        
        Args:
            input_data: List of key-value pairs for the job (from Pydantic model)
            identifier_from_purchaser: Optional identifier from purchaser
            db: Database session (required)
            
        Returns:
            StartJobResponse with job_id, blockchainIdentifier, and payment details
        """
        if not db:
            raise ValueError("Database session is required")
        
        job_id = str(uuid4())
        
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
        
        # Create payment request if payment service is configured and not cached
        blockchain_identifier = None
        payment_request_data = None
        payment_status = "awaiting_payment"
        initial_status = "awaiting_payment"
        
        if cache_entry:
            # If cached, skip payment and mark as completed
            initial_status = "completed"
            payment_status = None
        elif self.payment_service.is_configured():
            try:
                # Create payment request using Masumi SDK
                payment_result = await self.payment_service.create_payment_request(
                    identifier_from_purchaser=identifier_from_purchaser or job_id,
                    input_data=input_dict
                )
                
                blockchain_identifier = payment_result["blockchain_identifier"]
                payment_request_data = payment_result["payment_request"]
                
                logger.info(f"Created payment request for job {job_id}: {blockchain_identifier}")
            except Exception as e:
                logger.error(f"Failed to create payment request: {e}")
                # Continue without payment if payment service fails
                initial_status = "processing"
                payment_status = None
        
        # Create job in database
        job = Job(
            job_id=job_id,
            payment_id=identifier_from_purchaser if identifier_from_purchaser else job_id,
            blockchain_identifier=blockchain_identifier,
            payment_status=payment_status,
            identifier_from_purchaser=identifier_from_purchaser,
            input_data=input_dict,
            status=initial_status,
            result=cache_entry.result_string if cache_entry else None,
            error=None
        )
        db.add(job)
        
        # Update cache last_accessed_at if using cached result
        if cache_entry:
            cache_entry.last_accessed_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        # Build response
        response_data = {
            "status": "success",
            "job_id": job_id,
            "payment_id": identifier_from_purchaser if identifier_from_purchaser else job_id
        }
        
        if payment_request_data and blockchain_identifier:
            data = payment_request_data.get("data", {})
            
            # Extract amounts from payment request or use configured amounts
            amounts_list = []
            if payment_result.get("payment") and payment_result["payment"].amounts:
                # Convert Amount objects to dict format
                for amount in payment_result["payment"].amounts:
                    amounts_list.append({
                        "quantity": str(amount.quantity),
                        "unit": amount.unit
                    })
            elif settings.PAYMENT_AMOUNT:
                # Use configured payment amount
                amounts_list = [{
                    "quantity": str(settings.PAYMENT_AMOUNT),
                    "unit": settings.PAYMENT_UNIT
                }]
            
            response_data.update({
                "blockchainIdentifier": blockchain_identifier,
                "submitResultTime": data.get("submitResultTime"),
                "unlockTime": data.get("unlockTime"),
                "externalDisputeUnlockTime": data.get("externalDisputeUnlockTime"),
                "agentIdentifier": settings.AGENT_IDENTIFIER,
                "sellerVKey": settings.SELLER_VKEY,
                "identifierFromPurchaser": identifier_from_purchaser,
                "amounts": amounts_list,
                "input_hash": payment_result.get("payment", {}).input_hash if payment_result.get("payment") else None,
                "payByTime": data.get("payByTime")
            })
        
        if cache_entry:
            logger.info(f"Created job {job_id} with cached result")
        else:
            logger.info(f"Created job {job_id} with blockchain_identifier {blockchain_identifier}")
        
        return StartJobResponse(**response_data)
    
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
            
            # Extract PDF URL from input_data (dictionary format from Masumi)
            # Masumi uploads the file and sends a URL string (not base64)
            # Look for the field ID from input_schema ("document_upload") or common keys
            pdf_value = None
            for key in ["document_upload", "document", "pdf"]:
                if key in input_data:
                    pdf_value = input_data[key]
                    break
            
            # Fallback: find any URL string (Masumi sends URL strings, not base64)
            if not pdf_value:
                for key, value in input_data.items():
                    if isinstance(value, str) and (
                        value.startswith("http://") or
                        value.startswith("https://")
                    ):
                        pdf_value = value
                        break
            
            if not pdf_value:
                raise ValueError("No PDF URL found in input_data. Expected 'document_upload' key (from input_schema) with URL string value.")
            
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
            
            # Payment completion is handled in _handle_payment_status callback
            # No need to complete here as it's already done in the callback
            
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
    
    async def start_payment_monitoring(self, job_id: str, blockchain_identifier: str) -> None:
        """
        Start monitoring payment status for a job.
        When payment is confirmed, starts job processing.
        
        Args:
            job_id: Job identifier
            blockchain_identifier: Blockchain payment identifier
        """
        from app.db.base import get_session_factory
        
        async def payment_callback(blockchain_id: str):
            """Async callback when payment is confirmed"""
            logger.info(f"Payment {blockchain_id} confirmed for job {job_id}, starting processing...")
            
            # Create new session for processing
            session_factory = get_session_factory()
            async with session_factory() as session:
                try:
                    # Update job status to running
                    result = await session.execute(select(Job).where(Job.job_id == job_id))
                    job = result.scalar_one_or_none()
                    
                    if job:
                        job.status = "running"
                        job.payment_status = "paid"
                        await session.commit()
                        logger.info(f"Job {job_id} status updated to running")
                        
                        # Start processing the job (this will create its own session)
                        await self.process_job(job_id)
                    else:
                        logger.error(f"Job {job_id} not found when payment confirmed")
                except Exception as e:
                    logger.error(f"Error processing job after payment confirmation: {e}")
                    # Update job status to failed
                    try:
                        result = await session.execute(select(Job).where(Job.job_id == job_id))
                        job = result.scalar_one_or_none()
                        if job:
                            job.status = "failed"
                            job.error = f"Error after payment confirmation: {str(e)}"
                            await session.commit()
                    except Exception as db_error:
                        logger.error(f"Failed to update job status: {db_error}")
                finally:
                    await session.close()
        
        try:
            # Get payment object for monitoring
            session_factory = get_session_factory()
            async with session_factory() as session:
                try:
                    result = await session.execute(select(Job).where(Job.job_id == job_id))
                    job = result.scalar_one_or_none()
                    
                    if not job:
                        logger.error(f"Job {job_id} not found for payment monitoring")
                        return
                    
                    # Recreate payment object for monitoring
                    payment_result = await self.payment_service.create_payment_request(
                        identifier_from_purchaser=job.identifier_from_purchaser or job.job_id,
                        input_data=job.input_data
                    )
                    payment = payment_result["payment"]
                    
                    # Add blockchain identifier to payment
                    payment.payment_ids.add(blockchain_identifier)
                    
                    # Start monitoring
                    await self.payment_service.start_payment_monitoring(payment, payment_callback)
                    logger.info(f"Started payment monitoring for job {job_id}")
                finally:
                    await session.close()
        except Exception as e:
            logger.error(f"Error starting payment monitoring for job {job_id}: {e}")
            # Update job status to failed
            try:
                session_factory = get_session_factory()
                async with session_factory() as session:
                    result = await session.execute(select(Job).where(Job.job_id == job_id))
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        job.error = f"Payment monitoring failed: {str(e)}"
                        await session.commit()
            except Exception as db_error:
                logger.error(f"Failed to update job status: {db_error}")
    
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
