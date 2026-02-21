"""Router for the generate endpoint that kicks off video generation."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.contracts.api_types import GenerateRequest, GenerateResponse
from shared.contracts.enums import JobStatus

from ..database import get_db
from ..models.document import Document
from ..models.job import Job
from ..services.job_manager import JobManager
from ..tasks.video_task import generate_video_task

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """
    Validate the generation request, create a Job in the database,
    dispatch a Celery task, and return the job ID.
    """
    # Validate that all referenced documents exist
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="At least one document_id is required.")

    doc_uuids = []
    for doc_id in request.document_ids:
        try:
            doc_uuids.append(uuid.UUID(doc_id))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid document ID: {doc_id}")

    result = await db.execute(
        select(Document).where(Document.id.in_(doc_uuids))
    )
    found_docs = result.scalars().all()

    if len(found_docs) != len(request.document_ids):
        found_ids = {str(d.id) for d in found_docs}
        missing = [did for did in request.document_ids if did not in found_ids]
        raise HTTPException(status_code=404, detail=f"Documents not found: {missing}")

    # Create the Job record
    job_manager = JobManager(db)
    job = await job_manager.create_job(
        character=request.character.value,
        difficulty=request.difficulty.value,
        prompt=request.prompt,
        documents=list(found_docs),
    )

    # Combine extracted text from all documents
    combined_text = "\n\n---\n\n".join(
        doc.extracted_text or "" for doc in found_docs
    )

    # Dispatch Celery task
    generate_video_task.delay(
        job_id=str(job.id),
        character=request.character.value,
        difficulty=request.difficulty.value,
        prompt=request.prompt,
        extracted_text=combined_text,
    )

    return GenerateResponse(
        job_id=str(job.id),
        status=JobStatus.PENDING,
        message="Video generation job has been queued.",
    )
