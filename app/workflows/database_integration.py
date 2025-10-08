"""
Database integration for LangGraph workflows
Connects workflows with existing Supabase/PostgreSQL database
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import asyncio

from sqlalchemy import Column, String, DateTime, Integer, Text, Float, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

try:
    from ..core.database import database, Base
    from ..core.config import settings
except ImportError:
    # For testing without full database setup
    database = None
    Base = declarative_base()
    settings = None
from .base import BaseWorkflowState, WorkflowStatus
import structlog

logger = structlog.get_logger()


class WorkflowExecution(Base):
    """Database model for workflow executions"""
    __tablename__ = "workflow_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(String, unique=True, nullable=False, index=True)
    workflow_type = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=True, index=True)
    
    status = Column(String, nullable=False, default=WorkflowStatus.PENDING.value)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    current_node = Column(String, nullable=True)
    
    # JSON fields for flexible data storage
    initial_state = Column(JSON, nullable=True)
    final_state = Column(JSON, nullable=True)
    user_profile = Column(JSON, nullable=True)
    job_data = Column(JSON, nullable=True)
    company_data = Column(JSON, nullable=True)
    
    # Results and metrics
    analysis_results = Column(JSON, nullable=True)
    decisions = Column(JSON, nullable=True)
    actions_taken = Column(JSON, nullable=True)
    results = Column(JSON, nullable=True)
    
    # Performance metrics
    match_score = Column(Float, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    ai_cost_usd = Column(Float, nullable=True, default=0.0)
    
    # Error handling
    errors = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    
    # Metadata
    user_tier = Column(String, nullable=True, default="free")
    config = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobApplication(Base):
    """Database model for job applications"""
    __tablename__ = "job_applications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=False, index=True)
    workflow_execution_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Application details
    application_status = Column(String, nullable=False, default="pending")  # pending, submitted, rejected, interview, etc.
    applied_at = Column(DateTime, nullable=True)
    application_method = Column(String, nullable=True)  # api, manual, email
    
    # Generated content
    cover_letter = Column(JSON, nullable=True)
    resume_optimizations = Column(JSON, nullable=True)
    
    # Matching and scoring
    match_score = Column(Float, nullable=True)
    success_probability = Column(Float, nullable=True)
    recommendation = Column(String, nullable=True)
    
    # Follow-up tracking
    follow_up_scheduled = Column(Boolean, default=False)
    follow_up_timeline = Column(JSON, nullable=True)
    last_follow_up = Column(DateTime, nullable=True)
    
    # Response tracking
    employer_response = Column(String, nullable=True)  # no_response, rejection, interview_request, etc.
    response_received_at = Column(DateTime, nullable=True)
    interview_scheduled = Column(Boolean, default=False)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowAnalytics(Base):
    """Database model for workflow analytics"""
    __tablename__ = "workflow_analytics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_execution_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Performance metrics
    total_processing_time = Column(Float, nullable=True)
    ai_processing_time = Column(Float, nullable=True)
    node_count = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    warning_count = Column(Integer, nullable=True)
    
    # AI usage metrics
    ai_calls_made = Column(Integer, nullable=True, default=0)
    total_tokens_used = Column(Integer, nullable=True, default=0)
    total_ai_cost = Column(Float, nullable=True, default=0.0)
    
    # Success metrics
    workflow_success = Column(Boolean, nullable=True)
    application_submitted = Column(Boolean, nullable=True)
    match_quality_score = Column(Float, nullable=True)
    
    # User tier for cost analysis
    user_tier = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WorkflowDatabaseManager:
    """Manages database operations for LangGraph workflows"""
    
    def __init__(self):
        self.logger = logger.bind(component="WorkflowDatabaseManager")
    
    async def save_workflow_execution(self, state: BaseWorkflowState, workflow_type: str) -> str:
        """Save workflow execution to database"""
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
            
            execution_data = {
                "workflow_id": state["workflow_id"],
                "workflow_type": workflow_type,
                "user_id": state["user_id"],
                "job_id": state.get("job_id"),
                "status": state.get("status", WorkflowStatus.PENDING.value).value if hasattr(state.get("status"), 'value') else str(state.get("status", WorkflowStatus.PENDING.value)),
                "started_at": state.get("started_at"),
                "completed_at": state.get("completed_at"),
                "current_node": state.get("current_node"),
                "initial_state": self._sanitize_json(state),
                "final_state": self._sanitize_json(state),
                "user_profile": state.get("user_profile", {}),
                "job_data": state.get("job_data", {}),
                "company_data": state.get("company_data", {}),
                "analysis_results": state.get("analysis_results", {}),
                "decisions": state.get("decisions", {}),
                "actions_taken": state.get("actions_taken", []),
                "results": state.get("results", {}),
                "match_score": state.get("match_score"),
                "processing_time_seconds": processing_time,
                "ai_cost_usd": ai_cost,
                "errors": state.get("errors", []),
                "warnings": state.get("warnings", []),
                "user_tier": state.get("user_tier", "free"),
                "config": state.get("config", {})
            }
            
            # Insert or update workflow execution
            query = """
                INSERT INTO workflow_executions (
                    workflow_id, workflow_type, user_id, job_id, status, started_at, completed_at,
                    current_node, initial_state, final_state, user_profile, job_data, company_data,
                    analysis_results, decisions, actions_taken, results, match_score, 
                    processing_time_seconds, ai_cost_usd, errors, warnings, user_tier, config
                ) VALUES (
                    :workflow_id, :workflow_type, :user_id, :job_id, :status, :started_at, :completed_at,
                    :current_node, :initial_state, :final_state, :user_profile, :job_data, :company_data,
                    :analysis_results, :decisions, :actions_taken, :results, :match_score,
                    :processing_time_seconds, :ai_cost_usd, :errors, :warnings, :user_tier, :config
                )
                ON CONFLICT (workflow_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    completed_at = EXCLUDED.completed_at,
                    current_node = EXCLUDED.current_node,
                    final_state = EXCLUDED.final_state,
                    analysis_results = EXCLUDED.analysis_results,
                    decisions = EXCLUDED.decisions,
                    actions_taken = EXCLUDED.actions_taken,
                    results = EXCLUDED.results,
                    match_score = EXCLUDED.match_score,
                    processing_time_seconds = EXCLUDED.processing_time_seconds,
                    ai_cost_usd = EXCLUDED.ai_cost_usd,
                    errors = EXCLUDED.errors,
                    warnings = EXCLUDED.warnings,
                    updated_at = NOW()
                RETURNING id
            """
            
            result = await database.fetch_one(query, execution_data)
            execution_id = result["id"] if result else None
            
            self.logger.info("Workflow execution saved",
                           workflow_id=state["workflow_id"],
                           execution_id=str(execution_id))
            
            return str(execution_id)
            
        except Exception as e:
            self.logger.error("Failed to save workflow execution", 
                            workflow_id=state.get("workflow_id"),
                            error=str(e))
            raise
    
    async def save_job_application(self, state: BaseWorkflowState, execution_id: str) -> str:
        """Save job application details to database"""
        try:
            application_data = {
                "user_id": state["user_id"],
                "job_id": state.get("job_id"),
                "workflow_execution_id": execution_id,
                "application_status": "submitted" if state.get("application_submitted") else "pending",
                "applied_at": datetime.utcnow() if state.get("application_submitted") else None,
                "application_method": "api",  # Default method
                "cover_letter": state.get("cover_letter", {}),
                "resume_optimizations": state.get("resume_optimizations", {}),
                "match_score": state.get("match_score"),
                "success_probability": state.get("analysis_results", {}).get("job_match", {}).get("success_probability"),
                "recommendation": state.get("analysis_results", {}).get("job_match", {}).get("recommendation"),
                "follow_up_scheduled": state.get("follow_up_scheduled", False),
                "follow_up_timeline": state.get("application_timeline", {})
            }
            
            query = """
                INSERT INTO job_applications (
                    user_id, job_id, workflow_execution_id, application_status, applied_at,
                    application_method, cover_letter, resume_optimizations, match_score,
                    success_probability, recommendation, follow_up_scheduled, follow_up_timeline
                ) VALUES (
                    :user_id, :job_id, :workflow_execution_id, :application_status, :applied_at,
                    :application_method, :cover_letter, :resume_optimizations, :match_score,
                    :success_probability, :recommendation, :follow_up_scheduled, :follow_up_timeline
                )
                RETURNING id
            """
            
            result = await database.fetch_one(query, application_data)
            application_id = result["id"] if result else None
            
            self.logger.info("Job application saved",
                           job_id=state.get("job_id"),
                           application_id=str(application_id))
            
            return str(application_id)
            
        except Exception as e:
            self.logger.error("Failed to save job application",
                            job_id=state.get("job_id"),
                            error=str(e))
            raise
    
    async def save_workflow_analytics(self, state: BaseWorkflowState, execution_id: str):
        """Save workflow analytics data"""
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
            
            analytics_data = {
                "workflow_execution_id": execution_id,
                "user_id": state["user_id"],
                "total_processing_time": processing_time,
                "ai_processing_time": sum(response.get("processing_time", 0) 
                                        for response in state.get("ai_responses", {}).values()),
                "node_count": len(state.get("progress", {})),
                "error_count": len(state.get("errors", [])),
                "warning_count": len(state.get("warnings", [])),
                "ai_calls_made": ai_calls,
                "total_tokens_used": total_tokens,
                "total_ai_cost": total_cost,
                "workflow_success": state.get("status") == WorkflowStatus.COMPLETED,
                "application_submitted": state.get("application_submitted", False),
                "match_quality_score": state.get("match_score"),
                "user_tier": state.get("user_tier", "free")
            }
            
            query = """
                INSERT INTO workflow_analytics (
                    workflow_execution_id, user_id, total_processing_time, ai_processing_time,
                    node_count, error_count, warning_count, ai_calls_made, total_tokens_used,
                    total_ai_cost, workflow_success, application_submitted, match_quality_score, user_tier
                ) VALUES (
                    :workflow_execution_id, :user_id, :total_processing_time, :ai_processing_time,
                    :node_count, :error_count, :warning_count, :ai_calls_made, :total_tokens_used,
                    :total_ai_cost, :workflow_success, :application_submitted, :match_quality_score, :user_tier
                )
            """
            
            await database.execute(query, analytics_data)
            
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
            query = "SELECT * FROM workflow_executions WHERE workflow_id = :workflow_id"
            result = await database.fetch_one(query, {"workflow_id": workflow_id})
            return dict(result) if result else None
            
        except Exception as e:
            self.logger.error("Failed to retrieve workflow execution",
                            workflow_id=workflow_id,
                            error=str(e))
            return None
    
    async def get_user_workflow_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get workflow history for a user"""
        try:
            query = """
                SELECT * FROM workflow_executions 
                WHERE user_id = :user_id 
                ORDER BY created_at DESC 
                LIMIT :limit
            """
            results = await database.fetch_all(query, {"user_id": user_id, "limit": limit})
            return [dict(result) for result in results]
            
        except Exception as e:
            self.logger.error("Failed to retrieve user workflow history",
                            user_id=user_id,
                            error=str(e))
            return []
    
    async def get_workflow_analytics_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get workflow analytics summary for a user"""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_workflows,
                    COUNT(CASE WHEN workflow_success THEN 1 END) as successful_workflows,
                    COUNT(CASE WHEN application_submitted THEN 1 END) as applications_submitted,
                    AVG(match_quality_score) as avg_match_score,
                    SUM(total_ai_cost) as total_ai_spend,
                    AVG(total_processing_time) as avg_processing_time
                FROM workflow_analytics wa
                JOIN workflow_executions we ON wa.workflow_execution_id = we.id
                WHERE wa.user_id = :user_id 
                AND wa.created_at >= NOW() - INTERVAL ':days days'
            """
            
            result = await database.fetch_one(query, {"user_id": user_id, "days": days})
            return dict(result) if result else {}
            
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
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_json(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_json(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data


# Global database manager instance
workflow_db_manager = WorkflowDatabaseManager()


# Export public interfaces
__all__ = [
    "WorkflowExecution",
    "JobApplication", 
    "WorkflowAnalytics",
    "WorkflowDatabaseManager",
    "workflow_db_manager"
]