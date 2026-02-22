"""Celery task for classifying completed videos into subjects and topics."""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="backend.app.tasks.classify_task.classify_video_task",
    bind=True,
)
def classify_video_task(self, job_id: str) -> dict:
    """
    Post-processing task: classify a completed video into a subject and topic.

    Creates its own async database session and runs the TopicClassifier.
    """
    logger.info(f"Starting classification for job {job_id}")

    async def _do_classify():
        from ..database import async_session_factory
        from ..models.job import Job
        from ..services.topic_classifier import TopicClassifier

        async with async_session_factory() as session:
            try:
                result = await session.execute(
                    select(Job)
                    .options(selectinload(Job.documents))
                    .where(Job.id == uuid.UUID(job_id))
                )
                job = result.scalar_one_or_none()

                if job is None:
                    logger.warning(f"Job {job_id} not found for classification")
                    return {"job_id": job_id, "classified": False, "reason": "not_found"}

                if job.status != "completed":
                    logger.warning(f"Job {job_id} not completed, status={job.status}")
                    return {"job_id": job_id, "classified": False, "reason": "not_completed"}

                classifier = TopicClassifier(session)
                topic = await classifier.classify_job(job)

                await session.commit()

                if topic:
                    return {
                        "job_id": job_id,
                        "classified": True,
                        "subject_id": str(topic.subject_id),
                        "topic_id": str(topic.id),
                        "topic_name": topic.name,
                    }
                else:
                    return {
                        "job_id": job_id,
                        "classified": False,
                        "reason": "classification_failed",
                    }

            except Exception as e:
                await session.rollback()
                logger.error(f"Classification failed for job {job_id}: {e}", exc_info=True)
                return {"job_id": job_id, "classified": False, "reason": str(e)}

    return asyncio.run(_do_classify())
