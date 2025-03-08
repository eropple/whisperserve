import asyncio
import time
import uuid
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, cast

import structlog
from sqlalchemy import ColumnElement, func, select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobState
from app.db.engine import get_db_session
from app.worker.backends.base import ModelBackend, TranscriptionResult
from app.utils.config import ServerConfig

# Set up structured logger
logger = structlog.get_logger()

class JobProcessor:
    """
    Main job processor that handles claiming jobs from the database,
    processing them with the appropriate backend, and updating results.
    """
    
    def __init__(
        self,
        model_backend: ModelBackend,
        server_config: ServerConfig,
        worker_id: Optional[str] = None
    ):
        """
        Initialize the job processor.
        
        Args:
            model_backend: The model backend to use for transcription
            server_config: Server configuration
            worker_id: Unique ID for this worker instance
        """
        self.backend = model_backend
        self.worker_id = worker_id or f"worker-{uuid.uuid4()}"
        self.config = server_config
        self.running = False
        self.processing_dir = Path("/tmp/whisperserve/processing")
        
        # Ensure processing directory exists
        os.makedirs(self.processing_dir, exist_ok=True)
        
        # Bind worker ID to logger context
        self.log = logger.bind(worker_id=self.worker_id, component="job_processor")
    
    async def start(self) -> None:
        """Start the job processor loop."""
        if self.running:
            return
        
        self.log.info("starting_job_processor", backend=self.backend.name)
        
        # Initialize the model backend
        if not await self.backend.initialize():
            self.log.error("backend_initialization_failed", backend=self.backend.name)
            return
        
        self.log.info("backend_initialized", 
                      backend=self.backend.name, 
                      model_size=self.backend.model_size)
        
        self.running = True
        
        while self.running:
            try:
                # Process a batch of jobs
                processed = await self.process_job_batch()
                
                # If no jobs were processed, wait a bit before trying again
                if not processed:
                    await asyncio.sleep(self.config.job_polling_interval)
            except Exception as e:
                self.log.exception("job_processor_error", error=str(e))
                await asyncio.sleep(self.config.job_polling_interval)
    
    async def stop(self) -> None:
        """Stop the job processor."""
        self.log.info("stopping_job_processor")
        self.running = False
        
        # Shut down the backend
        try:
            await self.backend.shutdown()
        except Exception as e:
            self.log.error("backend_shutdown_error", error=str(e))
    
    async def claim_jobs(self, session: AsyncSession, batch_size: int) -> List[Job]:
        """
        Claim pending jobs for processing using SKIP LOCKED.
        
        Args:
            session: Database session
            batch_size: Maximum number of jobs to claim
            
        Returns:
            List of claimed jobs
        """
        self.log.debug("claiming_jobs", batch_size=batch_size)
        
        # Find jobs to process that are:
        # 1. In PENDING state, or
        # 2. In RETRYING state and ready for retry (next_attempt_at <= now)
        now = datetime.now()
        
        stmt = (
            select(Job)
            .where(
                or_(
                    # New pending jobs
                    cast("ColumnElement[bool]", Job.state == JobState.PENDING),
                    # Failed jobs ready for retry
                    and_(
                        cast("ColumnElement[bool]", Job.state == JobState.RETRYING),
                        Job.next_attempt_at <= func.now()
                    )
                )
            )
            .order_by(Job.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        
        result = await session.execute(stmt)
        jobs = result.scalars().all()
        
        # Mark jobs as claimed
        for job in jobs:
            job.state = JobState.CLAIMED
            job.worker_id = self.worker_id
            # Don't update started_at yet - that happens when processing begins
        
        if jobs:
            self.log.info("jobs_claimed", count=len(jobs))
            await session.commit()
        
        return list(jobs)
    
    async def process_job(self, job: Job, session: AsyncSession) -> None:
        """
        Process a single job.
        
        Args:
            job: The job to process
            session: Database session
        """
        job_logger = self.log.bind(
            job_id=str(job.id),
            tenant_id=job.tenant_id,
            media_url=job.media_url
        )
        
        job_logger.info("processing_job")
        
        # Mark as processing and record start time
        job.mark_as_processing(self.worker_id)
        await session.commit()
        
        # Create a directory for this job
        job_dir = self.processing_dir / str(job.id)
        os.makedirs(job_dir, exist_ok=True)
        
        try:
            # Step 1: Download the media file
            job.state = JobState.DOWNLOADING
            await session.commit()
            
            media_file = await self.download_media(job, job_dir, job_logger)
            
            # Step 2: Process with the model backend
            job.state = JobState.PROCESSING
            await session.commit()
            
            job_logger.info("transcription_started")
            start_time = time.time()
            
            result = await self.backend.transcribe(
                audio_path=str(media_file),
                options={
                    "processing_mode": job.processing_mode,
                    "track_index": job.track_index
                }
            )
            
            processing_time = time.time() - start_time
            job_logger.info("transcription_completed", 
                          duration=result.duration,
                          processing_time=processing_time,
                          language=result.language)
            
            # Step 3: Record the results
            job.mark_as_succeeded(
                result=result.to_dict(),
                media_duration=result.duration,
                processing_time=processing_time
            )
            
            await session.commit()
            job_logger.info("job_succeeded")
            
        except Exception as e:
            job_logger.exception("job_processing_failed", error=str(e))
            
            # Record the failure
            error_info = {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "worker_id": self.worker_id
            }
            job.record_failure(error_info)
            await session.commit()
            
        finally:
            # Clean up job directory
            try:
                import shutil
                shutil.rmtree(job_dir, ignore_errors=True)
            except Exception as e:
                job_logger.warning("cleanup_failed", error=str(e))
    
    async def process_job_batch(self) -> int:
        """
        Process a batch of jobs.
        
        Returns:
            int: Number of jobs processed
        """
        processed_count = 0
        
        async with get_db_session() as session:
            # Find and claim a batch of jobs
            jobs = await self.claim_jobs(session, self.config.job_batch_size)
            
            if not jobs:
                return 0
            
            # Process each job
            for job in jobs:
                try:
                    await self.process_job(job, session)
                    processed_count += 1
                except Exception as e:
                    self.log.exception("batch_processing_error", 
                                    job_id=str(job.id),
                                    error=str(e))
                    
                    # Record the failure
                    error_info = {
                        "error": str(e),
                        "traceback": str(e.__traceback__),
                        "worker_id": self.worker_id,
                        "timestamp": datetime.now().isoformat()
                    }
                    job.record_failure(error_info)
                    await session.commit()
        
        return processed_count
    
    async def download_media(self, job: Job, job_dir: Path, job_logger) -> Path:
        """
        Download media file from URL and verify integrity if hash is provided.
        
        Args:
            job: The job containing the media URL
            job_dir: Directory to save the downloaded file
            job_logger: Logger with job context
            
        Returns:
            Path to the downloaded file
        """
        import aiohttp
        import aiofiles
        from urllib.parse import urlparse
        
        job_logger.info("media_download_started")
        
        # Ensure media_url is a string for urlparse
        media_url = str(job.media_url)
        
        # Extract filename from URL or use job ID
        url_path = urlparse(media_url).path
        filename = os.path.basename(url_path) or f"media_{job.id}"
        output_file = job_dir / filename
        
        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(media_url) as response:
                if response.status != 200:
                    error_msg = f"Failed to download media: HTTP {response.status}"
                    job_logger.error("media_download_failed", 
                                    status=response.status,
                                    error=error_msg)
                    raise ValueError(error_msg)
                
                # Stream to file while calculating hash
                hash_sha256 = hashlib.sha256()
                total_bytes = 0
                
                async with aiofiles.open(output_file, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)
                        hash_sha256.update(chunk)
                        total_bytes += len(chunk)
                
                # Verify hash if provided
                calculated_hash = hash_sha256.hexdigest()
                # Use explicit checking for None rather than relying on truthiness
                media_sha256 = job.media_sha256
                if media_sha256 is not None and calculated_hash != media_sha256:
                    error_msg = "Media file hash mismatch"
                    job_logger.error("hash_verification_failed", 
                                expected=media_sha256,
                                calculated=calculated_hash)
                    raise ValueError(error_msg)
    
        
        job_logger.info("media_download_completed", 
                        file_size=total_bytes,
                        sha256=calculated_hash)
        
        return output_file
