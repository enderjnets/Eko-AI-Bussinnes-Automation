from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "eko_ai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.scheduled",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Denver",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    # Beat schedule
    beat_schedule={
        "process-follow-ups-every-hour": {
            "task": "app.tasks.scheduled.process_follow_ups",
            "schedule": 3600.0,  # 1 hour
        },
        "enrich-pending-leads-every-30-min": {
            "task": "app.tasks.scheduled.enrich_pending_leads",
            "schedule": 1800.0,  # 30 minutes
        },
        "sync-dnc-registry-monthly": {
            "task": "app.tasks.scheduled.sync_dnc_registry",
            "schedule": crontab(day_of_month=1, hour=2, minute=0),
        },
        "generate-daily-report": {
            "task": "app.tasks.scheduled.generate_daily_report",
            "schedule": crontab(hour=8, minute=0),  # 8am MT
        },
    },
)
