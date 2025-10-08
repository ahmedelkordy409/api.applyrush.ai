"""
Celery configuration for JobHire.AI
Handles background task processing for auto-apply system
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "jobhire-ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.job_tasks",
        "app.workers.application_tasks",
        "app.workers.notification_tasks",
        "app.workers.analytics_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing
    task_routes={
        "app.workers.job_tasks.*": {"queue": "jobs"},
        "app.workers.application_tasks.*": {"queue": "applications"},
        "app.workers.notification_tasks.*": {"queue": "notifications"},
        "app.workers.analytics_tasks.*": {"queue": "analytics"},
    },
    
    # Task execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_backend_transport_options={"master_name": "mymaster"},
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Rate limiting
    task_annotations={
        "*": {"rate_limit": "100/m"},  # Global rate limit
        "app.workers.job_tasks.fetch_jobs": {"rate_limit": "10/m"},
        "app.workers.application_tasks.submit_application": {"rate_limit": "5/m"},
    },
    
    # Beat scheduler for periodic tasks
    beat_schedule={
        # Job fetching tasks
        "fetch-trending-jobs": {
            "task": "app.workers.job_tasks.fetch_trending_jobs",
            "schedule": crontab(minute=0, hour="*/2"),  # Every 2 hours
        },
        "refresh-job-cache": {
            "task": "app.workers.job_tasks.refresh_job_cache",
            "schedule": crontab(minute=30, hour="*/4"),  # Every 4 hours at :30
        },
        
        # Application processing
        "process-auto-apply-queue": {
            "task": "app.workers.application_tasks.process_auto_apply_queue",
            "schedule": crontab(minute="*/10"),  # Every 10 minutes
        },
        "update-application-statuses": {
            "task": "app.workers.application_tasks.update_application_statuses",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        },
        
        # Analytics and monitoring
        "calculate-user-analytics": {
            "task": "app.workers.analytics_tasks.calculate_user_analytics",
            "schedule": crontab(minute=0, hour=2),  # Daily at 2 AM
        },
        "cleanup-old-data": {
            "task": "app.workers.analytics_tasks.cleanup_old_data", 
            "schedule": crontab(minute=0, hour=3, day_of_week=0),  # Weekly on Sunday
        },
        
        # Notifications
        "send-daily-digest": {
            "task": "app.workers.notification_tasks.send_daily_digest",
            "schedule": crontab(minute=0, hour=9),  # Daily at 9 AM
        },
    },
)


# Task retry configuration
celery_app.conf.task_default_retry_delay = 60  # 1 minute
celery_app.conf.task_max_retries = 3


if __name__ == "__main__":
    celery_app.start()