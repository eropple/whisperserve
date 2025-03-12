"""Transcription workflow."""
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from app.worker.activities.interfaces import (
    download_media,
    transcribe_media,
    update_job_status
)

from app.worker.models import (
    DownloadMediaInput,
    TranscribeMediaInput,
    TranscriptionWorkflowInput,
    TranscriptionWorkflowOutput,
    UpdateJobStatusInput,
)

from app.models.job import JobState


@workflow.defn
class TranscriptionWorkflow:
    """Workflow for speech-to-text transcription jobs."""
    
    @workflow.run
    async def run(self, input_data: TranscriptionWorkflowInput) -> TranscriptionWorkflowOutput:
        """Execute the transcription workflow."""

        from datetime import timedelta
        # Define retry policies
        standard_retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(minutes=1),
            maximum_attempts=3,
            non_retryable_error_types=["ValueError"]
        )
        
        # Use a more persistent retry policy for media download
        download_retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            maximum_interval=timedelta(minutes=5),
            maximum_attempts=5,
            non_retryable_error_types=["ValueError"]
        )
        
        # Initialize output
        output = TranscriptionWorkflowOutput(
            job_id=input_data.job_id,
            tenant_id=input_data.tenant_id,
            status=JobState.PENDING
        )
        
        try:
            # Step 1: Update status to DOWNLOADING
            await workflow.execute_activity(
                update_job_status,
                UpdateJobStatusInput(
                    job_id=input_data.job_id,
                    tenant_id=input_data.tenant_id,
                    status=JobState.DOWNLOADING
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=standard_retry_policy
            )
            
            # Step 2: Download the media file to S3
            download_result = await workflow.execute_activity(
                download_media,
                DownloadMediaInput(
                    job_id=input_data.job_id,
                    tenant_id=input_data.tenant_id,
                    media_url=input_data.media_url,
                    expected_hash=input_data.media_sha256
                ),
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=download_retry_policy
            )
            
            # Step 3: Update status to PROCESSING
            await workflow.execute_activity(
                update_job_status,
                UpdateJobStatusInput(
                    job_id=input_data.job_id,
                    tenant_id=input_data.tenant_id,
                    status=JobState.PROCESSING
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=standard_retry_policy
            )
            
            # Step 4: Transcribe the media using S3 location
            transcribe_result = await workflow.execute_activity(
                transcribe_media,
                TranscribeMediaInput(
                    job_id=input_data.job_id,
                    tenant_id=input_data.tenant_id,
                    s3_location=download_result.s3_location,
                    processing_mode=input_data.processing_mode,
                    track_index=input_data.track_index,
                    options=input_data.options
                ),
                start_to_close_timeout=timedelta(hours=2),  # Longer timeout for large files
                retry_policy=standard_retry_policy
            )
            
            # Step 5: Update job with successful result
            result_dict = {
                "text": transcribe_result.text,
                "segments": transcribe_result.segments,
                "language": transcribe_result.language,
                "duration": transcribe_result.duration
            }
            
            metadata = {
                "media_duration_seconds": transcribe_result.duration,
                "processing_time_seconds": transcribe_result.processing_time
            }
            
            final_status = await workflow.execute_activity(
                update_job_status,
                UpdateJobStatusInput(
                    job_id=input_data.job_id,
                    tenant_id=input_data.tenant_id,
                    status=JobState.SUCCEEDED,
                    result=result_dict,
                    metadata=metadata
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=standard_retry_policy
            )
            
            # Set successful output
            output.status = JobState.SUCCEEDED
            output.result = result_dict
            output.processing_time = transcribe_result.processing_time
            output.media_duration = transcribe_result.duration
            
        except Exception as e:
            # Handle workflow failure
            error_details = {
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            # Try to update job status to FAILED
            try:
                await workflow.execute_activity(
                    update_job_status,
                    UpdateJobStatusInput(
                        job_id=input_data.job_id,
                        tenant_id=input_data.tenant_id,
                        status=JobState.FAILED,
                        error=error_details
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    # Always retry this final status update
                    retry_policy=RetryPolicy(maximum_attempts=10)
                )
            except Exception as status_error:
                # If we can't update the status, log it and continue with the original error
                workflow.logger.error(f"Failed to update job status: {status_error}")
            
            # Set error in output
            output.status = JobState.FAILED
            output.error = error_details
            
            # Re-raise the original exception for Temporal visibility
            if isinstance(e, ApplicationError):
                raise
            else:
                raise ApplicationError("TRANSCRIPTION_FAILED", str(e))
        
        return output
