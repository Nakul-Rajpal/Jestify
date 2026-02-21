"""Router for job status and video retrieval endpoints."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.contracts.api_types import JobStatusResponse

from ..config import settings
from ..database import get_db
from ..services.job_manager import JobManager

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """
    Return the current status of a generation job.
    Checks Redis first for live progress updates, then falls back to the database.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    job_manager = JobManager(db)

    # Try Redis first for live progress
    redis_data = await job_manager.get_job_from_redis(str(job_uuid))
    if redis_data:
        return JobStatusResponse(
            job_id=job_id,
            status=redis_data["status"],
            progress_percent=redis_data.get("progress_percent", 0),
            current_step=redis_data.get("current_step", "unknown"),
            video_url=redis_data.get("video_url"),
            thumbnail_url=redis_data.get("thumbnail_url"),
            error_message=redis_data.get("error_message"),
            created_at=redis_data["created_at"],
            updated_at=redis_data["updated_at"],
        )

    # Fall back to database
    job = await job_manager.get_job(job_uuid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    video_url = f"/api/jobs/{job_id}/video" if job.video_path else None
    thumbnail_url = f"/api/jobs/{job_id}/thumbnail" if job.thumbnail_path else None

    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
        video_url=video_url,
        thumbnail_url=thumbnail_url,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{job_id}/video")
async def get_job_video(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Return the completed video file for a job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    job_manager = JobManager(db)
    job = await job_manager.get_job(job_uuid)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    # Try 1: Use video_path from database if it exists on disk
    if job.video_path:
        video_path = Path(job.video_path)
        if video_path.exists():
            return FileResponse(
                path=str(video_path),
                media_type="video/mp4",
                filename=f"jestify_{job_id}.mp4",
            )

    # Try 2: Fallback to conventional storage path
    fallback_path = Path(settings.STORAGE_PATH) / "videos" / job_id / "final.mp4"
    if fallback_path.exists():
        return FileResponse(
            path=str(fallback_path),
            media_type="video/mp4",
            filename=f"jestify_{job_id}.mp4",
        )

    raise HTTPException(status_code=404, detail="Video not yet available for this job.")
