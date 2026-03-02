from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from .enums import Character, Difficulty, JobStatus


class GenerateRequest(BaseModel):
    character: Character
    difficulty: Difficulty
    document_ids: List[str]
    prompt: Optional[str] = None
    interests: Optional[List[str]] = None
    voice_id: Optional[str] = None


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


# --- Library types ---


class TopicSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    sort_order: int
    video_count: int


class SubjectSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: str
    topic_count: int
    video_count: int
    topics: List[TopicSummary]


class LibraryResponse(BaseModel):
    subjects: List[SubjectSummary]


class VideoSummary(BaseModel):
    job_id: str
    title: str
    character: str
    difficulty: str
    video_url: str
    thumbnail_url: Optional[str] = None
    created_at: datetime


class TopicDetailResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    sort_order: int
    subject_name: str
    videos: List[VideoSummary]


class VoiceInfo(BaseModel):
    id: str
    name: str
    description: str
    is_public: bool
    language: Optional[str] = None


class VoiceListResponse(BaseModel):
    voices: List[VoiceInfo]
