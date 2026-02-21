"""Celery task for the video generation pipeline."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import redis

from shared.contracts.enums import Character, Difficulty, JobStatus
from shared.contracts.pipeline_schema import PipelineInput

from ..config import settings
from .celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_redis_progress(
    job_id: str,
    status: str,
    progress_percent: int,
    current_step: str,
    error_message: Optional[str] = None,
    video_url: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
) -> None:
    """Push live progress to Redis so the jobs endpoint can read it."""
    try:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
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
        r.set(f"job:{job_id}", json.dumps(data), ex=3600)  # 1 hour TTL
        r.close()
    except Exception as e:
        logger.warning(f"Failed to update Redis progress for job {job_id}: {e}")


@celery_app.task(name="backend.app.tasks.video_task.generate_video_task", bind=True)
def generate_video_task(
    self,
    job_id: str,
    character: str,
    difficulty: str,
    extracted_text: str,
    prompt: Optional[str] = None,
) -> dict:
    """
    Main Celery task that orchestrates the video generation pipeline.

    Steps:
    1. Generate the educational script using Claude
    2. Dispatch to the rendering pipeline (ManimGL + TTS + compositing)
    3. Update job status throughout

    Args:
        job_id: UUID of the job.
        character: Character enum value string.
        difficulty: Difficulty enum value string.
        extracted_text: Combined extracted text from all documents.
        prompt: Optional user prompt for additional instructions.

    Returns:
        A dict with the pipeline result.
    """
    logger.info(f"Starting video generation task for job {job_id}")

    try:
        # Step 1: Generate script
        _update_redis_progress(
            job_id,
            status=JobStatus.GENERATING_SCRIPT.value,
            progress_percent=10,
            current_step="Generating educational script with AI...",
        )

        from ..services.script_generator import ScriptGenerator

        generator = ScriptGenerator()
        script = generator.generate(
            extracted_text=extracted_text,
            character=Character(character),
            difficulty=Difficulty(difficulty),
            user_prompt=prompt,
        )

        _update_redis_progress(
            job_id,
            status=JobStatus.RENDERING_ANIMATIONS.value,
            progress_percent=30,
            current_step="Script generated. Rendering animations...",
        )

        # Step 2: Build pipeline input
        output_path = f"{settings.STORAGE_PATH}/videos/{job_id}"
        pipeline_input = PipelineInput(
            job_id=job_id,
            script=script,
            character=Character(character),
            output_path=output_path,
        )

        # Step 3: Dispatch to pipeline worker
        # TODO: Integrate with the actual ManimGL rendering pipeline
        # For now, we log the pipeline input and mark as completed
        logger.info(
            f"Pipeline input ready for job {job_id}: "
            f"{script.total_scenes} scenes, character={character}"
        )

        _update_redis_progress(
            job_id,
            status=JobStatus.RENDERING_ANIMATIONS.value,
            progress_percent=50,
            current_step="Rendering ManimGL animations...",
        )

        # Placeholder: actual rendering, TTS, and compositing would happen here
        # The pipeline would call _update_redis_progress at each stage

        _update_redis_progress(
            job_id,
            status=JobStatus.COMPLETED.value,
            progress_percent=100,
            current_step="Video generation complete.",
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "script": script.model_dump(),
            "pipeline_input": pipeline_input.model_dump(),
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
        raise
