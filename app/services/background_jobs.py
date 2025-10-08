"""
Background Jobs Service
Handles automated job matching, auto-apply, and queue processing
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database_new import get_async_db
from app.services.job_matcher_service import job_matcher_service

logger = logging.getLogger(__name__)


class BackgroundJobService:
    """Service for background job processing"""

    def __init__(self):
        self.matcher = job_matcher_service

    async def find_matches_for_active_users(self):
        """Find job matches for all active users"""
        try:
            from app.core.database_new import MongoDB
            db = MongoDB.get_async_db()

            # Get all users with active search
            active_users = await db.users.find({
                "preferences.search_active": True
            }).to_list(length=None)

            logger.info(f"Finding matches for {len(active_users)} active users")

            for user in active_users:
                try:
                    await self._process_user_matches(db, user)
                except Exception as e:
                    logger.error(f"Error processing matches for user {user['_id']}: {e}")
                    continue

            logger.info("Completed finding matches for all active users")

        except Exception as e:
            logger.error(f"Error in find_matches_for_active_users: {e}")

    async def _process_user_matches(self, db: AsyncIOMotorDatabase, user: Dict[str, Any]):
        """Process job matches for a single user"""
        user_id = str(user["_id"])

        # Get user preferences
        preferences = user.get("preferences", {})
        match_threshold = preferences.get("match_threshold", "good-fit")

        # Convert match threshold to score
        threshold_map = {
            "open": 60,
            "good-fit": 70,
            "top": 85
        }
        min_score = threshold_map.get(match_threshold, 70)

        logger.info(f"Processing matches for user {user_id} with preferences: {preferences}")

        # Get real jobs from database (scraped from job boards)
        jobs_cursor = db.jobs.find({
            "is_active": True
        }).sort("created_at", -1).limit(100)  # Get latest 100 jobs

        jobs = await jobs_cursor.to_list(length=100)

        # Match jobs for user
        for job in jobs:
            try:
                job_id = str(job["_id"])

                # DUPLICATE CHECK 1: Check if job already exists in queue
                existing_queue = await db.application_queue.find_one({
                    "user_id": ObjectId(user_id),
                    "job_id": ObjectId(job_id)
                })

                if existing_queue:
                    logger.debug(f"Job {job_id} already in queue for user {user_id}")
                    continue

                # DUPLICATE CHECK 2: Check if already applied to this job
                existing_application = await db.applications.find_one({
                    "user_id": ObjectId(user_id),
                    "job_id": ObjectId(job_id)
                })

                if existing_application:
                    logger.debug(f"User {user_id} already applied to job {job_id}")
                    continue

                # Check hard filters first
                passes_filters, filter_reason = self.matcher.passes_user_filters(user, job)
                if not passes_filters:
                    logger.debug(f"Job {job_id} filtered out: {filter_reason}")
                    continue

                # Calculate match score using collected user data
                match_result = await self.matcher.calculate_match_score(user, job)
                match_score = match_result["score"]
                match_reasons = match_result["reasons"]

                if match_score >= min_score:
                    # Convert job _id to job_id for queue
                    job_for_queue = job.copy()
                    job_for_queue["id"] = job_id

                    # Add to queue
                    queue_item = {
                        "user_id": ObjectId(user_id),
                        "job_id": ObjectId(job_id),
                        "status": "pending",
                        "match_score": match_score,
                        "match_reasons": match_reasons,
                        "match_breakdown": match_result.get("breakdown", {}),
                        "job": job_for_queue,
                        "created_at": datetime.utcnow(),
                        "expires_at": datetime.utcnow() + timedelta(days=7)
                    }

                    # Set auto-apply time based on approval mode
                    approval_mode = preferences.get("approval_mode", "approval")
                    if approval_mode == "instant":
                        queue_item["auto_apply_after"] = datetime.utcnow()
                        queue_item["status"] = "approved"
                    elif approval_mode == "delayed":
                        delay_hours = preferences.get("auto_apply_delay", 24)
                        queue_item["auto_apply_after"] = datetime.utcnow() + timedelta(hours=delay_hours)

                    await db.application_queue.insert_one(queue_item)
                    logger.info(f"Added job {job_id} to queue for user {user_id} (score: {match_score})")

            except Exception as e:
                logger.error(f"Error matching job {job.get('_id')} for user {user_id}: {e}")
                continue

    async def process_auto_apply_queue(self):
        """Process auto-apply queue for approved applications"""
        try:
            from app.core.database_new import MongoDB
            db = MongoDB.get_async_db()

            # Get applications ready for auto-apply
            now = datetime.utcnow()
            ready_applications = await db.application_queue.find({
                "status": "approved",
                "auto_apply_after": {"$lte": now}
            }).to_list(length=100)

            logger.info(f"Processing {len(ready_applications)} applications for auto-apply")

            for app in ready_applications:
                try:
                    await self._auto_apply_application(db, app)
                except Exception as e:
                    logger.error(f"Error auto-applying application {app['_id']}: {e}")
                    continue

            logger.info("Completed processing auto-apply queue")

        except Exception as e:
            logger.error(f"Error in process_auto_apply_queue: {e}")

    def _can_apply_via_email(self, job: Dict[str, Any]) -> bool:
        """Check if job supports email application"""
        # Check for email application fields
        email_fields = ['apply_email', 'application_email', 'contact_email', 'email']

        for field in email_fields:
            if job.get(field):
                return True

        # Check if apply_url is a mailto: link
        apply_url = job.get('apply_url', '')
        if apply_url.startswith('mailto:'):
            return True

        return False

    async def _auto_apply_application(self, db: AsyncIOMotorDatabase, queue_item: Dict[str, Any]):
        """Auto-apply to a single job"""
        try:
            user_id = queue_item["user_id"]
            job = queue_item["job"]
            job_id = job.get("id")

            # CRITICAL: Check if already applied to prevent duplicates
            existing_application = await db.applications.find_one({
                "user_id": ObjectId(user_id),
                "job_id": job_id
            })

            if existing_application:
                logger.warning(f"DUPLICATE PREVENTED: User {user_id} already applied to job {job_id}")
                # Remove from queue since already applied
                await db.application_queue.delete_one({"_id": queue_item["_id"]})
                return

            # Get user data
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                logger.error(f"User {user_id} not found")
                return

            # Get user's resume
            resume = await db.resumes.find_one({
                "user_id": user_id,
                "is_primary": True
            })

            # Generate cover letter if enabled
            cover_letter = None
            try:
                if user.get("preferences", {}).get("ai_features", {}).get("cover_letters", True):
                    from app.services.ai_client import AIClient
                    ai_client = AIClient()

                    # Generate cover letter prompt
                    profile = user.get("profile", {})
                    prompt = f"""Write a professional cover letter for this job application:

