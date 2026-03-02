"""Celery task for the video generation pipeline."""

import json
import logging
import time
import traceback
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
        r.set(f"job:{job_id}", json.dumps(data), ex=3600)
        r.close()
        logger.debug("[video_task] Redis updated: job=%s status=%s pct=%d", job_id, status, progress_percent)
    except Exception as e:
        logger.warning("[video_task] Failed to update Redis for job %s: %s", job_id, e)


@celery_app.task(name="backend.app.tasks.video_task.generate_video_task", bind=True)
def generate_video_task(
    self,
    job_id: str,
    character: str,
    difficulty: str,
    extracted_text: str,
    prompt: Optional[str] = None,
    interests: Optional[list[str]] = None,
    voice_id: Optional[str] = None,
) -> dict:
    """Main Celery task that orchestrates the video generation pipeline."""
    task_t0 = time.perf_counter()

    logger.info("=" * 70)
    logger.info("[video_task] TASK START: %s", job_id)
    logger.info("=" * 70)
    logger.info("[video_task] Character: %s", character)
    logger.info("[video_task] Difficulty: %s", difficulty)
    logger.info("[video_task] Prompt: %s", prompt or "(none)")
    logger.info("[video_task] Interests: %s", ", ".join(interests or []) or "(none)")
    logger.info("[video_task] Extracted text: %d chars", len(extracted_text))
    logger.info("[video_task] Extracted text preview: %.300s...", extracted_text)
    logger.info("[video_task] Celery task ID: %s", self.request.id)

    try:
        # ── Step 1: Generate script ─────────────────────────────────── #
        logger.info("[video_task] ── Step 1: Script Generation ──")
        _update_redis_progress(
            job_id,
            status=JobStatus.GENERATING_SCRIPT.value,
            progress_percent=5,
            current_step="Generating educational script with AI...",
        )

        step_t0 = time.perf_counter()
        from ..services.script_generator import ScriptGenerator

        generator = ScriptGenerator()
        script = generator.generate(
            extracted_text=extracted_text,
            character=Character(character),
            difficulty=Difficulty(difficulty),
            user_prompt=prompt,
            user_interests=interests,
        )
        step_elapsed = time.perf_counter() - step_t0

        logger.info("[video_task] Script generated in %.1fs", step_elapsed)
        logger.info("[video_task]   Title: %s", script.title)
        logger.info("[video_task]   Total scenes: %d", script.total_scenes)
        for i, s in enumerate(script.scenes):
            logger.info(
                "[video_task]   Scene %d: type=%s, duration=%.0fs, narration=%d chars",
                i + 1, s.manim_scene_type, s.duration_hint_seconds,
                len(s.narration_text),
            )

        _update_redis_progress(
            job_id,
            status=JobStatus.RENDERING_ANIMATIONS.value,
            progress_percent=30,
            current_step="Script generated. Rendering animations...",
        )

        # ── Step 2: Build pipeline input ────────────────────────────── #
        logger.info("[video_task] ── Step 2: Building pipeline input ──")
        output_path = f"{settings.STORAGE_PATH}/videos/{job_id}"
        logger.info("[video_task] Output path: %s", output_path)

        pipeline_input = PipelineInput(
            job_id=job_id,
            script=script,
            character=Character(character),
            output_path=output_path,
            voice_id=voice_id,
        )

        logger.info(
            "[video_task] Pipeline input ready: %d scenes, character=%s",
            script.total_scenes, character,
        )

        _update_redis_progress(
            job_id,
            status=JobStatus.RENDERING_ANIMATIONS.value,
            progress_percent=50,
            current_step="Rendering Manim animations...",
        )

        # TODO: Integrate with the actual rendering pipeline
        # For now, we log the pipeline input and mark as completed

        _update_redis_progress(
            job_id,
            status=JobStatus.COMPLETED.value,
            progress_percent=100,
            current_step="Video generation complete.",
        )

        total_elapsed = time.perf_counter() - task_t0
        logger.info("=" * 70)
        logger.info("[video_task] TASK COMPLETE: %s (%.1fs)", job_id, total_elapsed)
        logger.info("=" * 70)

        # Trigger post-processing classification into subject/topic
        from .classify_task import classify_video_task

        classify_video_task.delay(job_id)

        return {
            "job_id": job_id,
            "status": "completed",
            "script": script.model_dump(),
            "pipeline_input": pipeline_input.model_dump(),
        }

    except Exception as e:
        total_elapsed = time.perf_counter() - task_t0
        logger.error("=" * 70)
        logger.error("[video_task] TASK FAILED: %s after %.1fs", job_id, total_elapsed)
        logger.error("[video_task] Error: %s", e)
        logger.error("[video_task] Traceback:\n%s", traceback.format_exc())
        logger.error("=" * 70)
        _update_redis_progress(
            job_id,
            status=JobStatus.FAILED.value,
            progress_percent=0,
            current_step="Failed",
            error_message=str(e),
        )
        raise
