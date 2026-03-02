"""Router for job status and video retrieval endpoints."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.contracts.api_types import JobStatusResponse
from shared.contracts.enums import JobStatus

from ..config import PROJECT_ROOT, settings
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
        # Keep DB synced with live Redis progress so UI can recover
        try:
            await job_manager.update_job_status(
                job_uuid,
                status=redis_data.get("status"),
                progress_percent=redis_data.get("progress_percent"),
                current_step=redis_data.get("current_step"),
                error_message=redis_data.get("error_message"),
            )
            await db.commit()
        except Exception:
            await db.rollback()

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

    if job.status == JobStatus.PENDING.value:
        elapsed_seconds = max(
            0.0,
            (datetime.now(timezone.utc) - job.created_at).total_seconds(),
        )

        if elapsed_seconds >= settings.JOB_QUEUE_FAIL_SECONDS:
            fail_message = (
                "Job stayed queued too long. No worker appears to be consuming queue "
                "'video_pipeline'. Start the pipeline worker (for local dev: `make dev-worker`) "
                "and retry."
            )
            job = await job_manager.update_job_status(
                job_uuid,
                status=JobStatus.FAILED.value,
                progress_percent=0,
                current_step="Failed: worker unavailable",
                error_message=fail_message,
            )
            await db.commit()
        elif elapsed_seconds >= settings.JOB_QUEUE_WARNING_SECONDS:
            warning_step = (
                "Still queued. Ensure a Celery worker is running on queue "
                "'video_pipeline'."
            )
            if job.current_step != warning_step:
                job = await job_manager.update_job_status(
                    job_uuid,
                    current_step=warning_step,
                )
                await db.commit()

    # Safety net: if worker wrote output file but DB/Redis missed updates,
    # surface completion so frontend never hangs on "pending".
    resolved_video_path = _resolve_video_path(job, job_id)
    if job.status != JobStatus.COMPLETED.value and resolved_video_path is not None:
        job = await job_manager.update_job_status(
            job_uuid,
            status=JobStatus.COMPLETED.value,
            progress_percent=100,
            current_step="Video generation complete.",
            video_path=str(resolved_video_path),
            error_message=None,
        )
        await db.commit()
        resolved_video_path = _resolve_video_path(job, job_id)

    video_url = f"/api/jobs/{job_id}/video" if resolved_video_path else None
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


def _resolve_video_path(job, job_id: str) -> Path | None:
    """Find the video file on disk, checking DB path then fallback."""
    def _candidate_paths(raw_path: str) -> list[Path]:
        p = Path(raw_path)
        candidates = [p]
        if not p.is_absolute():
            candidates.append((PROJECT_ROOT / p).resolve())
            # Backward-compatibility for worker runs started from `pipeline/`.
            candidates.append((PROJECT_ROOT / "pipeline" / p).resolve())
        return candidates

    if job.video_path:
        for p in _candidate_paths(job.video_path):
            if p.exists() and p.stat().st_size > 0:
                return p
    fallback = Path(settings.STORAGE_PATH) / "videos" / job_id / "final.mp4"
    if fallback.exists() and fallback.stat().st_size > 0:
        return fallback
    legacy_fallback = PROJECT_ROOT / "pipeline" / "storage" / "videos" / job_id / "final.mp4"
    if legacy_fallback.exists() and legacy_fallback.stat().st_size > 0:
        return legacy_fallback
    return None


@router.get("/{job_id}/video")
async def get_job_video(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return the completed video file with HTTP Range support for streaming."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    job_manager = JobManager(db)
    job = await job_manager.get_job(job_uuid)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    video_path = _resolve_video_path(job, job_id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Video not yet available for this job.")

    file_size = video_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        range_spec = range_header.replace("bytes=", "")
        range_start_str, range_end_str = range_spec.split("-", 1)
        range_start = int(range_start_str) if range_start_str else 0
        range_end = int(range_end_str) if range_end_str else file_size - 1
        range_end = min(range_end, file_size - 1)
        content_length = range_end - range_start + 1

        def iter_range():
            with open(video_path, "rb") as f:
                f.seek(range_start)
                remaining = content_length
                while remaining > 0:
                    chunk = f.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {range_start}-{range_end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Disposition": f'inline; filename="jestify_{job_id}.mp4"',
                "Cache-Control": "public, max-age=3600",
            },
        )

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"jestify_{job_id}.mp4",
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=3600",
        },
    )
