"""Pydantic schemas for Job-related request/response validation."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from shared.contracts.enums import JobStatus


class JobBase(BaseModel):
    """Base schema for Job data."""
    character: str
    difficulty: str
    prompt: Optional[str] = None


class JobCreate(JobBase):
    """Schema for creating a new job (internal use)."""
    document_ids: list[str]


class JobUpdate(BaseModel):
    """Schema for updating an existing job."""
    status: Optional[JobStatus] = None
    progress_percent: Optional[int] = None
    current_step: Optional[str] = None
    script_json: Optional[dict] = None
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    error_message: Optional[str] = None


class JobRead(BaseModel):
    """Schema for reading a Job from the database."""
    id: str
    status: str
    progress_percent: int
    current_step: str
    character: str
    difficulty: str
    prompt: Optional[str] = None
    script_json: Optional[dict] = None
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
