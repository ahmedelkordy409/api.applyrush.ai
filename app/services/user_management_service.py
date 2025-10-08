"""
User Management Service
Handles user settings, search controls, onboarding, and queue management
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import json

try:
    from ..core.database import database
    from ..core.config import settings
    from ..core.monitoring import performance_monitor
except ImportError:
    database = None
    settings = None
    performance_monitor = None

from ..models.user_settings import (
    SearchStatus, QueuePriority, OnboardingStatus,
    SearchSettingsUpdate, SearchControlRequest, QueueItemRequest,
    OnboardingStepData, UserPreferencesUpdate, QueueFilters
)
from ..models.documents import DocumentType, DocumentStatus
import structlog

logger = structlog.get_logger()


class UserManagementService:
    """
    Comprehensive user management service for JobHire.AI
    Handles all user-related operations including settings, search control, and onboarding
    """
    
    def __init__(self):
        self.logger = logger.bind(service="UserManagementService")
    
    # === USER PROFILE MANAGEMENT ===
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get complete user profile"""
        try:
            query = "SELECT * FROM user_profiles WHERE user_id = :user_id"
            result = await database.fetch_one(query, {"user_id": user_id})
            return dict(result) if result else None
        except Exception as e:
            self.logger.error("Failed to get user profile", user_id=user_id, error=str(e))
            return None
    
    async def create_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """Create new user profile"""
        try:
            query = """
                INSERT INTO user_profiles (
                    user_id, email, full_name, phone, skills, experience_years,
                    education, location, remote_preference, target_roles,
                    industries, salary_minimum, salary_target, user_tier
                ) VALUES (
                    :user_id, :email, :full_name, :phone, :skills, :experience_years,
                    :education, :location, :remote_preference, :target_roles,
                    :industries, :salary_minimum, :salary_target, :user_tier
                )
            """
            
            await database.execute(query, {
                "user_id": user_id,
                "email": profile_data.get("email"),
                "full_name": profile_data.get("full_name"),
                "phone": profile_data.get("phone"),
                "skills": json.dumps(profile_data.get("skills", [])),
                "experience_years": profile_data.get("experience_years"),
                "education": json.dumps(profile_data.get("education", [])),
                "location": json.dumps(profile_data.get("location", {})),
                "remote_preference": profile_data.get("remote_preference", "hybrid"),
                "target_roles": json.dumps(profile_data.get("target_roles", [])),
                "industries": json.dumps(profile_data.get("industries", [])),
                "salary_minimum": profile_data.get("salary_minimum"),
                "salary_target": profile_data.get("salary_target"),
                "user_tier": profile_data.get("user_tier", "free")
            })
            
            # Create default search settings
            await self.create_default_search_settings(user_id)
            
            self.logger.info("User profile created", user_id=user_id)
            return True
            
        except Exception as e:
            self.logger.error("Failed to create user profile", user_id=user_id, error=str(e))
            return False
    
    async def update_user_preferences(self, user_id: str, preferences: UserPreferencesUpdate) -> bool:
        """Update user preferences"""
        try:
            update_fields = []
            update_values = {"user_id": user_id}
            
            for field, value in preferences.dict(exclude_unset=True).items():
                if value is not None:
                    if isinstance(value, (list, dict)):
                        update_fields.append(f"{field} = :{field}")
                        update_values[field] = json.dumps(value)
                    else:
                        update_fields.append(f"{field} = :{field}")
                        update_values[field] = value
            
            if not update_fields:
                return True
            
            query = f"""
                UPDATE user_profiles 
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE user_id = :user_id
            """
            
            await database.execute(query, update_values)
            
            self.logger.info("User preferences updated", user_id=user_id, fields=list(preferences.dict(exclude_unset=True).keys()))
            return True
            
        except Exception as e:
            self.logger.error("Failed to update user preferences", user_id=user_id, error=str(e))
            return False
    
    # === SEARCH SETTINGS MANAGEMENT ===
    
    async def get_search_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user search settings"""
        try:
            query = "SELECT * FROM user_search_settings WHERE user_id = :user_id"
            result = await database.fetch_one(query, {"user_id": user_id})
            return dict(result) if result else None
        except Exception as e:
            self.logger.error("Failed to get search settings", user_id=user_id, error=str(e))
            return None
    
    async def create_default_search_settings(self, user_id: str) -> bool:
        """Create default search settings for new user"""
        try:
            default_settings = {
                "user_id": user_id,
                "search_status": SearchStatus.ACTIVE.value,
                "keywords": json.dumps([]),
                "excluded_keywords": json.dumps([]),
                "minimum_match_score": 70.0,
                "auto_apply_threshold": 85.0,
                "max_applications_per_day": 10,
                "max_applications_per_week": 50,
                "search_frequency_hours": 4,
                "enabled_platforms": json.dumps(["linkedin", "indeed"]),
                "require_manual_review": True,
                "remote_only": False
            }
            
            query = """
                INSERT INTO user_search_settings (
                    user_id, search_status, keywords, excluded_keywords,
                    minimum_match_score, auto_apply_threshold, max_applications_per_day,
                    max_applications_per_week, search_frequency_hours, enabled_platforms,
                    require_manual_review, remote_only
                ) VALUES (
                    :user_id, :search_status, :keywords, :excluded_keywords,
                    :minimum_match_score, :auto_apply_threshold, :max_applications_per_day,
                    :max_applications_per_week, :search_frequency_hours, :enabled_platforms,
                    :require_manual_review, :remote_only
                )
            """
            
            await database.execute(query, default_settings)
            
            self.logger.info("Default search settings created", user_id=user_id)
            return True
            
        except Exception as e:
            self.logger.error("Failed to create default search settings", user_id=user_id, error=str(e))
            return False
    
    async def update_search_settings(self, user_id: str, settings: SearchSettingsUpdate) -> bool:
        """Update user search settings"""
        try:
            update_fields = []
            update_values = {"user_id": user_id}
            
            for field, value in settings.dict(exclude_unset=True).items():
                if value is not None:
                    if isinstance(value, list):
                        update_fields.append(f"{field} = :{field}")
                        update_values[field] = json.dumps(value)
                    else:
                        update_fields.append(f"{field} = :{field}")
                        update_values[field] = value
            
            if not update_fields:
                return True
            
            query = f"""
                UPDATE user_search_settings 
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE user_id = :user_id
            """
            
            await database.execute(query, update_values)
            
            self.logger.info("Search settings updated", user_id=user_id)
            return True
            
        except Exception as e:
            self.logger.error("Failed to update search settings", user_id=user_id, error=str(e))
            return False
    
    # === SEARCH CONTROL ===
    
    async def control_search(self, user_id: str, control: SearchControlRequest) -> Dict[str, Any]:
        """Control user search (pause, resume, stop, start)"""
        try:
            current_settings = await self.get_search_settings(user_id)
            if not current_settings:
                return {"success": False, "error": "User search settings not found"}
            
            current_status = current_settings.get("search_status")
            
            # Validate state transitions
            valid_transitions = {
                "pause": [SearchStatus.ACTIVE.value],
                "resume": [SearchStatus.PAUSED.value],
                "stop": [SearchStatus.ACTIVE.value, SearchStatus.PAUSED.value],
                "start": [SearchStatus.STOPPED.value]
            }
            
            if current_status not in valid_transitions.get(control.action, []):
                return {
                    "success": False,
                    "error": f"Cannot {control.action} from status {current_status}"
                }
            
            # Update status based on action
            new_status = {
                "pause": SearchStatus.PAUSED.value,
                "resume": SearchStatus.ACTIVE.value,
                "stop": SearchStatus.STOPPED.value,
                "start": SearchStatus.ACTIVE.value
            }[control.action]
            
            update_data = {
                "user_id": user_id,
                "search_status": new_status
            }
            
            # Handle pause-specific fields
            if control.action == "pause":
                update_data["search_paused_at"] = datetime.utcnow()
                update_data["search_pause_reason"] = control.reason
                update_data["auto_resume_at"] = control.auto_resume_at
            elif control.action == "resume":
                update_data["search_paused_at"] = None
                update_data["search_pause_reason"] = None
                update_data["auto_resume_at"] = None
            
            # Build update query
            set_clauses = []
            for key, value in update_data.items():
                if key != "user_id":
                    set_clauses.append(f"{key} = :{key}")
            
            query = f"""
                UPDATE user_search_settings 
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE user_id = :user_id
            """
            
            await database.execute(query, update_data)
            
            self.logger.info("Search control applied", 
                           user_id=user_id, 
                           action=control.action,
                           new_status=new_status)
            
            return {
                "success": True,
                "previous_status": current_status,
                "new_status": new_status,
                "message": f"Search {control.action}d successfully"
            }
            
        except Exception as e:
            self.logger.error("Failed to control search", user_id=user_id, action=control.action, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def check_auto_resume(self) -> List[str]:
        """Check for users whose search should auto-resume"""
        try:
            query = """
                SELECT user_id FROM user_search_settings 
                WHERE search_status = :paused 
                AND auto_resume_at IS NOT NULL 
                AND auto_resume_at <= NOW()
            """
            
            results = await database.fetch_all(query, {"paused": SearchStatus.PAUSED.value})
            
            resumed_users = []
            for result in results:
                user_id = result["user_id"]
                resume_result = await self.control_search(
                    user_id, 
                    SearchControlRequest(action="resume", reason="Auto-resume triggered")
                )
                if resume_result["success"]:
                    resumed_users.append(user_id)
            
            if resumed_users:
                self.logger.info("Auto-resumed searches", users=resumed_users)
            
            return resumed_users
            
        except Exception as e:
            self.logger.error("Failed to check auto-resume", error=str(e))
            return []
    
    # === QUEUE MANAGEMENT ===
    
    async def add_to_queue(self, user_id: str, queue_item: QueueItemRequest) -> Dict[str, Any]:
        """Add job to user's application queue"""
        try:
            # Check if job already in queue
            existing_query = """
                SELECT id FROM user_queues 
                WHERE user_id = :user_id AND job_id = :job_id AND status = 'queued'
            """
            existing = await database.fetch_one(existing_query, {
                "user_id": user_id,
                "job_id": queue_item.job_id
            })
            
            if existing:
                return {"success": False, "error": "Job already in queue"}
            
            # Add to queue
            queue_data = {
                "user_id": user_id,
                "job_id": queue_item.job_id,
                "priority": queue_item.priority.value,
                "job_data": json.dumps(queue_item.job_data),
                "scheduled_for": queue_item.scheduled_for,
                "user_notes": queue_item.user_notes,
                "status": "queued"
            }
            
            query = """
                INSERT INTO user_queues (
                    user_id, job_id, priority, job_data, scheduled_for, user_notes, status
                ) VALUES (
                    :user_id, :job_id, :priority, :job_data, :scheduled_for, :user_notes, :status
                )
                RETURNING id
            """
            
            result = await database.fetch_one(query, queue_data)
            queue_id = result["id"]
            
            self.logger.info("Job added to queue", user_id=user_id, job_id=queue_item.job_id, queue_id=str(queue_id))
            
            return {
                "success": True,
                "queue_id": str(queue_id),
                "message": "Job added to queue successfully"
            }
            
        except Exception as e:
            self.logger.error("Failed to add job to queue", user_id=user_id, job_id=queue_item.job_id, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def get_user_queue(self, user_id: str, filters: QueueFilters = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's application queue with optional filters"""
        try:
            where_clauses = ["user_id = :user_id"]
            params = {"user_id": user_id, "limit": limit}
            
            if filters:
                if filters.status:
                    where_clauses.append("status = :status")
                    params["status"] = filters.status
                
                if filters.priority:
                    where_clauses.append("priority = :priority")
                    params["priority"] = filters.priority.value
                
                if filters.date_from:
                    where_clauses.append("queued_at >= :date_from")
                    params["date_from"] = filters.date_from
                
                if filters.date_to:
                    where_clauses.append("queued_at <= :date_to")
                    params["date_to"] = filters.date_to
                
                if filters.flagged_only:
                    where_clauses.append("user_flagged = TRUE")
                
                if filters.min_match_score:
                    where_clauses.append("match_score >= :min_match_score")
                    params["min_match_score"] = filters.min_match_score
            
            query = f"""
                SELECT * FROM user_queues 
                WHERE {' AND '.join(where_clauses)}
                ORDER BY 
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'normal' THEN 3 
                        WHEN 'low' THEN 4 
                    END,
                    queued_at DESC
                LIMIT :limit
            """
            
            results = await database.fetch_all(query, params)
            return [dict(result) for result in results]
            
        except Exception as e:
            self.logger.error("Failed to get user queue", user_id=user_id, error=str(e))
            return []
    
    async def update_queue_item(self, user_id: str, queue_id: str, updates: Dict[str, Any]) -> bool:
        """Update queue item"""
        try:
            allowed_fields = ["priority", "scheduled_for", "user_notes", "user_flagged", "user_action", "status"]
            
            update_fields = []
            update_values = {"user_id": user_id, "queue_id": queue_id}
            
            for field, value in updates.items():
                if field in allowed_fields and value is not None:
                    update_fields.append(f"{field} = :{field}")
                    update_values[field] = value
            
            if not update_fields:
                return True
            
            query = f"""
                UPDATE user_queues 
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE id = :queue_id AND user_id = :user_id
            """
            
            await database.execute(query, update_values)
            
            self.logger.info("Queue item updated", user_id=user_id, queue_id=queue_id)
            return True
            
        except Exception as e:
            self.logger.error("Failed to update queue item", user_id=user_id, queue_id=queue_id, error=str(e))
            return False
    
    async def get_next_queue_items(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get next items to process from all user queues"""
        try:
            query = """
                SELECT uq.*, up.user_tier, uss.search_status 
                FROM user_queues uq
                JOIN user_profiles up ON uq.user_id = up.user_id
                JOIN user_search_settings uss ON uq.user_id = uss.user_id
                WHERE uq.status = 'queued'
                AND uss.search_status = 'active'
                AND (uq.scheduled_for IS NULL OR uq.scheduled_for <= NOW())
                ORDER BY 
                    CASE uq.priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'normal' THEN 3 
                        WHEN 'low' THEN 4 
                    END,
                    uq.queued_at ASC
                LIMIT :limit
            """
            
            results = await database.fetch_all(query, {"limit": limit})
            return [dict(result) for result in results]
            
        except Exception as e:
            self.logger.error("Failed to get next queue items", error=str(e))
            return []
    
    # === ONBOARDING MANAGEMENT ===
    
    async def get_onboarding_status(self, user_id: str) -> Dict[str, Any]:
        """Get user onboarding status and progress"""
        try:
            # Get overall status
            profile_query = "SELECT onboarding_status, onboarding_completed_at FROM user_profiles WHERE user_id = :user_id"
            profile_result = await database.fetch_one(profile_query, {"user_id": user_id})
            
            if not profile_result:
                return {"status": OnboardingStatus.NOT_STARTED.value, "progress": 0, "steps": []}
            
            # Get step details
            steps_query = """
                SELECT * FROM onboarding_steps 
                WHERE user_id = :user_id 
                ORDER BY step_order
            """
            steps_results = await database.fetch_all(steps_query, {"user_id": user_id})
            
            steps = [dict(step) for step in steps_results]
            completed_steps = len([s for s in steps if s["status"] == "completed"])
            total_steps = len(steps) if steps else 6  # Default expected steps
            
            progress = (completed_steps / total_steps * 100) if total_steps > 0 else 0
            
            return {
                "status": profile_result["onboarding_status"],
                "completed_at": profile_result["onboarding_completed_at"],
                "progress": round(progress, 1),
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "steps": steps
            }
            
        except Exception as e:
            self.logger.error("Failed to get onboarding status", user_id=user_id, error=str(e))
            return {"status": OnboardingStatus.NOT_STARTED.value, "progress": 0, "steps": []}
    
    async def update_onboarding_step(self, user_id: str, step_data: OnboardingStepData) -> bool:
        """Update or create onboarding step"""
        try:
            # Check if step exists
            existing_query = """
                SELECT id FROM onboarding_steps 
                WHERE user_id = :user_id AND step_name = :step_name
            """
            existing = await database.fetch_one(existing_query, {
                "user_id": user_id,
                "step_name": step_data.step_name
            })
            
            step_values = {
                "user_id": user_id,
                "step_name": step_data.step_name,
                "step_data": json.dumps(step_data.step_data),
                "completion_percentage": step_data.completion_percentage,
                "status": "completed" if step_data.completion_percentage >= 100 else "in_progress"
            }
            
            if existing:
                # Update existing step
                query = """
                    UPDATE onboarding_steps 
                    SET step_data = :step_data, completion_percentage = :completion_percentage,
                        status = :status, completed_at = :completed_at, updated_at = NOW()
                    WHERE user_id = :user_id AND step_name = :step_name
                """
                step_values["completed_at"] = datetime.utcnow() if step_data.completion_percentage >= 100 else None
            else:
                # Create new step
                query = """
                    INSERT INTO onboarding_steps (
                        user_id, step_name, step_data, completion_percentage, status,
                        started_at, completed_at, step_order
                    ) VALUES (
                        :user_id, :step_name, :step_data, :completion_percentage, :status,
                        :started_at, :completed_at, :step_order
                    )
                """
                step_values.update({
                    "started_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow() if step_data.completion_percentage >= 100 else None,
                    "step_order": self._get_step_order(step_data.step_name)
                })
            
            await database.execute(query, step_values)
            
            # Check if onboarding is complete
            await self._check_onboarding_completion(user_id)
            
            self.logger.info("Onboarding step updated", user_id=user_id, step=step_data.step_name)
            return True
            
        except Exception as e:
            self.logger.error("Failed to update onboarding step", user_id=user_id, step=step_data.step_name, error=str(e))
            return False
    
    def _get_step_order(self, step_name: str) -> int:
        """Get step order for onboarding steps"""
        step_orders = {
            "profile": 1,
            "preferences": 2,
            "resume": 3,
            "search_settings": 4,
            "review": 5,
            "completion": 6
        }
        return step_orders.get(step_name, 99)
    
    async def _check_onboarding_completion(self, user_id: str):
        """Check if user has completed onboarding"""
        try:
            # Get all steps
            query = """
                SELECT COUNT(*) as total, COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
                FROM onboarding_steps 
                WHERE user_id = :user_id
            """
            result = await database.fetch_one(query, {"user_id": user_id})
            
            if result and result["total"] >= 5 and result["completed"] >= 4:  # Most steps completed
                # Mark onboarding as completed
                update_query = """
                    UPDATE user_profiles 
                    SET onboarding_status = :status, onboarding_completed_at = NOW()
                    WHERE user_id = :user_id
                """
                await database.execute(update_query, {
                    "user_id": user_id,
                    "status": OnboardingStatus.COMPLETED.value
                })
                
                self.logger.info("Onboarding completed", user_id=user_id)
                
        except Exception as e:
            self.logger.error("Failed to check onboarding completion", user_id=user_id, error=str(e))
    
    # === UTILITY METHODS ===
    
    async def get_user_dashboard_data(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive dashboard data for user"""
        try:
            # Get all user data in parallel
            profile_task = self.get_user_profile(user_id)
            search_settings_task = self.get_search_settings(user_id)
            queue_task = self.get_user_queue(user_id, limit=10)
            onboarding_task = self.get_onboarding_status(user_id)
            
            profile, search_settings, queue, onboarding = await asyncio.gather(
                profile_task, search_settings_task, queue_task, onboarding_task
            )
            
            # Get queue statistics
            queue_stats = await self._get_queue_statistics(user_id)
            
            return {
                "profile": profile,
                "search_settings": search_settings,
                "queue": {
                    "items": queue,
                    "statistics": queue_stats
                },
                "onboarding": onboarding,
                "dashboard_generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get user dashboard data", user_id=user_id, error=str(e))
            return {}
    
    async def _get_queue_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get queue statistics for user"""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_items,
                    COUNT(CASE WHEN status = 'queued' THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
                    COUNT(CASE WHEN application_submitted = TRUE THEN 1 END) as applications_submitted,
                    AVG(match_score) as avg_match_score
                FROM user_queues 
                WHERE user_id = :user_id
            """
            
            result = await database.fetch_one(query, {"user_id": user_id})
            
            if result:
                return {
                    "total_items": result["total_items"] or 0,
                    "pending": result["pending"] or 0,
                    "completed": result["completed"] or 0,
                    "processing": result["processing"] or 0,
                    "applications_submitted": result["applications_submitted"] or 0,
                    "avg_match_score": round(result["avg_match_score"] or 0, 1)
                }
            
            return {
                "total_items": 0,
                "pending": 0,
                "completed": 0,
                "processing": 0,
                "applications_submitted": 0,
                "avg_match_score": 0
            }
            
        except Exception as e:
            self.logger.error("Failed to get queue statistics", user_id=user_id, error=str(e))
            return {}


# Global service instance
user_management_service = UserManagementService()

# Export service
__all__ = ["UserManagementService", "user_management_service"]