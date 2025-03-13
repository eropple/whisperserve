"""Jobs API router for WhisperServe."""
from typing import Dict, Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_config, get_db, get_client
from app.models.job import Job, JobState, ProcessingMode
from app.utils.config import AppConfig
from app.utils.jwt_utils import extract_tenant_id_from_request
from app.worker.models import TranscriptionWorkflowInput
from app.worker.workflows.transcription import TranscriptionWorkflow
from app.logging import get_logger
from app.api.schemas.jobs import (
    CreateJobRequest, 
    JobResponse, 
    JobListResponse,
    JobSummaryResponse
)

# Configure logger
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Security scheme for OpenAPI documentation
security = HTTPBearer(auto_error=False)

# Create a tenant_id dependency to reuse
async def get_tenant_id(
    request: Request,
    config: AppConfig = Depends(get_config)
) -> str:
    """Extract and validate tenant_id from JWT token."""
    tenant_id = extract_tenant_id_from_request(request, config.jwt)
    if not tenant_id:
        logger.warning("unauthorized_access_attempt", path=request.url.path)
        raise HTTPException(status_code=401, detail="Valid authentication required")
    return tenant_id

@router.post("", operation_id="createJob", response_model=JobResponse, status_code=201)
async def create_job(
    request: Request,
    job_request: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
    config: AppConfig = Depends(get_config),
    token: Any = Security(security)
) -> Dict[str, Any]:
    """
    Create a new transcription job.
    
    Requires JWT bearer authentication with a valid tenant_id claim.
    """
    # Get tenant ID from JWT
    tenant_id = await get_tenant_id(request, config)
    logger.info("creating_job", tenant_id=tenant_id, media_url=job_request.media_url)
    
    # Create new job in database - using kwargs to avoid type errors
    job = Job(
        tenant_id=tenant_id,
        media_url=str(job_request.media_url),  # Convert HttpUrl to string
        media_sha256=job_request.media_sha256,
        processing_mode=job_request.processing_mode or ProcessingMode.DOWNMIX,
        track_index=job_request.track_index,
        state=JobState.PENDING
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Get job ID as string for workflow
    job_id = str(job.id)
    
    # Prepare Temporal workflow input
    workflow_input = TranscriptionWorkflowInput(
        job_id=job_id,
        tenant_id=tenant_id,
        media_url=str(job_request.media_url),  # Convert HttpUrl to string
        media_sha256=job_request.media_sha256,
        processing_mode=str(job_request.processing_mode or "downmix"),
        track_index=job_request.track_index,
        options=job_request.options or {}
    )
    
    # Start Temporal workflow
    try:
        # Get Temporal client using dependency
        temporal_client = await get_client(config)
        
        workflow_id = f"{config.temporal.workflow_id_prefix}{job_id}"
        await temporal_client.start_workflow(
            TranscriptionWorkflow.run,
            workflow_input,
            id=workflow_id,
            task_queue=config.temporal.task_queue
        )
        logger.info("workflow_started", workflow_id=workflow_id, job_id=job_id)
    except Exception as e:
        # If workflow fails to start, mark job as failed
        logger.exception("workflow_start_failed", job_id=job_id, error=str(e))
        job.state = JobState.FAILED
        job.error = {"error": f"Failed to start workflow: {str(e)}"}
        await db.commit()
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to start transcription workflow: {str(e)}"
        )
    
    # Properly convert SQLAlchemy model attributes to primitive types
    job_data = {
        "id": str(job.id),
        "tenant_id": str(job.tenant_id),
        "state": job.state.value if job.state is not None else None,
        "media_url": str(job.media_url),
        "media_sha256": job.media_sha256,
        "processing_mode": job.processing_mode.value if job.processing_mode is not None else None,
        "track_index": job.track_index,
        "created_at": job.created_at,
        "updated_at": job.updated_at
    }
    
    # Return job details using explicit dictionary conversion
    return JobResponse(**job_data).dict()

@router.get("/{job_id}", operation_id="getJob", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: AppConfig = Depends(get_config),
    token: Any = Security(security)
) -> Dict[str, Any]:
    """
    Get job details by ID.
    
    Requires JWT bearer authentication with a valid tenant_id claim.
    """
    # Get tenant ID from JWT
    tenant_id = await get_tenant_id(request, config)
    logger.info("fetching_job", job_id=str(job_id), tenant_id=tenant_id)
    
    # Get job from database
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    # Check if job exists
    if not job:
        logger.warning("job_not_found", job_id=str(job_id))
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify tenant ownership
    if str(job.tenant_id) != str(tenant_id):
        logger.warning("unauthorized_job_access", 
                        job_id=str(job_id), 
                        request_tenant_id=tenant_id, 
                        job_tenant_id=job.tenant_id)
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Properly convert SQLAlchemy model attributes to primitive types
    job_data = {
        "id": str(job.id),
        "tenant_id": str(job.tenant_id),
        "state": job.state.value if job.state is not None else None,
        "media_url": str(job.media_url),
        "media_sha256": job.media_sha256,
        "processing_mode": job.processing_mode.value if job.processing_mode is not None else None,
        "track_index": job.track_index,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "worker_id": job.worker_id,
        "error": job.error,
        "error_history": job.error_history,
        "result": job.result,
        "media_duration_seconds": job.media_duration_seconds,
        "processing_time_seconds": job.processing_time_seconds
    }
    
    # Return job details using explicit dictionary conversion
    return JobResponse(**job_data).dict()

@router.get("", operation_id="listJobs", response_model=JobListResponse)
async def list_jobs(
    request: Request,
    state: Optional[JobState] = None,
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    config: AppConfig = Depends(get_config),
    token: Any = Security(security)
) -> Dict[str, Any]:
    """
    List jobs for the authenticated tenant.
    
    Requires JWT bearer authentication with a valid tenant_id claim.
    """
    # Get tenant ID from JWT
    tenant_id = await get_tenant_id(request, config)
    logger.info("listing_jobs", tenant_id=tenant_id, state=state.value if state else None)
    
    # Build query
    query = select(Job).where(Job.tenant_id == tenant_id)
    
    # Apply state filter if provided
    if state is not None:
        query = query.where(Job.state == state) # type: ignore
    
    # Apply sorting (newest first)
    query = query.order_by(Job.created_at.desc())
    
    # Get total count (without pagination)
    count_query = select(Job.id).where(Job.tenant_id == tenant_id)
    if state is not None:
        count_query = count_query.where(Job.state == state) # type: ignore
    count_result = await db.execute(count_query)
    total_count = len(count_result.scalars().all())
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Convert to response models with explicit type conversion
    job_summaries = []
    for job in jobs:
        job_data = {
            "id": str(job.id),
            "state": job.state.value,
            "media_url": str(job.media_url),
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "media_duration_seconds": job.media_duration_seconds,
            "processing_time_seconds": job.processing_time_seconds
        }
        job_summaries.append(JobSummaryResponse(**job_data).dict())
    
    # Return paginated response
    return {
        "jobs": job_summaries,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }
