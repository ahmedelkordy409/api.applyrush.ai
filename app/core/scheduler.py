"""
Job Scheduler Configuration
Uses APScheduler for background job execution
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from app.services.background_jobs import background_job_service

logger = logging.getLogger(__name__)

# Create scheduler instance
scheduler = AsyncIOScheduler()


def start_scheduler():
    """Start the background job scheduler"""

    # Job 1: Find matches for active users - Every 30 minutes
    scheduler.add_job(
        background_job_service.find_matches_for_active_users,
        trigger=IntervalTrigger(minutes=30),
        id="find_matches",
        name="Find job matches for active users",
        replace_existing=True,
        max_instances=1
    )
    logger.info("Scheduled: Find matches job (every 30 minutes)")

    # Job 2: Process auto-apply queue - Every 5 minutes
    scheduler.add_job(
        background_job_service.process_auto_apply_queue,
        trigger=IntervalTrigger(minutes=5),
        id="auto_apply",
        name="Process auto-apply queue",
        replace_existing=True,
        max_instances=1
    )
    logger.info("Scheduled: Auto-apply job (every 5 minutes)")

    # Job 3: Cleanup expired queue items - Every hour
    scheduler.add_job(
        background_job_service.cleanup_expired_queue_items,
        trigger=IntervalTrigger(hours=1),
        id="cleanup_expired",
        name="Cleanup expired queue items",
        replace_existing=True,
        max_instances=1
    )
    logger.info("Scheduled: Cleanup job (every hour)")

    # Job 4: Update stats - Every 15 minutes
    scheduler.add_job(
        background_job_service.update_application_stats,
        trigger=IntervalTrigger(minutes=15),
        id="update_stats",
        name="Update application statistics",
        replace_existing=True,
        max_instances=1
    )
    logger.info("Scheduled: Stats update job (every 15 minutes)")

    # Start the scheduler
    scheduler.start()
    logger.info("Background job scheduler started successfully")


def stop_scheduler():
    """Stop the background job scheduler"""
    scheduler.shutdown(wait=True)
    logger.info("Background job scheduler stopped")


def get_scheduler_status():
    """Get status of all scheduled jobs"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    return jobs
