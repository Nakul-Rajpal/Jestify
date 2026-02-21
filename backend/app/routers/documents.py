"""Router for document upload and retrieval endpoints."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.contracts.api_types import DocumentUploadResponse
from shared.contracts.enums import DocumentType

from ..config import settings
from ..database import get_db
from ..models.document import Document
from ..services.document_processor import DocumentProcessor

router = APIRouter(prefix="/documents", tags=["documents"])

# Allowed MIME types mapped to document types
MIME_TYPE_MAP: dict[str, DocumentType] = {
    "application/pdf": DocumentType.PDF,
    "image/png": DocumentType.IMAGE,
    "image/jpeg": DocumentType.IMAGE,
    "image/jpg": DocumentType.IMAGE,
    "image/webp": DocumentType.IMAGE,
    "image/tiff": DocumentType.IMAGE,
    "text/plain": DocumentType.TEXT,
    "text/markdown": DocumentType.TEXT,
    "text/csv": DocumentType.TEXT,
}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Accept a multipart file upload, validate its type, save to storage,
    extract text content, and return metadata.
    """
    # Validate MIME type
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in MIME_TYPE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {mime_type}. "
            f"Allowed types: {', '.join(MIME_TYPE_MAP.keys())}",
        )

    document_type = MIME_TYPE_MAP[mime_type]

    # Read file content
    content = await file.read()
    size_bytes = len(content)

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Save file to storage
    doc_id = uuid.uuid4()
    storage_dir = Path(settings.STORAGE_PATH) / "documents"
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename or "file").suffix
    saved_filename = f"{doc_id}{file_ext}"
    file_path = storage_dir / saved_filename

    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text
    processor = DocumentProcessor()
    extracted_text = processor.extract_text(str(file_path), mime_type)

    # Create database record
    document = Document(
        id=doc_id,
        filename=file.filename or "unknown",
        document_type=document_type.value,
        mime_type=mime_type,
        size_bytes=size_bytes,
        original_path=str(file_path),
        extracted_text=extracted_text,
    )
    db.add(document)
    await db.flush()

    # Build preview (first 500 chars)
    preview = (extracted_text[:500] + "...") if len(extracted_text) > 500 else extracted_text

    return DocumentUploadResponse(
        document_id=str(doc_id),
        filename=file.filename or "unknown",
        document_type=document_type.value,
        size_bytes=size_bytes,
        extracted_text_preview=preview,
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return document metadata by ID."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format.")

    result = await db.execute(select(Document).where(Document.id == doc_uuid))
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return {
        "id": str(document.id),
        "filename": document.filename,
        "document_type": document.document_type,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "extracted_text_preview": (
            (document.extracted_text[:500] + "...")
            if document.extracted_text and len(document.extracted_text) > 500
            else (document.extracted_text or "")
        ),
        "created_at": document.created_at.isoformat(),
    }
