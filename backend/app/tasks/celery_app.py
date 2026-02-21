"""Celery application instance and configuration."""

from celery import Celery

from ..config import settings

celery_app = Celery(
    "jestify",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "backend.app.tasks.video_task.generate_video_task": {"queue": "video_pipeline"},
        "backend.app.tasks.classify_task.classify_video_task": {"queue": "celery"},
    },

    # Task behavior
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result expiration (24 hours)
    result_expires=86400,
)

# Auto-discover tasks in the tasks package
celery_app.autodiscover_tasks(["backend.app.tasks"])
