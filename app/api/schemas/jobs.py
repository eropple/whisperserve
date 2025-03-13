"""Pydantic schemas for the jobs API."""
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models.job import ProcessingMode

class CreateJobRequest(BaseModel):
    """Request model for job creation."""
    media_url: HttpUrl = Field(..., description="URL of the media file to transcribe")
    media_sha256: Optional[str] = Field(None, description="SHA256 hash of the media file for verification")
    processing_mode: Optional[str] = Field("downmix", description="Audio processing mode")
    track_index: Optional[int] = Field(None, description="Audio track index when using 'select' mode")
    options: Optional[Dict[str, Any]] = Field(None, description="Additional processing options")
    
    class Config:
        schema_extra = {
            "example": {
                "media_url": "https://example.com/media/audio.mp3",
                "media_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "processing_mode": "downmix",
                "options": {
                    "language": "en",
                    "word_timestamps": True
                }
            }
        }

class JobSummaryResponse(BaseModel):
    """Summary response model for job listings."""
    id: str
    state: str
    media_url: str
    created_at: datetime
    updated_at: datetime
    media_duration_seconds: Optional[float] = None
    processing_time_seconds: Optional[float] = None

class JobResponse(BaseModel):
    """Full response model for job details."""
    id: str
    tenant_id: str
    state: str
    media_url: str
    media_sha256: Optional[str] = None
    processing_mode: Optional[str] = None
    track_index: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    worker_id: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    error_history: Optional[List[Dict[str, Any]]] = None
    result: Optional[Dict[str, Any]] = None
    media_duration_seconds: Optional[float] = None
    processing_time_seconds: Optional[float] = None

class JobListResponse(BaseModel):
    """Response model for job listings with pagination."""
    jobs: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int
