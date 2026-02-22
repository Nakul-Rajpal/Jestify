"""Router for the Video Library endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.contracts.api_types import (
    LibraryResponse,
    SubjectSummary,
    TopicDetailResponse,
    TopicSummary,
    VideoSummary,
)

from ..database import get_db
from ..models.job import Job
from ..models.subject import Subject
from ..models.topic import Topic

router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=LibraryResponse)
async def get_library(
    db: AsyncSession = Depends(get_db),
) -> LibraryResponse:
    """Return all subjects with their topics and video counts, topics sorted by sort_order."""
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.topics))
        .order_by(Subject.name)
    )
    subjects = result.scalars().unique().all()

    subject_summaries = []
    for subject in subjects:
        topic_summaries = []
        total_videos = 0

        for topic in sorted(subject.topics, key=lambda t: t.sort_order):
            count_result = await db.execute(
                select(func.count(Job.id)).where(
                    Job.topic_id == topic.id,
                    Job.status == "completed",
                )
            )
            video_count = count_result.scalar() or 0
            total_videos += video_count

            topic_summaries.append(
                TopicSummary(
                    id=str(topic.id),
                    name=topic.name,
                    description=topic.description,
                    sort_order=topic.sort_order,
                    video_count=video_count,
                )
            )

        subject_summaries.append(
            SubjectSummary(
                id=str(subject.id),
                name=subject.name,
                description=subject.description,
                category=subject.category,
                topic_count=len(topic_summaries),
                video_count=total_videos,
                topics=topic_summaries,
            )
        )

    return LibraryResponse(subjects=subject_summaries)


@router.get("/{subject_id}", response_model=LibraryResponse)
async def get_subject(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return a subject with all its topics and associated videos."""
    try:
        subj_uuid = uuid.UUID(subject_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subject ID format.")

    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.topics))
        .where(Subject.id == subj_uuid)
    )
    subject = result.scalar_one_or_none()

    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found.")

    topic_summaries = []
    all_videos = []

    for topic in sorted(subject.topics, key=lambda t: t.sort_order):
        jobs_result = await db.execute(
            select(Job)
            .where(Job.topic_id == topic.id, Job.status == "completed")
            .order_by(Job.created_at.desc())
        )
        jobs = jobs_result.scalars().all()

        topic_summaries.append(
            TopicSummary(
                id=str(topic.id),
                name=topic.name,
                description=topic.description,
                sort_order=topic.sort_order,
                video_count=len(jobs),
            )
        )

        for job in jobs:
            title = "Untitled Video"
            if job.script_json and "title" in job.script_json:
                title = job.script_json["title"]

            all_videos.append(
                VideoSummary(
                    job_id=str(job.id),
                    title=title,
                    character=job.character,
                    difficulty=job.difficulty,
                    video_url=f"/api/jobs/{job.id}/video",
                    thumbnail_url=(
                        f"/api/jobs/{job.id}/thumbnail" if job.thumbnail_path else None
                    ),
                    created_at=job.created_at,
                )
            )

    return {
        "id": str(subject.id),
        "name": subject.name,
        "description": subject.description,
        "category": subject.category,
        "topics": topic_summaries,
        "videos": all_videos,
    }


@router.get(
    "/{subject_id}/topics/{topic_id}",
    response_model=TopicDetailResponse,
)
async def get_topic_videos(
    subject_id: str,
    topic_id: str,
    db: AsyncSession = Depends(get_db),
) -> TopicDetailResponse:
    """Return all videos for a specific topic."""
    try:
        subj_uuid = uuid.UUID(subject_id)
        topic_uuid = uuid.UUID(topic_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format.")

    subject_result = await db.execute(
        select(Subject).where(Subject.id == subj_uuid)
    )
    subject = subject_result.scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found.")

    topic_result = await db.execute(
        select(Topic).where(
            Topic.id == topic_uuid,
            Topic.subject_id == subj_uuid,
        )
    )
    topic = topic_result.scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found in this subject.")

    jobs_result = await db.execute(
        select(Job)
        .where(Job.topic_id == topic_uuid, Job.status == "completed")
        .order_by(Job.created_at.desc())
    )
    jobs = jobs_result.scalars().all()

    videos = []
    for job in jobs:
        title = "Untitled Video"
        if job.script_json and "title" in job.script_json:
            title = job.script_json["title"]

        videos.append(
            VideoSummary(
                job_id=str(job.id),
                title=title,
                character=job.character,
                difficulty=job.difficulty,
                video_url=f"/api/jobs/{job.id}/video",
                thumbnail_url=(
                    f"/api/jobs/{job.id}/thumbnail" if job.thumbnail_path else None
                ),
                created_at=job.created_at,
            )
        )

    return TopicDetailResponse(
        id=str(topic.id),
        name=topic.name,
        description=topic.description,
        sort_order=topic.sort_order,
        subject_name=subject.name,
        videos=videos,
    )
