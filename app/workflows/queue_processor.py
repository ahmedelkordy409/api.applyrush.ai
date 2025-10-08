"""
Queue Processor for LangGraph Workflows
Processes jobs from user queues using LangGraph workflows
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

try:
    from ..core.database import database
    from ..core.monitoring import performance_monitor
except ImportError:
    database = None
    performance_monitor = None

from ..services.user_management_service import user_management_service
from ..ai.langgraph_service import langgraph_ai_service
from ..models.user_settings import QueuePriority
import structlog

logger = structlog.get_logger()


class QueueProcessor:
    """
    Processes jobs from user queues using LangGraph workflows
    Integrates user settings with workflow execution
    """
    
    def __init__(self):
        self.logger = logger.bind(service="QueueProcessor")
        self.processing = False
        self.max_concurrent_jobs = 10
        self.processing_semaphore = asyncio.Semaphore(self.max_concurrent_jobs)
    
    async def start_processing(self, interval_seconds: int = 30):
        """Start continuous queue processing"""
        if self.processing:
            self.logger.warning("Queue processing already running")
            return
        
        self.processing = True
        self.logger.info("Starting queue processor", interval=interval_seconds)
        
        try:
            while self.processing:
                await self.process_queue_batch()
                await asyncio.sleep(interval_seconds)
        except Exception as e:
            self.logger.error("Queue processor crashed", error=str(e))
        finally:
            self.processing = False
            self.logger.info("Queue processor stopped")
    
    async def stop_processing(self):
        """Stop queue processing"""
        self.processing = False
        self.logger.info("Queue processor stop requested")
    
    async def process_queue_batch(self, batch_size: int = 20):
        """Process a batch of items from the queue"""
        try:
            # Get next items to process
            queue_items = await user_management_service.get_next_queue_items(batch_size)
            
            if not queue_items:
                return
            
            self.logger.info("Processing queue batch", item_count=len(queue_items))
            
            # Process items concurrently with semaphore limit
            tasks = []
            for item in queue_items:
                task = asyncio.create_task(self._process_queue_item(item))
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log results
            successful = sum(1 for r in results if r is True)
            failed = len(results) - successful
            
            self.logger.info("Queue batch processed", 
                           successful=successful, 
                           failed=failed, 
                           total=len(results))
            
        except Exception as e:
            self.logger.error("Failed to process queue batch", error=str(e))
    
    async def _process_queue_item(self, queue_item: Dict[str, Any]) -> bool:
        """Process a single queue item"""
        queue_id = queue_item["id"]
        user_id = queue_item["user_id"]
        job_id = queue_item["job_id"]
        
        async with self.processing_semaphore:
            try:
                self.logger.info("Processing queue item", 
                               queue_id=str(queue_id), 
                               user_id=user_id, 
                               job_id=job_id)
                
                # Mark as processing
                await user_management_service.update_queue_item(
                    user_id, str(queue_id), {
                        "status": "processing",
                        "processed_at": datetime.utcnow()
                    }
                )
                
                # Get user profile and settings
                user_profile = await user_management_service.get_user_profile(user_id)
                search_settings = await user_management_service.get_search_settings(user_id)
                
                if not user_profile or not search_settings:
                    raise Exception("User profile or search settings not found")
                
                # Check if user search is still active
                if search_settings.get("search_status") != "active":
                    self.logger.info("Skipping job - user search not active", 
                                   user_id=user_id, 
                                   status=search_settings.get("search_status"))
                    
                    await user_management_service.update_queue_item(
                        user_id, str(queue_id), {
                            "status": "skipped",
                            "processing_error": "User search not active"
                        }
                    )
                    return True
                
                # Check daily application limits
                daily_limit = search_settings.get("max_applications_per_day", 10)
                applications_today = await self._count_applications_today(user_id)
                
                if applications_today >= daily_limit:
                    self.logger.info("Daily application limit reached", 
                                   user_id=user_id, 
                                   limit=daily_limit, 
                                   count=applications_today)
                    
                    # Reschedule for tomorrow
                    tomorrow = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    await user_management_service.update_queue_item(
                        user_id, str(queue_id), {
                            "status": "queued",
                            "scheduled_for": tomorrow,
                            "processing_error": "Daily application limit reached"
                        }
                    )
                    return True
                
                # Prepare job data
                job_data = queue_item["job_data"]
                if isinstance(job_data, str):
                    job_data = json.loads(job_data)
                
                # Process with LangGraph workflow
                workflow_result = await langgraph_ai_service.process_job_application(
                    user_id=user_id,
                    job_data=job_data,
                    user_profile=user_profile,
                    user_preferences=search_settings,
                    user_tier=user_profile.get("user_tier", "free")
                )
                
                # Update queue item with results
                update_data = {
                    "status": "completed",
                    "application_submitted": workflow_result.get("should_apply", False),
                    "workflow_execution_id": workflow_result.get("execution_id")
                }
                
                if workflow_result.get("should_apply"):
                    update_data["application_id"] = workflow_result.get("application_id")
                
                if not workflow_result.get("success"):
                    update_data["processing_error"] = workflow_result.get("error", "Workflow failed")
                    update_data["status"] = "failed"
                
                await user_management_service.update_queue_item(
                    user_id, str(queue_id), update_data
                )
                
                self.logger.info("Queue item processed successfully", 
                               queue_id=str(queue_id), 
                               application_submitted=workflow_result.get("should_apply", False))
                
                return True
                
            except Exception as e:
                self.logger.error("Failed to process queue item", 
                                queue_id=str(queue_id), 
                                error=str(e))
                
                # Mark as failed
                await user_management_service.update_queue_item(
                    user_id, str(queue_id), {
                        "status": "failed",
                        "processing_error": str(e)
                    }
                )
                
                return False
    
    async def _count_applications_today(self, user_id: str) -> int:
        """Count applications submitted today for user"""
        try:
            if not database:
                return 0
                
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            query = """
                SELECT COUNT(*) as count 
                FROM user_queues 
                WHERE user_id = :user_id 
                AND application_submitted = TRUE 
                AND processed_at >= :today_start
            """
            
            result = await database.fetch_one(query, {
                "user_id": user_id,
                "today_start": today_start
            })
            
            return result["count"] if result else 0
            
        except Exception as e:
            self.logger.error("Failed to count applications today", user_id=user_id, error=str(e))
            return 0
    
    async def process_single_job(self, user_id: str, job_data: Dict[str, Any], priority: QueuePriority = QueuePriority.NORMAL) -> Dict[str, Any]:
        """Process a single job immediately (bypass queue)"""
        try:
            self.logger.info("Processing single job", user_id=user_id, job_id=job_data.get("external_id"))
            
            # Get user data
            user_profile = await user_management_service.get_user_profile(user_id)
            search_settings = await user_management_service.get_search_settings(user_id)
            
            if not user_profile:
                return {"success": False, "error": "User profile not found"}
            
            # Process with LangGraph workflow
            result = await langgraph_ai_service.process_job_application(
                user_id=user_id,
                job_data=job_data,
                user_profile=user_profile,
                user_preferences=search_settings or {},
                user_tier=user_profile.get("user_tier", "free")
            )
            
            self.logger.info("Single job processed", 
                           user_id=user_id, 
                           success=result.get("success", False))
            
            return result
            
        except Exception as e:
            self.logger.error("Failed to process single job", user_id=user_id, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def priority_process_queue_item(self, queue_id: str) -> Dict[str, Any]:
        """Process a specific queue item with priority"""
        try:
            # Get queue item
            if not database:
                return {"success": False, "error": "Database not available"}
                
            query = "SELECT * FROM user_queues WHERE id = :queue_id AND status = 'queued'"
            result = await database.fetch_one(query, {"queue_id": queue_id})
            
            if not result:
                return {"success": False, "error": "Queue item not found or not in queued status"}
            
            queue_item = dict(result)
            
            # Process the item
            success = await self._process_queue_item(queue_item)
            
            return {
                "success": success,
                "queue_id": queue_id,
                "message": "Queue item processed successfully" if success else "Queue item processing failed"
            }
            
        except Exception as e:
            self.logger.error("Failed to priority process queue item", queue_id=queue_id, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get queue processing statistics"""
        try:
            if not database:
                return {}
                
            # Get overall queue stats
            stats_query = """
                SELECT 
                    COUNT(*) as total_items,
                    COUNT(CASE WHEN status = 'queued' THEN 1 END) as queued,
                    COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                    COUNT(CASE WHEN application_submitted = TRUE THEN 1 END) as applications_submitted
                FROM user_queues 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """
            
            stats_result = await database.fetch_one(stats_query)
            
            # Get processing rate (items per hour)
            rate_query = """
                SELECT COUNT(*) as processed_last_hour
                FROM user_queues 
                WHERE processed_at >= NOW() - INTERVAL '1 hour'
            """
            
            rate_result = await database.fetch_one(rate_query)
            
            return {
                "processing": self.processing,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "last_24_hours": {
                    "total_items": stats_result["total_items"] if stats_result else 0,
                    "queued": stats_result["queued"] if stats_result else 0,
                    "processing": stats_result["processing"] if stats_result else 0,
                    "completed": stats_result["completed"] if stats_result else 0,
                    "failed": stats_result["failed"] if stats_result else 0,
                    "applications_submitted": stats_result["applications_submitted"] if stats_result else 0
                },
                "processing_rate": {
                    "items_per_hour": rate_result["processed_last_hour"] if rate_result else 0
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get processing stats", error=str(e))
            return {"error": str(e)}


# Global queue processor instance
queue_processor = QueueProcessor()

# Export processor
__all__ = ["QueueProcessor", "queue_processor"]