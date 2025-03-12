"""Activity interfaces for workflow code to import - KEEP THIS FILE MINIMAL!"""
from temporalio import activity
from app.worker.models import (
    DownloadMediaInput, DownloadMediaOutput,
    TranscribeMediaInput, TranscribeMediaOutput,
    UpdateJobStatusInput, UpdateJobStatusOutput
)

# ONLY bare activity definitions - NO imports beyond basic types!
@activity.defn(name="download_media")
async def download_media(input_data: DownloadMediaInput) -> DownloadMediaOutput:
    """Download media activity interface."""
    raise NotImplementedError("Activity reference only")

@activity.defn(name="transcribe_media")
async def transcribe_media(input_data: TranscribeMediaInput) -> TranscribeMediaOutput:
    """Transcribe media activity interface."""
    raise NotImplementedError("Activity reference only")

@activity.defn(name="update_job_status")
async def update_job_status(input_data: UpdateJobStatusInput) -> UpdateJobStatusOutput:
    """Update job status activity interface."""
    raise NotImplementedError("Activity reference only")
