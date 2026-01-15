"""
Global Celery application instance.
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND_URL,
    include=["app.modules.tenderiq.analyze.tasks"]  # Auto-discover tasks from this module
)

celery_app.conf.update(
    task_track_started=True,
)
