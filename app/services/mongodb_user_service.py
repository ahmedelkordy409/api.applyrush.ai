"""
MongoDB User service for managing user data
Replaces the Supabase UserService
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
from beanie import PydanticObjectId

from app.models.mongodb_models import (
    User, Job, JobApplication, JobMatch, ApplicationStatusHistory,
    AIProcessingLog, UserAnalytics, JobStatus
)

logger = logging.getLogger(__name__)


class MongoDBUserService:
    """MongoDB-based user service replacing Supabase functionality"""

    def __init__(self):
        self.logger = logger

    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by ID"""
        try:
            # Try to find by ObjectId first, then by external_id
            try:
                user = await User.get(ObjectId(user_id))
            except:
                user = await User.find_one(User.external_id == user_id)

            if user:
                self.logger.info(f"Retrieved user profile for user {user_id}")
                return user.dict()

            self.logger.warning(f"No profile found for user {user_id}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting user profile {user_id}: {e}")
            return None

    async def get_users_by_subscription(self, subscription_status: str) -> List[Dict[str, Any]]:
        """Get all users with specific subscription status"""
        try:
            # In MongoDB, we'll store subscription status in preferences
            users = await User.find(
                User.preferences.subscription_status == subscription_status
            ).to_list()

            result = [user.dict() for user in users]
            self.logger.info(f"Retrieved {len(result)} users with subscription: {subscription_status}")
            return result

        except Exception as e:
            self.logger.error(f"Error getting users by subscription {subscription_status}: {e}")
            return []

    async def get_active_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recently active users for AI processing"""
        try:
            # Get users who have been active in last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)

            users = await User.find(
                User.updated_at >= thirty_days_ago
            ).limit(limit).to_list()

            result = [user.dict() for user in users]
            self.logger.info(f"Retrieved {len(result)} active users for AI processing")
            return result

        except Exception as e:
            self.logger.error(f"Error getting active users: {e}")
            return []

    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user profile"""
        try:
            # Try to find by ObjectId first, then by external_id
            try:
                user = await User.get(ObjectId(user_id))
            except:
                user = await User.find_one(User.external_id == user_id)

            if not user:
                self.logger.warning(f"No profile found to update for user {user_id}")
                return False

            # Update fields
            for key, value in updates.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            user.updated_at = datetime.utcnow()
            await user.save()

            self.logger.info(f"Updated profile for user {user_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error updating user profile {user_id}: {e}")
            return False

    async def get_user_applications(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's job applications"""
        try:
            # Convert user_id to ObjectId if needed
            try:
                user_object_id = ObjectId(user_id)
            except:
                # If user_id is external_id, find the user first
                user = await User.find_one(User.external_id == user_id)
                if not user:
                    return []
                user_object_id = user.id

            applications = await JobApplication.find(
                JobApplication.user_id == user_object_id
            ).sort(-JobApplication.created_at).limit(limit).to_list()

            # Get associated job data
            result = []
            for app in applications:
                app_data = app.dict()

                # Get job details
                job = await Job.get(app.job_id)
                if job:
                    app_data['job'] = job.dict()

                result.append(app_data)

            self.logger.info(f"Retrieved {len(result)} applications for user {user_id}")
            return result

        except Exception as e:
            self.logger.error(f"Error getting applications for user {user_id}: {e}")
            return []

    async def create_application(self, user_id: str, job_id: str, application_data: Dict[str, Any]) -> Optional[str]:
        """Create new job application"""
        try:
            # Convert IDs to ObjectId
            try:
                user_object_id = ObjectId(user_id)
            except:
                user = await User.find_one(User.external_id == user_id)
                if not user:
                    return None
                user_object_id = user.id

            try:
                job_object_id = ObjectId(job_id)
            except:
                job = await Job.find_one(Job.external_id == job_id)
                if not job:
                    return None
                job_object_id = job.id

            # Create application
            application = JobApplication(
                user_id=user_object_id,
                job_id=job_object_id,
                status=JobStatus(application_data.get('status', 'pending')),
                cover_letter=application_data.get('cover_letter'),
                resume_version=application_data.get('resume_version'),
                applied_via=application_data.get('source', 'ai_agent')
            )

            if application_data.get('applied_at'):
                application.applied_at = application_data['applied_at']
                application.status = JobStatus.SUBMITTED

            await application.insert()

            self.logger.info(f"Created application {application.id} for user {user_id} to job {job_id}")
            return str(application.id)

        except Exception as e:
            self.logger.error(f"Error creating application for user {user_id}: {e}")
            return None

    async def get_user_job_queue(self, user_id: str, status: str = 'pending', limit: int = 20) -> List[Dict[str, Any]]:
        """Get user's application queue (job matches that are pending application)"""
        try:
            # Convert user_id to ObjectId if needed
            try:
                user_object_id = ObjectId(user_id)
            except:
                user = await User.find_one(User.external_id == user_id)
                if not user:
                    return []
                user_object_id = user.id

            # Find job matches that haven't been applied to yet
            job_matches = await JobMatch.find(
                JobMatch.user_id == user_object_id
            ).sort(-JobMatch.created_at).limit(limit).to_list()

            result = []
            for match in job_matches:
                # Check if application already exists
                existing_app = await JobApplication.find_one(
                    JobApplication.user_id == user_object_id,
                    JobApplication.job_id == match.job_id
                )

                if not existing_app:  # Only include if not already applied
                    match_data = match.dict()

                    # Get job details
                    job = await Job.get(match.job_id)
                    if job:
                        match_data['job'] = job.dict()

                    result.append(match_data)

            self.logger.info(f"Retrieved {len(result)} queue items for user {user_id}")
            return result

        except Exception as e:
            self.logger.error(f"Error getting job queue for user {user_id}: {e}")
            return []

    async def add_to_job_queue(self, user_id: str, job_id: str, match_data: Dict[str, Any]) -> Optional[str]:
        """Add job to user's application queue (create a job match)"""
        try:
            # Convert IDs to ObjectId
            try:
                user_object_id = ObjectId(user_id)
            except:
                user = await User.find_one(User.external_id == user_id)
                if not user:
                    return None
                user_object_id = user.id

            try:
                job_object_id = ObjectId(job_id)
            except:
                job = await Job.find_one(Job.external_id == job_id)
                if not job:
                    return None
                job_object_id = job.id

            # Create job match
            job_match = JobMatch(
                user_id=user_object_id,
                job_id=job_object_id,
                overall_score=match_data.get('match_score'),
                matched_skills=match_data.get('match_reasons', []),
                apply_priority=match_data.get('priority', 50)
            )

            await job_match.insert()

            self.logger.info(f"Added job {job_id} to queue for user {user_id}: {job_match.id}")
            return str(job_match.id)

        except Exception as e:
            self.logger.error(f"Error adding job to queue for user {user_id}: {e}")
            return None

    async def update_queue_item(self, queue_id: str, updates: Dict[str, Any]) -> bool:
        """Update queue item (job match)"""
        try:
            job_match = await JobMatch.get(ObjectId(queue_id))
            if not job_match:
                self.logger.warning(f"No job match found: {queue_id}")
                return False

            # Update fields
            for key, value in updates.items():
                if hasattr(job_match, key):
                    setattr(job_match, key, value)

            job_match.updated_at = datetime.utcnow()
            await job_match.save()

            self.logger.info(f"Updated job match {queue_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error updating job match {queue_id}: {e}")
            return False

    async def get_job_matches(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get AI job matches for user"""
        try:
            # Convert user_id to ObjectId if needed
            try:
                user_object_id = ObjectId(user_id)
            except:
                user = await User.find_one(User.external_id == user_id)
                if not user:
                    return []
                user_object_id = user.id

            matches = await JobMatch.find(
                JobMatch.user_id == user_object_id
            ).sort(-JobMatch.overall_score).limit(limit).to_list()

            result = []
            for match in matches:
                match_data = match.dict()

                # Get job details
                job = await Job.get(match.job_id)
                if job:
                    match_data['job'] = job.dict()

                result.append(match_data)

            self.logger.info(f"Retrieved {len(result)} job matches for user {user_id}")
            return result

        except Exception as e:
            self.logger.error(f"Error getting job matches for user {user_id}: {e}")
            return []

    async def create_job_match(self, user_id: str, job_id: str, match_analysis: Dict[str, Any]) -> Optional[str]:
        """Create new job match record"""
        try:
            # Convert IDs to ObjectId
            try:
                user_object_id = ObjectId(user_id)
            except:
                user = await User.find_one(User.external_id == user_id)
                if not user:
                    return None
                user_object_id = user.id

            try:
                job_object_id = ObjectId(job_id)
            except:
                job = await Job.find_one(Job.external_id == job_id)
                if not job:
                    return None
                job_object_id = job.id

            # Create job match
            job_match = JobMatch(
                user_id=user_object_id,
                job_id=job_object_id,
                overall_score=match_analysis.get('match_score'),
                skill_match_score=match_analysis.get('skill_match_score'),
                experience_score=match_analysis.get('experience_score'),
                location_score=match_analysis.get('location_compatibility'),
                matched_skills=match_analysis.get('match_reasons', []),
                missing_skills=match_analysis.get('missing_skills', []),
                improvement_suggestions=match_analysis.get('recommended_skills', []),
                success_probability=match_analysis.get('confidence_score')
            )

            await job_match.insert()

            self.logger.info(f"Created job match {job_match.id} for user {user_id}")
            return str(job_match.id)

        except Exception as e:
            self.logger.error(f"Error creating job match for user {user_id}: {e}")
            return None

    async def track_user_activity(self, user_id: str, action: str, resource_type: str = None,
                                 resource_id: str = None, metadata: Dict = None) -> None:
        """Track user activity - can be implemented with a separate analytics collection"""
        try:
            # For now, just update the user's last activity
            await self.update_last_active(user_id)
            self.logger.debug(f"Tracked activity for user {user_id}: {action}")

        except Exception as e:
            self.logger.error(f"Error tracking user activity: {e}")

    async def update_last_active(self, user_id: str) -> None:
        """Update user's last active timestamp"""
        try:
            await self.update_user_profile(user_id, {
                'updated_at': datetime.utcnow()
            })
        except Exception as e:
            self.logger.error(f"Error updating last active for user {user_id}: {e}")

    async def get_user_subscription_info(self, user_id: str) -> Dict[str, Any]:
        """Get user's subscription information"""
        try:
            # Get user profile
            profile = await self.get_user_profile(user_id)
            if not profile:
                return {'subscription_status': 'free', 'limits': {}}

            # Extract subscription info from preferences
            preferences = profile.get('preferences', {})
            subscription_status = preferences.get('subscription_status', 'free')

            # For now, return basic subscription info
            # You can expand this to include usage tracking, plan details, etc.
            return {
                'subscription_status': subscription_status,
                'profile_completion': self._calculate_profile_completion(profile),
                'current_usage': {},  # Can be implemented with usage tracking
                'plan_details': {}  # Can be implemented with plan management
            }

        except Exception as e:
            self.logger.error(f"Error getting subscription info for user {user_id}: {e}")
            return {'subscription_status': 'free', 'limits': {}}

    def _calculate_profile_completion(self, profile: Dict[str, Any]) -> int:
        """Calculate profile completion percentage"""
        required_fields = ['full_name', 'email', 'resume_text', 'skills', 'experience_years']
        completed_fields = sum(1 for field in required_fields if profile.get(field))
        return int((completed_fields / len(required_fields)) * 100)

    async def create_user(self, email: str, full_name: str = None, external_id: str = None) -> Optional[str]:
        """Create a new user"""
        try:
            user = User(
                email=email,
                full_name=full_name,
                external_id=external_id
            )
            await user.insert()

            self.logger.info(f"Created user {user.id} with email {email}")
            return str(user.id)

        except Exception as e:
            self.logger.error(f"Error creating user with email {email}: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            user = await User.find_one(User.email == email)
            if user:
                return user.dict()
            return None
        except Exception as e:
            self.logger.error(f"Error getting user by email {email}: {e}")
            return None


# Global MongoDB user service instance
_mongodb_user_service = None


def get_mongodb_user_service() -> MongoDBUserService:
    """Get global MongoDB user service instance"""
    global _mongodb_user_service
    if _mongodb_user_service is None:
        _mongodb_user_service = MongoDBUserService()
    return _mongodb_user_service