import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Type, TypeVar, cast, Union
from enum import Enum

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.decl_api import DeclarativeMeta

# Create the base class
Base = declarative_base()

# Type variable for models that inherit from Base
# Using DeclarativeMeta instead of Base for the bound
T = TypeVar('T', bound='DeclarativeMeta')
ModelType = Type[T]

class JobState(str, Enum):
    """Finite state machine for job processing states."""
    PENDING = "pending"              # Initial state, job created but not claimed
    CLAIMED = "claimed"              # Job has been claimed by a worker but processing not started
    DOWNLOADING = "downloading"      # Media is being downloaded
    PROCESSING = "processing"        # Transcription is in progress
    SUCCEEDED = "succeeded"          # Job completed successfully
    FAILED = "failed"                # Job failed and won't be retried
    RETRYING = "retrying"            # Job failed but will be retried later
    CANCELED = "canceled"            # Job was canceled by user or system

class ProcessingMode(str, Enum):
    """Audio processing modes for transcription."""
    DOWNMIX = "downmix"       # Mix all audio channels to mono
    SELECT = "select"         # Select a specific audio track/channel
    MULTITRACK = "multitrack" # Process all tracks separately


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    
    # FSM state tracking
    state = Column(SQLEnum(JobState), nullable=False, default=JobState.PENDING, index=True)
    
    # Job configuration
    media_url = Column(String, nullable=False)
    media_sha256 = Column(String(64), nullable=True)  # SHA256 hash for download integrity
    processing_mode = Column(SQLEnum(ProcessingMode), nullable=False, default=ProcessingMode.DOWNMIX)

    track_index = Column(Integer, nullable=True)

    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
    
    # Worker tracking
    worker_id = Column(String, nullable=True)
    
    # Results and errors
    error = Column(JSON, nullable=True)  # JSON blob with error details
    error_history = Column(JSON, default=list)  # History of errors from previous attempts
    result = Column(JSON, nullable=True)  # Transcription result
    
    # Metrics
    media_duration_seconds = Column(Float, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for API responses."""
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "state": self.state.value if self.state is not None else None,
            "media_url": self.media_url,
            "media_sha256": self.media_sha256,  # Added SHA256 field
            "processing_mode": self.processing_mode,
            "track_index": self.track_index,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at is not None else None,
            "worker_id": self.worker_id,
            "error": self.error,
            "error_history": self.error_history,
            "result": self.result,
            "media_duration_seconds": self.media_duration_seconds,
            "processing_time_seconds": self.processing_time_seconds,
        }
    
    def record_failure(self, error_info: Dict[str, Any]) -> None:
        """
        Record a job failure, update error history, and determine if retry is possible.
        """
        # Update error history
        if self.error_history is None:
            self.error_history = []
        
        # Add current error to history with timestamp
        error_entry = {
            "attempt": self.attempt_count,
            "timestamp": datetime.now().isoformat(),
            "error": error_info
        }
        
        history = self.error_history
        if isinstance(history, list):
            history.append(error_entry)
            self.error_history = history
        else:
            self.error_history = [error_entry]
        
        # Set current error
        self.error = error_info
        
        # Increment attempt count
        current_attempts = cast(int, self.attempt_count)
        self.attempt_count = current_attempts + 1
        
        # Check if we've exceeded max attempts
        max_attempts = cast(int, self.max_attempts)
        if current_attempts + 1 >= max_attempts:
            self.state = JobState.FAILED
        else:
            self.state = JobState.RETRYING
    
    def mark_as_processing(self, worker_id: str) -> None:
        """Mark the job as being processed by a worker."""
        self.worker_id = worker_id
        self.state = JobState.PROCESSING
        if self.started_at is None:
            self.started_at = datetime.now()
    
    def mark_as_succeeded(self, result: Dict[str, Any], 
                         media_duration: Optional[float] = None,
                         processing_time: Optional[float] = None) -> None:
        """Mark the job as successfully completed."""
        self.state = JobState.SUCCEEDED
        self.result = result
        self.completed_at = datetime.now()
        self.media_duration_seconds = media_duration
        self.processing_time_seconds = processing_time
