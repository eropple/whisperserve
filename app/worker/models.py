"""Pydantic models for Temporal activities and workflows."""
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field


class S3Location(BaseModel):
    """S3 location information."""
    bucket: str
    key: str


class DownloadMediaInput(BaseModel):
    """Input for download_media activity."""
    job_id: str
    media_url: str
    expected_hash: Optional[str] = None
    tenant_id: str


class DownloadMediaOutput(BaseModel):
    """Output from download_media activity."""
    s3_location: S3Location
    file_size: int
    sha256: str


class TranscribeMediaInput(BaseModel):
    """Input for transcribe_media activity."""
    job_id: str
    s3_location: S3Location
    tenant_id: str
    processing_mode: str = "downmix"
    track_index: Optional[int] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class TranscribeMediaOutput(BaseModel):
    """Output from transcribe_media activity."""
    text: str
    segments: List[Dict[str, Any]]
    language: str
    duration: float
    processing_time: float


class UpdateJobStatusInput(BaseModel):
    """Input for update_job_status activity."""
    job_id: str
    status: str
    tenant_id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateJobStatusOutput(BaseModel):
    """Output from update_job_status activity."""
    status: str
    job_id: str


class TranscriptionWorkflowInput(BaseModel):
    """Input for the transcription workflow."""
    job_id: str
    tenant_id: str
    media_url: str
    media_sha256: Optional[str] = None
    processing_mode: str = "downmix"
    track_index: Optional[int] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class TranscriptionWorkflowOutput(BaseModel):
    """Output from the transcription workflow."""
    job_id: str
    tenant_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None
    media_duration: Optional[float] = None
