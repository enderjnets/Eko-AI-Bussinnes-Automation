from celery import Celery
from celery.signals import worker_process_init
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


@worker_process_init.connect
def init_worker_process(**kwargs):
    """Recreate the SQLAlchemy engine in each forked worker process.
    This prevents 'Future attached to a different loop' errors because
    asyncpg connections created in the parent process are not safe to use
    in forked children.
    """
    from app.db.base import recreate_engine
    recreate_engine()

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
        "execute-sequences-every-hour": {
            "task": "app.tasks.scheduled.execute_sequences",
            "schedule": 3600.0,  # 1 hour
        },
        "remind-scheduled-calls-daily": {
            "task": "app.tasks.scheduled.remind_scheduled_calls",
            "schedule": crontab(hour=9, minute=0),  # 9am MT
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
        "backup-database-daily": {
            "task": "app.tasks.scheduled.backup_database",
            "schedule": crontab(hour=3, minute=0),  # 3am MT
        },
        "backup-processed-leads-every-2h": {
            "task": "app.tasks.scheduled.backup_processed_leads",
            "schedule": 7200.0,  # every 2 hours
        },
    },
)
