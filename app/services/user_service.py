"""
User service for managing real user data from Supabase
"""

import os
import logging
from typing import Dict, Any, Optional, List
from supabase import create_client, Client
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self):
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by ID"""
        try:
            result = self.supabase.table('profiles').select('*').eq('id', user_id).execute()
            
            if result.data:
                profile = result.data[0]
                # Convert JSONB fields to proper format
                if profile.get('job_preferences'):
                    profile['job_preferences'] = json.loads(profile['job_preferences']) if isinstance(profile['job_preferences'], str) else profile['job_preferences']
                if profile.get('notification_preferences'):
                    profile['notification_preferences'] = json.loads(profile['notification_preferences']) if isinstance(profile['notification_preferences'], str) else profile['notification_preferences']
                
                logger.info(f"Retrieved user profile for user {user_id}")
                return profile
            
            logger.warning(f"No profile found for user {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting user profile {user_id}: {e}")
            return None
    
    async def get_users_by_subscription(self, subscription_status: str) -> List[Dict[str, Any]]:
        """Get all users with specific subscription status"""
        try:
            result = self.supabase.table('profiles').select('*').eq('subscription_status', subscription_status).execute()
            
            users = []
            for profile in result.data:
                # Convert JSONB fields
                if profile.get('job_preferences'):
                    profile['job_preferences'] = json.loads(profile['job_preferences']) if isinstance(profile['job_preferences'], str) else profile['job_preferences']
                users.append(profile)
            
            logger.info(f"Retrieved {len(users)} users with subscription: {subscription_status}")
            return users
            
        except Exception as e:
            logger.error(f"Error getting users by subscription {subscription_status}: {e}")
            return []
    
    async def get_active_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recently active users for AI processing"""
        try:
            # Get users who have been active in last 30 days
            result = self.supabase.table('profiles').select('*').gte('last_active_at', datetime.now().strftime('%Y-%m-%d')).limit(limit).execute()
            
            users = []
            for profile in result.data:
                if profile.get('job_preferences'):
                    profile['job_preferences'] = json.loads(profile['job_preferences']) if isinstance(profile['job_preferences'], str) else profile['job_preferences']
                users.append(profile)
            
            logger.info(f"Retrieved {len(users)} active users for AI processing")
            return users
            
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
    
    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user profile"""
        try:
            # Convert dict fields to JSONB
            if 'job_preferences' in updates:
                updates['job_preferences'] = json.dumps(updates['job_preferences'])
            if 'notification_preferences' in updates:
                updates['notification_preferences'] = json.dumps(updates['notification_preferences'])
            
            updates['updated_at'] = datetime.now().isoformat()
            
            result = self.supabase.table('profiles').update(updates).eq('id', user_id).execute()
            
            if result.data:
                logger.info(f"Updated profile for user {user_id}")
                return True
            else:
                logger.warning(f"No profile updated for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating user profile {user_id}: {e}")
            return False
    
    async def get_user_applications(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's job applications"""
        try:
            result = (self.supabase.table('applications')
                     .select('*, jobs(*)')
                     .eq('user_id', user_id)
                     .order('created_at', desc=True)
                     .limit(limit)
                     .execute())
            
            applications = result.data or []
            
            for app in applications:
                # Convert JSONB fields
                if app.get('custom_answers'):
                    app['custom_answers'] = json.loads(app['custom_answers']) if isinstance(app['custom_answers'], str) else app['custom_answers']
            
            logger.info(f"Retrieved {len(applications)} applications for user {user_id}")
            return applications
            
        except Exception as e:
            logger.error(f"Error getting applications for user {user_id}: {e}")
            return []
    
    async def create_application(self, user_id: str, job_id: str, application_data: Dict[str, Any]) -> Optional[str]:
        """Create new job application"""
        try:
            data = {
                'user_id': user_id,
                'job_id': job_id,
                'status': application_data.get('status', 'pending'),
                'cover_letter': application_data.get('cover_letter'),
                'resume_version': application_data.get('resume_version'),
                'custom_answers': json.dumps(application_data.get('custom_answers', {})),
                'source': application_data.get('source', 'ai_agent'),
                'created_at': datetime.now().isoformat()
            }
            
            if application_data.get('applied_at'):
                data['applied_at'] = application_data['applied_at']
                data['status'] = 'applied'
            
            result = self.supabase.table('applications').insert(data).execute()
            
            if result.data:
                app_id = result.data[0]['id']
                logger.info(f"Created application {app_id} for user {user_id} to job {job_id}")
                return app_id
            else:
                logger.error(f"Failed to create application for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating application for user {user_id}: {e}")
            return None
    
    async def get_user_job_queue(self, user_id: str, status: str = 'pending', limit: int = 20) -> List[Dict[str, Any]]:
        """Get user's application queue"""
        try:
            query = (self.supabase.table('application_queue')
                    .select('*, jobs(*)')
                    .eq('user_id', user_id)
                    .order('created_at', desc=True)
                    .limit(limit))
            
            if status:
                query = query.eq('status', status)
            
            result = query.execute()
            queue_items = result.data or []
            
            for item in queue_items:
                # Convert JSONB and array fields
                if item.get('match_reasons'):
                    if isinstance(item['match_reasons'], str):
                        item['match_reasons'] = json.loads(item['match_reasons'])
            
            logger.info(f"Retrieved {len(queue_items)} queue items for user {user_id}")
            return queue_items
            
        except Exception as e:
            logger.error(f"Error getting job queue for user {user_id}: {e}")
            return []
    
    async def add_to_job_queue(self, user_id: str, job_id: str, match_data: Dict[str, Any]) -> Optional[str]:
        """Add job to user's application queue"""
        try:
            data = {
                'user_id': user_id,
                'job_id': job_id,
                'status': 'pending',
                'match_score': match_data.get('match_score'),
                'match_reasons': match_data.get('match_reasons', []),
                'ai_generated_cover_letter': match_data.get('cover_letter'),
                'priority': match_data.get('priority', 50),
                'created_at': datetime.now().isoformat()
            }
            
            # Set expiration (7 days from now)
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(days=7)
            data['expires_at'] = expires_at.isoformat()
            
            result = self.supabase.table('application_queue').insert(data).execute()
            
            if result.data:
                queue_id = result.data[0]['id']
                logger.info(f"Added job {job_id} to queue for user {user_id}: {queue_id}")
                return queue_id
            else:
                logger.error(f"Failed to add job to queue for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error adding job to queue for user {user_id}: {e}")
            return None
    
    async def update_queue_item(self, queue_id: str, updates: Dict[str, Any]) -> bool:
        """Update queue item"""
        try:
            updates['updated_at'] = datetime.now().isoformat()
            
            result = self.supabase.table('application_queue').update(updates).eq('id', queue_id).execute()
            
            if result.data:
                logger.info(f"Updated queue item {queue_id}")
                return True
            else:
                logger.warning(f"No queue item updated: {queue_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating queue item {queue_id}: {e}")
            return False
    
    async def get_job_matches(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get AI job matches for user"""
        try:
            result = (self.supabase.table('job_matches')
                     .select('*, jobs(*)')
                     .eq('user_id', user_id)
                     .eq('status', 'pending')
                     .order('match_score', desc=True)
                     .limit(limit)
                     .execute())
            
            matches = result.data or []
            
            for match in matches:
                # Convert JSONB and array fields
                if match.get('match_reasons'):
                    if isinstance(match['match_reasons'], str):
                        match['match_reasons'] = json.loads(match['match_reasons'])
                if match.get('missing_skills'):
                    if isinstance(match['missing_skills'], str):
                        match['missing_skills'] = json.loads(match['missing_skills'])
                if match.get('salary_fit_analysis'):
                    if isinstance(match['salary_fit_analysis'], str):
                        match['salary_fit_analysis'] = json.loads(match['salary_fit_analysis'])
            
            logger.info(f"Retrieved {len(matches)} job matches for user {user_id}")
            return matches
            
        except Exception as e:
            logger.error(f"Error getting job matches for user {user_id}: {e}")
            return []
    
    async def create_job_match(self, user_id: str, job_id: str, match_analysis: Dict[str, Any]) -> Optional[str]:
        """Create new job match record"""
        try:
            data = {
                'user_id': user_id,
                'job_id': job_id,
                'match_score': match_analysis.get('match_score'),
                'confidence_score': match_analysis.get('confidence_score'),
                'match_reasons': match_analysis.get('match_reasons', []),
                'missing_skills': match_analysis.get('missing_skills', []),
                'recommended_skills': match_analysis.get('recommended_skills', []),
                'salary_fit_analysis': json.dumps(match_analysis.get('salary_fit_analysis', {})),
                'location_compatibility': match_analysis.get('location_compatibility'),
                'status': 'pending',
                'model_version': match_analysis.get('model_version', '2.0'),
                'matching_criteria': json.dumps(match_analysis.get('matching_criteria', {})),
                'created_at': datetime.now().isoformat()
            }
            
            result = self.supabase.table('job_matches').insert(data).execute()
            
            if result.data:
                match_id = result.data[0]['id']
                logger.info(f"Created job match {match_id} for user {user_id}")
                return match_id
            else:
                logger.error(f"Failed to create job match for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating job match for user {user_id}: {e}")
            return None
    
    async def track_user_activity(self, user_id: str, action: str, resource_type: str = None, 
                                 resource_id: str = None, metadata: Dict = None) -> None:
        """Track user activity"""
        try:
            data = {
                'user_id': user_id,
                'action': action,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'metadata': json.dumps(metadata or {}),
                'created_at': datetime.now().isoformat()
            }
            
            self.supabase.table('user_activity').insert(data).execute()
            logger.debug(f"Tracked activity for user {user_id}: {action}")
            
        except Exception as e:
            logger.error(f"Error tracking user activity: {e}")
    
    async def update_last_active(self, user_id: str) -> None:
        """Update user's last active timestamp"""
        try:
            await self.update_user_profile(user_id, {
                'last_active_at': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error updating last active for user {user_id}: {e}")
    
    async def get_user_subscription_info(self, user_id: str) -> Dict[str, Any]:
        """Get user's subscription information"""
        try:
            # Get profile with subscription status
            profile = await self.get_user_profile(user_id)
            if not profile:
                return {'subscription_status': 'free', 'limits': {}}
            
            # Get subscription plan details
            plan_result = (self.supabase.table('subscription_plans')
                          .select('*')
                          .eq('slug', profile.get('subscription_status', 'free'))
                          .execute())
            
            plan = plan_result.data[0] if plan_result.data else None
            
            # Get usage tracking
            usage_result = (self.supabase.table('usage_tracking')
                           .select('*')
                           .eq('user_id', user_id)
                           .gte('period_start', datetime.now().replace(day=1).isoformat())
                           .execute())
            
            usage = {item['feature_name']: item['usage_count'] for item in usage_result.data} if usage_result.data else {}
            
            return {
                'subscription_status': profile.get('subscription_status', 'free'),
                'stripe_customer_id': profile.get('stripe_customer_id'),
                'plan_details': plan,
                'current_usage': usage,
                'profile_completion': profile.get('profile_completion_percentage', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription info for user {user_id}: {e}")
            return {'subscription_status': 'free', 'limits': {}}

# Global user service instance
_user_service = None

def get_user_service() -> UserService:
    """Get global user service instance"""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service