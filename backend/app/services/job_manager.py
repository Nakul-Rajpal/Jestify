"""Service for CRUD operations on Job records, with Redis caching for live progress."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.job import Job
from ..models.document import Document

logger = logging.getLogger(__name__)


class JobManager:
    """Manages Job lifecycle: creation, updates, and retrieval."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_job(
        self,
        character: str,
        difficulty: str,
        prompt: Optional[str],
        documents: list[Document],
    ) -> Job:
        """
        Create a new Job record and associate it with the given documents.

        Args:
            character: Character enum value.
            difficulty: Difficulty enum value.
            prompt: Optional user prompt.
            documents: List of Document model instances to associate.

        Returns:
            The created Job instance.
        """
        job = Job(
            id=uuid.uuid4(),
            status="pending",
            progress_percent=0,
            current_step="pending",
            character=character,
            difficulty=difficulty,
            prompt=prompt,
        )
        job.documents = documents
        self.db.add(job)
        await self.db.flush()
        logger.info(f"Created job {job.id} for character={character}, difficulty={difficulty}")
        return job

    async def update_job_status(
        self,
        job_id: uuid.UUID,
        status: Optional[str] = None,
        progress_percent: Optional[int] = None,
        current_step: Optional[str] = None,
        script_json: Optional[dict] = None,
        video_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Job]:
        """
        Update fields on an existing Job record.

        Args:
            job_id: UUID of the job to update.
            status: New status string.
            progress_percent: New progress percentage (0-100).
            current_step: Description of the current pipeline step.
            script_json: Generated script as a dict.
            video_path: Path to the rendered video file.
            thumbnail_path: Path to the video thumbnail.
            error_message: Error message if the job failed.

        Returns:
            The updated Job instance, or None if not found.
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if job is None:
            logger.warning(f"Attempted to update non-existent job {job_id}")
            return None

        if status is not None:
            job.status = status
        if progress_percent is not None:
            job.progress_percent = progress_percent
        if current_step is not None:
            job.current_step = current_step
        if script_json is not None:
            job.script_json = script_json
        if video_path is not None:
            job.video_path = video_path
        if thumbnail_path is not None:
            job.thumbnail_path = thumbnail_path
        if error_message is not None:
            job.error_message = error_message

        job.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(f"Updated job {job_id}: status={status}, progress={progress_percent}%")
        return job

    async def get_job(self, job_id: uuid.UUID) -> Optional[Job]:
        """
        Retrieve a Job by its UUID.

        Args:
            job_id: UUID of the job.

        Returns:
            The Job instance, or None if not found.
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def get_job_from_redis(self, job_id: str) -> Optional[dict]:
        """
        Attempt to read live job progress from Redis.

        Args:
            job_id: String UUID of the job.

        Returns:
            A dict with job status data, or None if not cached in Redis.
        """
        try:
            import redis.asyncio as aioredis
            from ..config import settings

            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            data = await r.get(f"job:{job_id}")
            await r.aclose()

            if data:
                return json.loads(data)
        except Exception as e:
            logger.debug(f"Redis lookup failed for job {job_id}: {e}")

        return None
