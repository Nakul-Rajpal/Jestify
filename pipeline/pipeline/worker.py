"""Celery worker entry point for the video generation pipeline."""

import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── TeX env vars must be set before Celery forks workers ─────────────────── #
# dvisvgm (used by Manim for MathTex) needs both TEXMFCNF (for texmf.cnf)
# and TEXMFDIST (for PostScript headers and font maps) to render LaTeX.
# These must be inherited by the forked process — setting later is unreliable.
def _setup_tex_env() -> None:
    texmf_dist = None
    if "TEXMFCNF" not in os.environ:
        try:
            _kpse = subprocess.run(
                ["kpsewhich", "texmf.cnf"],
                capture_output=True, text=True, timeout=10,
            )
            if _kpse.returncode == 0 and _kpse.stdout.strip():
                cnf_dir = Path(_kpse.stdout.strip()).parent
                os.environ["TEXMFCNF"] = str(cnf_dir) + ":"
                texmf_dist = str(cnf_dir.parent)
        except Exception:
            for _candidate in Path("/opt/homebrew/Cellar/texlive").glob("*/share/texmf-dist/web2c"):
                if (_candidate / "texmf.cnf").exists():
                    os.environ["TEXMFCNF"] = str(_candidate) + ":"
                    texmf_dist = str(_candidate.parent)
                    break
    if "TEXMFDIST" not in os.environ:
        if texmf_dist:
            os.environ["TEXMFDIST"] = texmf_dist
        elif os.environ.get("TEXMFCNF"):
            candidate = str(Path(os.environ["TEXMFCNF"].rstrip(":")).parent)
            if Path(candidate).is_dir():
                os.environ["TEXMFDIST"] = candidate

_setup_tex_env()

if os.environ.get("TEXMFCNF"):
    print(f"[worker] TEXMFCNF={os.environ['TEXMFCNF']} (set at module load)", flush=True)
if os.environ.get("TEXMFDIST"):
    print(f"[worker] TEXMFDIST={os.environ['TEXMFDIST']} (set at module load)", flush=True)

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_PIPELINE_DIR = str(Path(__file__).resolve().parents[1])
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)

from celery import Celery

from shared.contracts.enums import Character, Difficulty, JobStatus
from shared.contracts.pipeline_schema import PipelineInput
from pipeline.config import REDIS_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

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
        logger.debug("[worker] Redis progress updated: job=%s status=%s pct=%d", job_id, status, progress_percent)
    except Exception as e:
        logger.warning("[worker] Failed to update Redis progress for job %s: %s", job_id, e)


