"""
Celery tasks for automated job applications
Background processing for auto-apply functionality
"""

from celery import shared_task
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def auto_apply_to_job_task(self, user_id: str, job_id: str, job_url: str, config: Dict[str, Any] = None):
    """
    Apply to a single job in the background

    Args:
        user_id: User ID
        job_id: Job ID
        job_url: Job posting URL
        config: Optional configuration for applicator
    """
    try:
        from app.services.auto_apply.greenhouse_applicator import GreenhouseApplicator
        from app.services.auto_apply.email_applicator import EmailApplicator
        from app.core.mongodb import get_database
        import asyncio

        async def apply_async():
            db = await get_database()

            # Get user profile
            user_profile = await db.users.find_one({"_id": user_id})
            if not user_profile:
                raise ValueError(f"User {user_id} not found")

            # Prepare user data
            user_data = {
                'user_id': str(user_id),
                'job_id': job_id,
                'first_name': user_profile.get('first_name', ''),
                'last_name': user_profile.get('last_name', ''),
                'email': user_profile.get('email', ''),
                'phone': user_profile.get('phone', ''),
                'linkedin_url': user_profile.get('linkedin_url', ''),
                'location': user_profile.get('location', ''),
            }

            # Select applicator
            if 'greenhouse' in job_url.lower():
                applicator = GreenhouseApplicator(config=config or {
                    'email_forwarding_enabled': True,
                    'headless': True
                })
            else:
                applicator = EmailApplicator(config=config or {})

            # Apply
            resume_path = user_profile.get('resume_path', '/tmp/resume.pdf')
            result = await applicator.apply(
                job_url=job_url,
                user_data=user_data,
                resume_path=resume_path
            )

            # Save to database
            application_doc = {
                'user_id': str(user_id),
                'job_id': job_id,
                'job_url': job_url,
                'application_method': 'browser_automation',
                'ats_type': result.ats_type.value,
                'status': result.status.value,
                'forwarding_email': result.confirmation_email,
                'confirmation_number': result.confirmation_number,
                'submitted_at': result.submitted_at,
                'created_at': datetime.utcnow()
            }

            await db.auto_apply_applications.insert_one(application_doc)

            return result.to_dict()

        # Run async function
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(apply_async())

        logger.info(f"Auto-apply completed for user {user_id}, job {job_id}")
        return result

    except Exception as e:
        logger.error(f"Auto-apply task failed: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@shared_task
def batch_auto_apply_task(user_id: str, max_applications: int = 10):
    """
    Apply to multiple matched jobs for a user

    Args:
        user_id: User ID
        max_applications: Maximum number of applications to submit
    """
    try:
        from app.core.mongodb import get_database
        import asyncio

        async def batch_apply_async():
            db = await get_database()

            # Get user settings
            user = await db.users.find_one({"_id": user_id})
            if not user:
                return {"error": "User not found"}

            settings = user.get('settings', {})
            if not settings.get('browserAutoApply', False):
                return {"skipped": "Browser auto-apply not enabled"}

            # Get matched jobs that haven't been applied to
            matched_jobs = await db.job_matches.find({
                "user_id": user_id,
                "overall_score": {"$gte": 70},
                "applied": {"$ne": True}
            }).limit(max_applications).to_list(length=max_applications)

            results = []
            for match in matched_jobs:
                # Queue individual apply task
                task = auto_apply_to_job_task.delay(
                    user_id=user_id,
                    job_id=match['job_id'],
                    job_url=match['job_url']
                )

                results.append({
                    "job_id": match['job_id'],
                    "task_id": task.id,
                    "status": "queued"
                })

                # Mark as applied
                await db.job_matches.update_one(
                    {"_id": match['_id']},
                    {"$set": {"applied": True, "applied_at": datetime.utcnow()}}
                )

            return {
                "user_id": user_id,
                "applications_queued": len(results),
                "results": results
            }

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(batch_apply_async())

        logger.info(f"Batch auto-apply completed for user {user_id}")
        return result

    except Exception as e:
        logger.error(f"Batch auto-apply failed: {str(e)}")
        return {"error": str(e)}


@shared_task
def process_email_webhook_task(email_data: Dict[str, Any]):
    """
    Process incoming email webhook

    Args:
        email_data: Email data from webhook
    """
    try:
        from app.services.email_forwarder.forwarder_service import EmailForwarderService
        import asyncio

        async def process_email_async():
            forwarder = EmailForwarderService()

            result = await forwarder.process_incoming_email(
                forwarding_address=email_data.get('to'),
                from_address=email_data.get('from'),
                subject=email_data.get('subject'),
                body=email_data.get('body'),
                html_body=email_data.get('html_body')
            )

            return result

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(process_email_async())

        logger.info(f"Email webhook processed: {result}")
        return result

    except Exception as e:
        logger.error(f"Email webhook processing failed: {str(e)}")
        return {"error": str(e)}


@shared_task
def cleanup_expired_forwarding_emails_task():
    """
    Clean up expired forwarding email addresses

    Runs daily to disable expired forwarding emails
    """
    try:
        from app.core.mongodb import get_database
        import asyncio

        async def cleanup_async():
            db = await get_database()

            # Find expired forwarding emails
            now = datetime.utcnow()
            result = await db.forwarding_emails.update_many(
                {
                    "expires_at": {"$lt": now},
                    "status": "active"
                },
                {
                    "$set": {
                        "status": "expired",
                        "updated_at": now
                    }
                }
            )

            return {
                "expired_count": result.modified_count,
                "timestamp": now.isoformat()
            }

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(cleanup_async())

        logger.info(f"Cleanup completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        return {"error": str(e)}


@shared_task
def daily_auto_apply_for_all_users_task():
    """
    Run auto-apply for all users with auto-apply enabled

    Scheduled to run daily
    """
    try:
        from app.core.mongodb import get_database
        import asyncio

        async def daily_apply_async():
            db = await get_database()

            # Find users with auto-apply enabled
            users = await db.users.find({
                "settings.browserAutoApply": True,
                "settings.approvalMode": {"$in": ["instant", "delayed"]}
            }).to_list(length=1000)

            results = []
            for user in users:
                # Queue batch apply task for each user
                task = batch_auto_apply_task.delay(
                    user_id=str(user['_id']),
                    max_applications=10
                )

                results.append({
                    "user_id": str(user['_id']),
                    "task_id": task.id
                })

            return {
                "users_processed": len(results),
                "results": results
            }

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(daily_apply_async())

        logger.info(f"Daily auto-apply completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Daily auto-apply failed: {str(e)}")
        return {"error": str(e)}


__all__ = [
    "auto_apply_to_job_task",
    "batch_auto_apply_task",
    "process_email_webhook_task",
    "cleanup_expired_forwarding_emails_task",
    "daily_auto_apply_for_all_users_task"
]
