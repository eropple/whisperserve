"""Job status management activity for Temporal."""
from sqlalchemy import select
from temporalio import activity

from app.models.job import Job, JobState
from app.db.engine import get_db_session
from app.logging import get_logger
from app.utils.config import load_config
from app.worker.models import UpdateJobStatusInput, UpdateJobStatusOutput

@activity.defn
async def update_job_status(input_data: UpdateJobStatusInput) -> UpdateJobStatusOutput:
    """
    Update job status in the database.
    """
    # Load config inside the activity
    config = load_config()
    
    logger = get_logger().bind(
        activity="update_job_status", 
        job_id=input_data.job_id,
        tenant_id=input_data.tenant_id
    )
    
    logger.info("updating_job_status", status=input_data.status)
    
    try:
        async with get_db_session() as session:
            # Get the job
            stmt = select(Job).where(Job.id == input_data.job_id)
            result_obj = await session.execute(stmt)
            job = result_obj.scalar_one_or_none()
            
            if not job:
                raise ValueError(f"Job {input_data.job_id} not found")
            
            # Verify tenant_id matches to prevent cross-tenant access
            # Convert both values to strings to ensure proper comparison
            if str(job.tenant_id) != str(input_data.tenant_id):
                raise ValueError(f"Job belongs to a different tenant")
            
            if input_data.status == JobState.SUCCEEDED:
                result = input_data.result
                if result is None:
                    raise ValueError("Result is required for SUCCEEDED status")
                
                job.mark_as_succeeded(
                    result=result,
                    media_duration=input_data.metadata.get("media_duration") if input_data.metadata else None,
                    processing_time=input_data.metadata.get("processing_time") if input_data.metadata else None
                )
            elif input_data.status == JobState.FAILED:
                job.record_failure(input_data.error or {"error": "Unknown error"})
            else:
                job.state = JobState(input_data.status)
                if input_data.metadata:
                    # Update additional fields based on metadata
                    for key, value in input_data.metadata.items():
                        if hasattr(job, key):
                            setattr(job, key, value)
            
            await session.commit()
            logger.info("job_status_updated", new_status=input_data.status)
            
            return UpdateJobStatusOutput(
                status=input_data.status,
                job_id=input_data.job_id
            )
    
    except Exception as e:
        logger.exception("status_update_failed", error=str(e))
        raise
