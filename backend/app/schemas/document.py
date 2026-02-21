"""Pydantic schemas for Document-related request/response validation."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentBase(BaseModel):
    """Base schema for Document data."""
    filename: str
    document_type: str
    mime_type: str
    size_bytes: int


class DocumentCreate(DocumentBase):
    """Schema for creating a new document record."""
    original_path: str
    extracted_text: Optional[str] = None


class DocumentRead(BaseModel):
    """Schema for reading a Document from the database."""
    id: str
    filename: str
    document_type: str
    mime_type: str
    size_bytes: int
    original_path: str
    extracted_text: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