@app.task(bind=True, name="backend.app.tasks.video_task.generate_video_task")
def generate_video_task(
    self,
    job_id: str,
    character: str,
    difficulty: str,
    extracted_text: str,
    prompt: Optional[str] = None,
):
    """Main Celery task picked up by the pipeline worker."""
    task_t0 = time.perf_counter()

    logger.info("=" * 70)
    logger.info("[worker] JOB START: %s", job_id)
    logger.info("=" * 70)
    logger.info("[worker] Character: %s", character)
    logger.info("[worker] Difficulty: %s", difficulty)
    logger.info("[worker] Prompt: %s", prompt or "(none)")
    logger.info("[worker] Extracted text: %d chars", len(extracted_text))
    logger.info("[worker] Extracted text preview: %.300s...", extracted_text)
    logger.info("[worker] Celery task ID: %s", self.request.id)
    logger.info("[worker] Python: %s", sys.executable)
    logger.info("[worker] CWD: %s", os.getcwd())
    logger.info("[worker] REDIS_URL: %s", REDIS_URL[:30] + "...")

    try:
        # ── Step 1: Generate script ─────────────────────────────────── #
        logger.info("[worker] ── Step 1/3: Generating script with Claude ──")
        _update_redis_progress(
            job_id,
            status=JobStatus.GENERATING_SCRIPT.value,
            progress_percent=10,
            current_step="Generating educational script with AI...",
        )

        step_t0 = time.perf_counter()
        from backend.app.services.script_generator import ScriptGenerator

        generator = ScriptGenerator()
        script = generator.generate(
            extracted_text=extracted_text,
            character=Character(character),
            difficulty=Difficulty(difficulty),
            user_prompt=prompt,
        )
        step_elapsed = time.perf_counter() - step_t0

        logger.info("[worker] Script generated in %.1fs", step_elapsed)
        logger.info("[worker]   Title: %s", script.title)
        logger.info("[worker]   Total scenes: %d", script.total_scenes)
        for i, s in enumerate(script.scenes):
            has_code = bool(s.manim_code)
            code_len = len(s.manim_code) if s.manim_code else 0
            logger.info(
                "[worker]   Scene %d: type=%s, duration=%.0fs, narration=%d chars, has_code=%s (%d chars)",
                i + 1, s.manim_scene_type, s.duration_hint_seconds,
                len(s.narration_text), has_code, code_len,
            )

        # ── Step 2: Build pipeline input ────────────────────────────── #
        logger.info("[worker] ── Step 2/3: Building pipeline input ──")
        _update_redis_progress(
            job_id,
            status=JobStatus.RENDERING_ANIMATIONS.value,
            progress_percent=20,
            current_step="Script generated. Starting animation rendering...",
        )

        from pipeline.config import STORAGE_PATH
        output_path = f"{STORAGE_PATH}/videos/{job_id}/final.mp4"
        logger.info("[worker] Output path: %s", output_path)
        logger.info("[worker] Storage path: %s", STORAGE_PATH)

        pipeline_input = PipelineInput(
            job_id=job_id,
            script=script,
            character=Character(character),
            output_path=output_path,
        )

        # ── Step 3: Run pipeline ────────────────────────────────────── #
        logger.info("[worker] ── Step 3/3: Running rendering pipeline ──")
        from pipeline.orchestrator import PipelineOrchestrator

        def _on_progress(status: JobStatus, progress_pct: int):
            step_messages = {
                JobStatus.RENDERING_ANIMATIONS: "Rendering animations...",
                JobStatus.SYNTHESIZING_VOICE: "Synthesizing character voice...",
                JobStatus.COMPOSITING: "Compositing character overlay...",
                JobStatus.ASSEMBLING: "Assembling final video...",
            }
            msg = step_messages.get(status, "Processing...")
            logger.info("[worker] Progress: %s %d%% — %s", status.value, progress_pct, msg)
            _update_redis_progress(
                job_id,
                status=status.value,
                progress_percent=progress_pct,
                current_step=msg,
            )

        orchestrator = PipelineOrchestrator(status_callback=_on_progress)
        output = orchestrator.run(pipeline_input)

        # ── Done ────────────────────────────────────────────────────── #
        _update_redis_progress(
            job_id,
            status=JobStatus.COMPLETED.value,
            progress_percent=100,
            current_step="Video generation complete.",
            video_url=f"/api/jobs/{job_id}/video",
        )

        total_elapsed = time.perf_counter() - task_t0
        logger.info("=" * 70)
        logger.info(
            "[worker] JOB COMPLETE: %s — %s (%.1fs total)",
            job_id, output.video_path, total_elapsed,
        )
        logger.info("[worker] Duration: %.1fs", output.duration_seconds)
        logger.info("=" * 70)

        return {
            "job_id": job_id,
            "status": "completed",
            "video_path": output.video_path,
            "duration_seconds": output.duration_seconds,
        }

    except Exception as e:
        total_elapsed = time.perf_counter() - task_t0
        logger.error("=" * 70)
        logger.error("[worker] JOB FAILED: %s after %.1fs", job_id, total_elapsed)
        logger.error("[worker] Error: %s", e)
        logger.error("[worker] Traceback:\n%s", traceback.format_exc())
        logger.error("=" * 70)
        _update_redis_progress(
            job_id,
            status=JobStatus.FAILED.value,
            progress_percent=0,
            current_step="Failed",
            error_message=str(e),
        )
        raise
