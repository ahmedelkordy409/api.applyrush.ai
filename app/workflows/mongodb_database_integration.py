"""
MongoDB database integration for LangGraph workflows
Replaces the PostgreSQL/Supabase database integration
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
from bson import ObjectId

from app.models.mongodb_models import (
    WorkflowExecution, WorkflowJobApplication, WorkflowAnalytics
)
from .base import BaseWorkflowState, WorkflowStatus

logger = structlog.get_logger()


class MongoDBWorkflowDatabaseManager:
    """Manages MongoDB operations for LangGraph workflows"""

    def __init__(self):
        self.logger = logger.bind(component="MongoDBWorkflowDatabaseManager")

    async def save_workflow_execution(self, state: BaseWorkflowState, workflow_type: str) -> str:
        """Save workflow execution to MongoDB"""
        try:
            # Calculate processing time
            processing_time = 0.0
            if state.get("completed_at") and state.get("started_at"):
                processing_time = (state["completed_at"] - state["started_at"]).total_seconds()

            # Calculate total AI cost
            ai_cost = 0.0
            ai_responses = state.get("ai_responses", {})
            for response_data in ai_responses.values():
                ai_cost += response_data.get("cost_usd", 0)

            # Check if execution already exists
            existing_execution = await WorkflowExecution.find_one(
                WorkflowExecution.workflow_id == state["workflow_id"]
            )

            if existing_execution:
                # Update existing execution
                existing_execution.status = str(state.get("status", WorkflowStatus.PENDING.value))
                existing_execution.completed_at = state.get("completed_at")
                existing_execution.current_node = state.get("current_node")
                existing_execution.final_state = self._sanitize_json(state)
                existing_execution.analysis_results = state.get("analysis_results", {})
                existing_execution.decisions = state.get("decisions", {})
                existing_execution.actions_taken = state.get("actions_taken", [])
                existing_execution.results = state.get("results", {})
                existing_execution.match_score = state.get("match_score")
                existing_execution.processing_time_seconds = processing_time
                existing_execution.ai_cost_usd = ai_cost
                existing_execution.errors = state.get("errors", [])
                existing_execution.warnings = state.get("warnings", [])
                existing_execution.updated_at = datetime.utcnow()

                await existing_execution.save()
                execution_id = str(existing_execution.id)

            else:
                # Create new execution
                execution = WorkflowExecution(
                    workflow_id=state["workflow_id"],
                    workflow_type=workflow_type,
                    user_id=state["user_id"],
                    job_id=state.get("job_id"),
                    status=str(state.get("status", WorkflowStatus.PENDING.value)),
                    started_at=state.get("started_at", datetime.utcnow()),
                    completed_at=state.get("completed_at"),
                    current_node=state.get("current_node"),
                    initial_state=self._sanitize_json(state),
                    final_state=self._sanitize_json(state),
                    user_profile=state.get("user_profile", {}),
                    job_data=state.get("job_data", {}),
                    company_data=state.get("company_data", {}),
                    analysis_results=state.get("analysis_results", {}),
                    decisions=state.get("decisions", {}),
                    actions_taken=state.get("actions_taken", []),
                    results=state.get("results", {}),
                    match_score=state.get("match_score"),
                    processing_time_seconds=processing_time,
                    ai_cost_usd=ai_cost,
                    errors=state.get("errors", []),
                    warnings=state.get("warnings", []),
                    user_tier=state.get("user_tier", "free"),
                    config=state.get("config", {})
                )

                await execution.insert()
                execution_id = str(execution.id)

            self.logger.info("Workflow execution saved",
                           workflow_id=state["workflow_id"],
                           execution_id=execution_id)

            return execution_id

        except Exception as e:
            self.logger.error("Failed to save workflow execution",
                            workflow_id=state.get("workflow_id"),
                            error=str(e))
            raise

    async def save_job_application(self, state: BaseWorkflowState, execution_id: str) -> str:
        """Save job application details to MongoDB"""
        try:
            application = WorkflowJobApplication(
                user_id=state["user_id"],
                job_id=state.get("job_id"),
                workflow_execution_id=ObjectId(execution_id),
                application_status="submitted" if state.get("application_submitted") else "pending",
                applied_at=datetime.utcnow() if state.get("application_submitted") else None,
                application_method="api",  # Default method
                cover_letter=state.get("cover_letter", {}),
                resume_optimizations=state.get("resume_optimizations", {}),
                match_score=state.get("match_score"),
                success_probability=state.get("analysis_results", {}).get("job_match", {}).get("success_probability"),
                recommendation=state.get("analysis_results", {}).get("job_match", {}).get("recommendation"),
                follow_up_scheduled=state.get("follow_up_scheduled", False),
                follow_up_timeline=state.get("application_timeline", {})
            )

            await application.insert()

            self.logger.info("Job application saved",
                           job_id=state.get("job_id"),
                           application_id=str(application.id))

            return str(application.id)

        except Exception as e:
            self.logger.error("Failed to save job application",
                            job_id=state.get("job_id"),
                            error=str(e))
            raise

    async def save_workflow_analytics(self, state: BaseWorkflowState, execution_id: str):
        """Save workflow analytics data to MongoDB"""
        try:
            # Calculate metrics
            processing_time = 0.0
            if state.get("completed_at") and state.get("started_at"):
                processing_time = (state["completed_at"] - state["started_at"]).total_seconds()

            ai_calls = len(state.get("ai_responses", {}))
            total_tokens = sum(response.get("estimated_tokens", 0)
                             for response in state.get("ai_responses", {}).values())
            total_cost = sum(response.get("cost_usd", 0)
                           for response in state.get("ai_responses", {}).values())

            analytics = WorkflowAnalytics(
                workflow_execution_id=ObjectId(execution_id),
                user_id=state["user_id"],
                total_processing_time=processing_time,
                ai_processing_time=sum(response.get("processing_time", 0)
                                     for response in state.get("ai_responses", {}).values()),
                node_count=len(state.get("progress", {})),
                error_count=len(state.get("errors", [])),
                warning_count=len(state.get("warnings", [])),
                ai_calls_made=ai_calls,
                total_tokens_used=total_tokens,
                total_ai_cost=total_cost,
                workflow_success=state.get("status") == WorkflowStatus.COMPLETED,
                application_submitted=state.get("application_submitted", False),
                match_quality_score=state.get("match_score"),
                user_tier=state.get("user_tier", "free")
            )

            await analytics.insert()

            self.logger.info("Workflow analytics saved",
                           execution_id=execution_id,
                           ai_cost=total_cost)

        except Exception as e:
            self.logger.error("Failed to save workflow analytics",
                            execution_id=execution_id,
                            error=str(e))
            raise

    async def get_workflow_execution(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve workflow execution by ID"""
        try:
            execution = await WorkflowExecution.find_one(
                WorkflowExecution.workflow_id == workflow_id
            )
            return execution.dict() if execution else None

        except Exception as e:
            self.logger.error("Failed to retrieve workflow execution",
                            workflow_id=workflow_id,
                            error=str(e))
            return None

    async def get_user_workflow_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get workflow history for a user"""
        try:
            executions = await WorkflowExecution.find(
                WorkflowExecution.user_id == user_id
            ).sort(-WorkflowExecution.created_at).limit(limit).to_list()

            return [execution.dict() for execution in executions]

        except Exception as e:
            self.logger.error("Failed to retrieve user workflow history",
                            user_id=user_id,
                            error=str(e))
            return []

    async def get_workflow_analytics_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get workflow analytics summary for a user"""
        try:
            # Calculate date threshold
            threshold_date = datetime.utcnow() - datetime.timedelta(days=days)

            # Get all analytics for the user in the time period
            analytics_list = await WorkflowAnalytics.find(
                WorkflowAnalytics.user_id == user_id,
                WorkflowAnalytics.created_at >= threshold_date
            ).to_list()

            if not analytics_list:
                return {}

            # Calculate summary statistics
            total_workflows = len(analytics_list)
            successful_workflows = sum(1 for a in analytics_list if a.workflow_success)
            applications_submitted = sum(1 for a in analytics_list if a.application_submitted)
            total_ai_spend = sum(a.total_ai_cost for a in analytics_list)
            avg_processing_time = sum(a.total_processing_time or 0 for a in analytics_list) / total_workflows

            # Calculate average match score (only for non-None values)
            match_scores = [a.match_quality_score for a in analytics_list if a.match_quality_score is not None]
            avg_match_score = sum(match_scores) / len(match_scores) if match_scores else None

            return {
                'total_workflows': total_workflows,
                'successful_workflows': successful_workflows,
                'applications_submitted': applications_submitted,
                'avg_match_score': avg_match_score,
                'total_ai_spend': total_ai_spend,
                'avg_processing_time': avg_processing_time
            }

        except Exception as e:
            self.logger.error("Failed to retrieve workflow analytics",
                            user_id=user_id,
                            error=str(e))
            return {}

    def _sanitize_json(self, data: Any) -> Any:
        """Sanitize data for JSON storage"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if isinstance(value, datetime):
                    sanitized[key] = value.isoformat()
                elif isinstance(value, ObjectId):
                    sanitized[key] = str(value)
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_json(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_json(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, ObjectId):
            return str(data)
        else:
            return data


# Global MongoDB database manager instance
mongodb_workflow_db_manager = MongoDBWorkflowDatabaseManager()


# Export public interfaces
__all__ = [
    "MongoDBWorkflowDatabaseManager",
    "mongodb_workflow_db_manager"
]