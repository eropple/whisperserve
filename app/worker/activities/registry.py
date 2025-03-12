"""Registry for Temporal activities."""
from typing import List, Callable

from app.worker.activities.download import download_media
from app.worker.activities.transcribe import transcribe_media
from app.worker.activities.status import update_job_status

def get_activities() -> List[Callable]:
    """
    Get all activity implementations.
    
    Returns:
        List of activity functions
    """
    return [
        download_media,
        transcribe_media,
        update_job_status
    ]