"""Celery worker entry point for the video generation pipeline."""

import asyncio
import json
import logging
import sys
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path so shared.contracts is importable.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Also ensure pipeline/ dir is on sys.path so 'pipeline' package is importable
_PIPELINE_DIR = str(Path(__file__).resolve().parents[1])
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)

from celery import Celery

from shared.contracts.enums import Character, Difficulty, JobStatus
from shared.contracts.pipeline_schema import PipelineInput
from pipeline.config import REDIS_URL

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Celery application
# --------------------------------------------------------------------------- #
app = Celery(
    "jestify_pipeline",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


# --------------------------------------------------------------------------- #
# Redis helpers
# --------------------------------------------------------------------------- #

def _redis_client():
    import redis as _redis
    return _redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _update_redis_progress(
    job_id: str,
    status: str,
    progress_percent: int,
    current_step: str,
    error_message: Optional[str] = None,
    video_url: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
):
    """Push live progress to Redis so the backend jobs endpoint can read it."""
    try:
        r = _redis_client()
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "status": status,
            "progress_percent": progress_percent,
            "current_step": current_step,
            "error_message": error_message,
            "video_url": video_url,
            "thumbnail_url": thumbnail_url,
            "created_at": now,
            "updated_at": now,
        }
        r.set(f"job:{job_id}", json.dumps(data), ex=3600)
        r.close()
    except Exception as e:
        logger.warning(f"Failed to update Redis progress for job {job_id}: {e}")


# --------------------------------------------------------------------------- #
# Database persistence
# --------------------------------------------------------------------------- #

def _persist_job_to_db(
    job_id: str,
    status: str,
    progress_percent: int,
    current_step: str,
    video_path: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """Persist final job state to PostgreSQL so it survives Redis TTL expiration."""

    async def _do_update():
        from backend.app.database import async_session_factory
        from backend.app.models.job import Job
        from sqlalchemy import select

        async with async_session_factory() as session:
            try:
                result = await session.execute(
                    select(Job).where(Job.id == _uuid.UUID(job_id))
                )
                job = result.scalar_one_or_none()
                if job is None:
                    logger.warning(f"Job {job_id} not found in DB for persistence")
                    return

                job.status = status
                job.progress_percent = progress_percent
                job.current_step = current_step
                if video_path is not None:
                    job.video_path = video_path
                if error_message is not None:
                    job.error_message = error_message
                job.updated_at = datetime.now(timezone.utc)

                await session.commit()
                logger.info(f"Persisted job {job_id} to DB: status={status}, video_path={video_path}")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to persist job {job_id} to DB: {e}", exc_info=True)

    try:
        asyncio.run(_do_update())
    except Exception as e:
        logger.error(f"DB persistence failed for job {job_id}: {e}", exc_info=True)


# --------------------------------------------------------------------------- #
# Celery task — matches the name the backend dispatches
# --------------------------------------------------------------------------- #

@app.task(bind=True, name="backend.app.tasks.video_task.generate_video_task")
def generate_video_task(
    self,
    job_id: str,
    character: str,
    difficulty: str,
    extracted_text: str,
    prompt: Optional[str] = None,
):
    """
    Main Celery task picked up by the pipeline worker.

    This task:
    1. Generates the educational script using Claude
    2. Runs the ManimGL rendering pipeline
    3. Updates job status in Redis throughout
    """
    logger.info(f"Starting video generation for job {job_id}")

    try:
        # Step 1: Generate script using Claude (two-phase: narration then manim code)
        _update_redis_progress(
            job_id,
            status=JobStatus.GENERATING_SCRIPT.value,
            progress_percent=5,
            current_step="Generating educational narration script...",
        )

        from backend.app.services.script_generator import ScriptGenerator

        generator = ScriptGenerator()

        def _on_script_progress(phase: str, pct: int):
            if phase == "generating_animations":
                _update_redis_progress(
                    job_id,
                    status=JobStatus.GENERATING_ANIMATIONS.value,
                    progress_percent=pct,
                    current_step="Designing ManimGL animation code...",
                )

        script = generator.generate(
            extracted_text=extracted_text,
            character=Character(character),
            difficulty=Difficulty(difficulty),
            user_prompt=prompt,
            on_progress=_on_script_progress,
        )

        logger.info(f"Script generated for job {job_id}: {script.total_scenes} scenes")

        # Step 2: Build pipeline input and run orchestrator
        _update_redis_progress(
            job_id,
            status=JobStatus.RENDERING_ANIMATIONS.value,
            progress_percent=20,
            current_step="Script generated. Starting video rendering...",
        )

        from pipeline.config import STORAGE_PATH
        output_path = f"{STORAGE_PATH}/videos/{job_id}/final.mp4"

        pipeline_input = PipelineInput(
            job_id=job_id,
            script=script,
            character=Character(character),
            output_path=output_path,
        )

        # Step 3: Run the full rendering pipeline
        from pipeline.orchestrator import PipelineOrchestrator

        def _on_progress(status: JobStatus, progress_pct: int):
            step_messages = {
                JobStatus.RENDERING_ANIMATIONS: "Rendering ManimGL animations...",
                JobStatus.SYNTHESIZING_VOICE: "Synthesizing character voice...",
                JobStatus.COMPOSITING: "Compositing character overlay...",
                JobStatus.ASSEMBLING: "Assembling final video...",
            }
            _update_redis_progress(
                job_id,
                status=status.value,
                progress_percent=progress_pct,
                current_step=step_messages.get(status, "Processing..."),
            )

        orchestrator = PipelineOrchestrator(status_callback=_on_progress)
        output = orchestrator.run(pipeline_input)

        # Step 4: Mark completed
        _update_redis_progress(
            job_id,
            status=JobStatus.COMPLETED.value,
            progress_percent=100,
            current_step="Video generation complete.",
            video_url=f"/api/jobs/{job_id}/video",
        )

        logger.info(f"Pipeline completed for job {job_id} -> {output.video_path}")

        # Persist final state to database
        _persist_job_to_db(
            job_id=job_id,
            status=JobStatus.COMPLETED.value,
            progress_percent=100,
            current_step="Video generation complete.",
            video_path=output.video_path,
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "video_path": output.video_path,
            "duration_seconds": output.duration_seconds,
        }

    except Exception as e:
        logger.error(f"Video generation failed for job {job_id}: {e}", exc_info=True)
        _update_redis_progress(
            job_id,
            status=JobStatus.FAILED.value,
            progress_percent=0,
            current_step="Failed",
            error_message=str(e),
        )
        _persist_job_to_db(
            job_id=job_id,
            status=JobStatus.FAILED.value,
            progress_percent=0,
            current_step="Failed",
            error_message=str(e),
        )
        raise
