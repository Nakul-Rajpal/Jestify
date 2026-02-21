from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from .enums import Character, Difficulty, JobStatus


class GenerateRequest(BaseModel):
    character: Character
    difficulty: Difficulty
    document_ids: List[str]
    prompt: Optional[str] = None


class GenerateResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress_percent: int
    current_step: str
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    document_type: str
    size_bytes: int
    extracted_text_preview: str


class CharacterInfo(BaseModel):
    id: Character
    name: str
    description: str
    thumbnail_url: str
    personality_summary: str


class CharacterListResponse(BaseModel):
    characters: List[CharacterInfo]