Job: {job.get('title', '')} at {job.get('company', '')}
Job Description: {job.get('description', '')[:500]}

Candidate: {profile.get('first_name', '')} {profile.get('last_name', '')}
Skills: {', '.join(profile.get('skills', []))}
Experience: {profile.get('years_of_experience', 0)} years

Write a concise, professional cover letter (3-4 paragraphs)."""

                    cover_letter = await ai_client.generate_text(prompt, max_tokens=500, temperature=0.7)
            except Exception as e:
                logger.warning(f"Failed to generate cover letter: {e}")
                cover_letter = None

            # Try to apply via email if job has application email
            application_result = None
            application_method = "database_only"

            # Check if job has email application method
            if self._can_apply_via_email(job):
                from app.services.job_application_email_service import send_job_application_email

                # Get resume file path
                resume_path = None
                if resume:
                    resume_path = resume.get("file_path")

                # Send actual email application
                application_result = await send_job_application_email(
                    db=db,
                    user_id=str(user_id),
                    job_data=job,
                    resume_path=resume_path,
                    cover_letter=cover_letter
                )

                if application_result.get("success"):
                    application_method = "email"
                    logger.info(f"Successfully sent email application for job {job['id']}")
                else:
                    logger.warning(f"Failed to send email application: {application_result.get('error')}")

            # Create application record with match score and details
            application = {
                "user_id": user_id,
                "job_id": job["id"],
                "job": job,
                "job_title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "status": "applied",
                "source": "auto_apply",
                "application_method": application_method,
                "application_result": application_result,
                "cover_letter": cover_letter,
                "resume_version": resume.get("version") if resume else None,
                "forwarding_email": application_result.get("forwarding_email") if application_result else None,
                # Add match score and reasons from queue item
                "match_score": queue_item.get("match_score", 0),
                "match_reasons": queue_item.get("match_reasons", []),
                "match_breakdown": queue_item.get("match_breakdown", {}),
                "applied_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await db.applications.insert_one(application)

            # Update queue status
            await db.application_queue.update_one(
                {"_id": queue_item["_id"]},
                {
                    "$set": {
                        "status": "auto_applied",
                        "application_id": str(result.inserted_id),
                        "application_method": application_method,
                        "applied_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Auto-applied to job {job['id']} for user {user_id} via {application_method}")

        except Exception as e:
            logger.error(f"Error in _auto_apply_application: {e}")
            # Update queue with error status
            await db.application_queue.update_one(
                {"_id": queue_item["_id"]},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(e),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

    async def cleanup_expired_queue_items(self):
        """Clean up expired queue items"""
        try:
            from app.core.database_new import MongoDB
            db = MongoDB.get_async_db()

            result = await db.application_queue.update_many(
                {
                    "status": "pending",
                    "expires_at": {"$lt": datetime.utcnow()}
                },
                {
                    "$set": {
                        "status": "expired",
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Marked {result.modified_count} queue items as expired")

        except Exception as e:
            logger.error(f"Error in cleanup_expired_queue_items: {e}")

    async def update_application_stats(self):
        """Update application statistics for all users"""
        try:
            from app.core.database_new import MongoDB
            db = MongoDB.get_async_db()

            # This would update various stats in the database
            # For now, just log
            logger.info("Updated application stats")

        except Exception as e:
            logger.error(f"Error in update_application_stats: {e}")


# Singleton instance
background_job_service = BackgroundJobService()
