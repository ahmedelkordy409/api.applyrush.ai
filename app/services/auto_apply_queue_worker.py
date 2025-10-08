"""
Auto-Apply Queue Worker
Processes applications from the queue one by one
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId

from app.core.database_new import get_async_db

logger = logging.getLogger(__name__)


class AutoApplyQueueWorker:
    """Background worker that processes auto-apply queue"""

    def __init__(self):
        self.is_running = False
        self.current_task = None
        self.processed_count = 0
        self.failed_count = 0
        self.bot_manager = None  # Initialize bot manager on first use

    async def start(self):
        """Start the queue worker"""
        if self.is_running:
            logger.warning("Queue worker is already running")
            return

        self.is_running = True
        logger.info("🚀 Auto-apply queue worker started")

        try:
            while self.is_running:
                await self.process_next_item()
                # Wait before checking for next item
                await asyncio.sleep(5)  # Check every 5 seconds
        except Exception as e:
            logger.error(f"❌ Queue worker error: {e}")
            self.is_running = False

    async def stop(self):
        """Stop the queue worker"""
        self.is_running = False
        logger.info("🛑 Auto-apply queue worker stopped")

    async def process_next_item(self, db=None):
        """Process the next item in the queue"""
        try:
            if db is None:
                from motor.motor_asyncio import AsyncIOMotorClient
                from app.core.config import settings
                client = AsyncIOMotorClient(settings.MONGODB_URL)
                db = client[settings.MONGODB_DATABASE]

            # Get the next pending item (ordered by priority, then created_at)
            queue_item = await db.auto_apply_queue.find_one_and_update(
                {"status": "pending"},
                {
                    "$set": {
                        "status": "processing",
                        "processing_started_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                },
                sort=[("priority", 1), ("created_at", 1)]
            )

            if not queue_item:
                # No items to process
                return

            logger.info(f"📋 Processing queue item: {queue_item['_id']}")

            # Process the application
            success, method = await self.process_application(queue_item, db)

            if success:
                # Mark as completed
                await db.auto_apply_queue.update_one(
                    {"_id": queue_item["_id"]},
                    {
                        "$set": {
                            "status": "completed",
                            "completed_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                # Update application status with tracking details
                await db.applications.update_one(
                    {"_id": ObjectId(queue_item["application_id"])},
                    {
                        "$set": {
                            "status": "applied",
                            "applied_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow(),
                            "application_method": method,
                            "source": "auto_apply",
                            "processed_by": "queue_worker"
                        }
                    }
                )

                # Create activity log
                await db.application_activity.insert_one({
                    "application_id": ObjectId(queue_item["application_id"]),
                    "user_id": queue_item["user_id"],
                    "action": "applied",
                    "details": f"Application submitted to {queue_item.get('job', {}).get('company', 'Unknown')}",
                    "timestamp": datetime.utcnow()
                })

                self.processed_count += 1
                logger.info(f"✅ Application {queue_item['application_id']} applied successfully")
            else:
                # Handle failure
                await self.handle_failure(queue_item, db)

        except Exception as e:
            logger.error(f"❌ Error processing queue item: {e}")

    async def process_application(self, queue_item: Dict[str, Any], db) -> tuple[bool, str]:
        """
        Process a single application
        Returns (success, method) tuple
        """
        try:
            application_id = queue_item["application_id"]
            user_id = queue_item["user_id"]

            # Get application details
            application = await db.applications.find_one({
                "_id": ObjectId(application_id)
            })

            if not application:
                logger.error(f"❌ Application {application_id} not found")
                return (False, "unknown")

            # Get job details
            job = application.get("job", {})
            if not job:
                logger.error(f"❌ No job data found for application {application_id}")
                return (False, "unknown")

            # Get user details
            user = await db.users.find_one({"_id": ObjectId(user_id) if isinstance(user_id, str) else user_id})
            if not user:
                logger.error(f"❌ User {user_id} not found")
                return (False, "unknown")

            logger.info(f"📝 Applying to: {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")

            # Get user settings
            user_settings = await db.user_settings.find_one({"user_id": str(user["_id"])})

            # Check if AI cover letters are enabled
            generate_cover_letter = user_settings.get("coverLetters", False) if user_settings else False

            cover_letter_text = None
            if generate_cover_letter:
                # Generate AI cover letter
                cover_letter_text = await self._generate_cover_letter(user, job, db)
                logger.info(f"✍️  Generated AI cover letter for {job.get('title')}")

            # Get user's resume
            resume_path = await self._get_user_resume(user["_id"], db)

            # Determine application method based on job source
            apply_url = job.get("apply_url", "")

            # Method 1: Email application (if job has email)
            if "@" in apply_url or job.get("apply_email"):
                success = await self._apply_via_email(
                    user=user,
                    job=job,
                    resume_path=resume_path,
                    cover_letter=cover_letter_text,
                    db=db
                )
                if success:
                    logger.info(f"📧 Application sent via email to {job.get('company')}")
                    return (True, "auto_apply_email")
                return (False, "auto_apply_email")

            # Method 2: Bot-based automation (uses BotManager to route to appropriate bot)
            elif apply_url.startswith("http"):
                logger.info(f"🤖 Using bot manager for: {apply_url}")

                # Initialize bot manager if not already done
                if self.bot_manager is None:
                    from app.services.bots.bot_manager import BotManager
                    self.bot_manager = BotManager()

                # Prepare user data for bot
                user_data = {
                    "email": user.get("email"),
                    "profile": user.get("profile", {}),
                    "desired_position": job.get("title"),
                    "location": user.get("job_preferences", {}).get("preferred_locations", ["USA"])[0] if user.get("job_preferences", {}).get("preferred_locations") else "USA",
                    "linkedin_email": user.get("linkedin_credentials", {}).get("email"),
                    "linkedin_password": user.get("linkedin_credentials", {}).get("password"),
                    "openai_api_key": user.get("ai_settings", {}).get("openai_api_key"),
                    "anthropic_api_key": user.get("ai_settings", {}).get("anthropic_api_key"),
                    "desired_positions": user.get("job_preferences", {}).get("desired_positions", []),
                    "preferred_locations": user.get("job_preferences", {}).get("preferred_locations", ["USA"])
                }

                # Use bot manager to apply (will route to appropriate bot or fallback to browser automation)
                result = await self.bot_manager.apply_to_job(
                    job_url=apply_url,
                    user_data=user_data,
                    resume_path=resume_path
                )

                if result.get("success"):
                    bot_used = result.get("bot_used", "browser")
                    logger.info(f"✅ Application submitted via {bot_used} to {job.get('company')}")
                    return (True, f"bot_{bot_used}")
                else:
                    logger.warning(f"⚠️ Bot automation failed: {result.get('error', 'Unknown error')}")
                    await db.applications.update_one(
                        {"_id": ObjectId(application_id)},
                        {
                            "$set": {
                                "application_method": "manual_url",
                                "apply_url": apply_url,
                                "notes": f"Bot automation failed: {result.get('error', 'Unknown error')} - requires manual submission"
                            }
                        }
                    )
                    return (False, "manual_url")

            # Method 3: Platform-specific API (LinkedIn, Indeed, etc.)
            else:
                logger.warning(f"⚠️  Unknown application method for {job.get('company')}")
                return (False, "unknown")

        except Exception as e:
            logger.error(f"❌ Error processing application: {e}")
            return (False, "unknown")

    async def _generate_cover_letter(self, user: Dict, job: Dict, db) -> str:
        """Generate AI cover letter for application"""
        try:
            from app.services.ai_service import generate_cover_letter

            # Get user profile and resume data
            resume = await db.resumes.find_one(
                {"user_id": user["_id"]},
                sort=[("created_at", -1)]
            )

            cover_letter = await generate_cover_letter(
                user_name=user.get("profile", {}).get("full_name", ""),
                user_email=user.get("email"),
                job_title=job.get("title"),
                company_name=job.get("company"),
                job_description=job.get("description", ""),
                user_experience=user.get("onboarding", {}).get("years_of_experience", 0),
                user_skills=user.get("job_preferences", {}).get("skills", []),
                resume_text=resume.get("parsed_data", {}).get("text", "") if resume else ""
            )

            return cover_letter
        except Exception as e:
            logger.error(f"❌ Error generating cover letter: {e}")
            return ""

    async def _get_user_resume(self, user_id, db) -> Optional[str]:
        """Get user's latest resume file path"""
        try:
            resume = await db.resumes.find_one(
                {"user_id": user_id},
                sort=[("created_at", -1)]
            )

            if resume and resume.get("file_path"):
                return resume["file_path"]

            logger.warning(f"⚠️  No resume found for user {user_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting resume: {e}")
            return None

    async def _apply_via_email(
        self,
        user: Dict,
        job: Dict,
        resume_path: Optional[str],
        cover_letter: Optional[str],
        db
    ) -> bool:
        """Send job application via email"""
        try:
            from app.services.job_application_email_service import JobApplicationEmailService

            email_service = JobApplicationEmailService(db)

            result = await email_service.apply_via_email(
                user_id=str(user["_id"]),
                job_data=job,
                resume_path=resume_path,
                cover_letter=cover_letter
            )

            return result.get("success", False)
        except Exception as e:
            logger.error(f"❌ Error sending email application: {e}")
            return False

    async def _apply_via_browser(
        self,
        user: Dict,
        job: Dict,
        resume_path: Optional[str],
        cover_letter: Optional[str],
        db
    ) -> bool:
        """Submit job application via browser automation"""
        try:
            from app.services.browser_auto_apply_service import BrowserAutoApplyService

            browser_service = BrowserAutoApplyService()

            # Prepare user data for form filling
            user_data = {
                "email": user.get("email"),
                "profile": user.get("profile", {}),
            }

            result = await browser_service.apply_to_job(
                job_url=job.get("apply_url"),
                user_data=user_data,
                job_data=job,
                resume_path=resume_path,
                cover_letter=cover_letter
            )

            await browser_service.close_browser()
            return result.get("success", False)
        except Exception as e:
            logger.error(f"❌ Error with browser automation: {e}")
            return False

    async def handle_failure(self, queue_item: Dict[str, Any], db):
        """Handle failed queue item"""
        try:
            retries = queue_item.get("retries", 0)
            max_retries = queue_item.get("max_retries", 3)

            if retries < max_retries:
                # Retry
                await db.auto_apply_queue.update_one(
                    {"_id": queue_item["_id"]},
                    {
                        "$set": {
                            "status": "pending",
                            "updated_at": datetime.utcnow()
                        },
                        "$inc": {"retries": 1}
                    }
                )
                logger.warning(f"⚠️  Queue item {queue_item['_id']} will be retried (attempt {retries + 1}/{max_retries})")
            else:
                # Max retries reached, mark as failed
                await db.auto_apply_queue.update_one(
                    {"_id": queue_item["_id"]},
                    {
                        "$set": {
                            "status": "failed",
                            "failed_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                # Update application status
                await db.applications.update_one(
                    {"_id": ObjectId(queue_item["application_id"])},
                    {
                        "$set": {
                            "status": "failed",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                self.failed_count += 1
                logger.error(f"❌ Queue item {queue_item['_id']} failed after {max_retries} retries")

        except Exception as e:
            logger.error(f"❌ Error handling failure: {e}")

    async def get_stats(self, db=None) -> Dict[str, Any]:
        """Get queue worker statistics"""
        try:
            if db is None:
                from motor.motor_asyncio import AsyncIOMotorClient
                from app.core.config import settings
                client = AsyncIOMotorClient(settings.MONGODB_URL)
                db = client[settings.MONGODB_DATABASE]

            pending_count = await db.auto_apply_queue.count_documents({"status": "pending"})
            processing_count = await db.auto_apply_queue.count_documents({"status": "processing"})
            completed_count = await db.auto_apply_queue.count_documents({"status": "completed"})
            failed_count = await db.auto_apply_queue.count_documents({"status": "failed"})

            return {
                "is_running": self.is_running,
                "pending": pending_count,
                "processing": processing_count,
                "completed": completed_count,
                "failed": failed_count,
                "total_processed": self.processed_count,
                "total_failed": self.failed_count
            }
        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}")
            return {
                "is_running": self.is_running,
                "error": str(e)
            }


# Global instance
queue_worker = AutoApplyQueueWorker()
