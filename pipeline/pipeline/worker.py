"""Celery worker entry point for the video generation pipeline."""

import json
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path so shared.contracts is importable.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Also ensure pipeline/ dir is on sys.path so 'pipeline' package is importable
# when running celery from the pipeline/ directory.
_PIPELINE_DIR = str(Path(__file__).resolve().parents[1])
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)

from celery import Celery

from shared.contracts.enums import JobStatus
from shared.contracts.pipeline_schema import PipelineInput, PipelineOutput
from pipeline.config import REDIS_URL
from pipeline.orchestrator import PipelineOrchestrator

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
    """Return a Redis client (lazy import to avoid hard dep at module level)."""
    import redis
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _set_job_status(job_id: str, status: JobStatus, extra: dict | None = None):
    """Persist job status and optional metadata into Redis."""
    r = _redis_client()
    payload = {"status": status.value}
    if extra:
        payload.update(extra)
    r.hset(f"job:{job_id}", mapping=payload)


# --------------------------------------------------------------------------- #
# Celery task
# --------------------------------------------------------------------------- #

@app.task(bind=True, name="pipeline.generate_video")
def generate_video_task(self, job_id: str, pipeline_input_json: str):
    """Main Celery task: receives a job and drives the full pipeline.

    Parameters
    ----------
    job_id : str
        Unique identifier for this generation job.
    pipeline_input_json : str
        JSON-serialised ``PipelineInput`` object.
    """
    logger.info("Starting pipeline for job %s", job_id)

    # --- deserialise -------------------------------------------------------
    try:
        pipeline_input = PipelineInput.model_validate_json(pipeline_input_json)
    except Exception as exc:
        logger.exception("Failed to deserialise PipelineInput for job %s", job_id)
        _set_job_status(job_id, JobStatus.FAILED, {"error": str(exc)})
        raise

    # --- progress callback -------------------------------------------------
    def _on_progress(status: JobStatus, progress_pct: int):
        _set_job_status(
            job_id,
            status,
            {"progress": progress_pct},
        )

    # --- run orchestrator --------------------------------------------------
    orchestrator = PipelineOrchestrator(status_callback=_on_progress)

    try:
        output: PipelineOutput = orchestrator.run(pipeline_input)
    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        _set_job_status(job_id, JobStatus.FAILED, {"error": str(exc)})
        raise

    # --- persist result ----------------------------------------------------
    _set_job_status(
        job_id,
        JobStatus.COMPLETED,
        {
            "progress": 100,
            "video_path": output.video_path,
            "duration_seconds": str(output.duration_seconds),
        },
    )
    logger.info("Pipeline completed for job %s -> %s", job_id, output.video_path)

    return output.model_dump()
