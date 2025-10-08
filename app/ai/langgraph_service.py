"""
Enhanced AI service using LangGraph workflows
Replaces direct AI calls with sophisticated workflow orchestration
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

from ..workflows.job_application_workflow import JobApplicationWorkflow
from ..workflows.database_integration import workflow_db_manager
from ..core.config import settings
from ..core.monitoring import performance_monitor
import structlog

logger = structlog.get_logger()


class LangGraphAIService:
    """
    Enhanced AI service that uses LangGraph workflows for complex operations
    Provides both simple AI calls and complex workflow orchestration
    """
    
    def __init__(self):
        self.logger = logger.bind(service="LangGraphAIService")
        
        # Initialize LLMs for different use cases
        self.fast_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            timeout=15
        )
        
        self.balanced_llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,
            timeout=30
        )
        
        # Initialize workflows
        self.job_application_workflow = JobApplicationWorkflow()
        
        # Workflow registry for dynamic execution
        self.workflows = {
            "job_application": self.job_application_workflow,
            # Future workflows can be added here
        }
    
    async def process_job_application(
        self,
        user_id: str,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        user_preferences: Dict[str, Any] = None,
        user_tier: str = "free"
    ) -> Dict[str, Any]:
        """
        Process a complete job application using LangGraph workflow
        
        This is the main entry point for end-to-end job application processing
        """
        try:
            self.logger.info("Starting job application processing",
                           user_id=user_id,
                           job_id=job_data.get("external_id"))
            
            # Prepare workflow parameters
            workflow_params = {
                "user_id": user_id,
                "job_id": job_data.get("external_id"),
                "job_data": job_data,
                "user_profile": user_profile,
                "user_preferences": user_preferences or {},
                "user_tier": user_tier
            }
            
            # Execute the job application workflow
            result = await self.job_application_workflow.execute(**workflow_params)
            
            # Extract key information for API response
            response = {
                "success": result.get("status") == "completed",
                "workflow_id": result.get("workflow_id"),
                "execution_id": result.get("execution_id"),
                "match_score": result.get("match_score", 0),
                "should_apply": result.get("application_submitted", False),
                "application_strategy": result.get("application_strategy"),
                "processing_time": result.get("processing_time_seconds", 0),
                "ai_cost": sum(resp.get("cost_usd", 0) for resp in result.get("ai_responses", {}).values()),
                "results": {
                    "job_analysis": result.get("analysis_results", {}),
                    "company_research": result.get("company_research", {}),
                    "cover_letter": result.get("cover_letter", {}),
                    "resume_optimizations": result.get("resume_optimizations", {}),
                    "application_timeline": result.get("application_timeline", {}),
                    "decisions": result.get("decisions", {}),
                    "actions_taken": result.get("actions_taken", [])
                },
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", [])
            }
            
            self.logger.info("Job application processing completed",
                           user_id=user_id,
                           success=response["success"],
                           match_score=response["match_score"])
            
            return response
            
        except Exception as e:
            self.logger.error("Job application processing failed",
                            user_id=user_id,
                            error=str(e))
            
            return {
                "success": False,
                "error": str(e),
                "workflow_id": None,
                "match_score": 0,
                "should_apply": False
            }
    
    async def batch_process_jobs(
        self,
        user_id: str,
        jobs: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        user_preferences: Dict[str, Any] = None,
        user_tier: str = "free",
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Process multiple jobs concurrently using workflows
        """
        try:
            self.logger.info("Starting batch job processing",
                           user_id=user_id,
                           job_count=len(jobs),
                           max_concurrent=max_concurrent)
            
            # Create semaphore to limit concurrent executions
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def process_single_job(job_data: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    return await self.process_job_application(
                        user_id=user_id,
                        job_data=job_data,
                        user_profile=user_profile,
                        user_preferences=user_preferences,
                        user_tier=user_tier
                    )
            
            # Process all jobs concurrently
            tasks = [process_single_job(job) for job in jobs]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error("Job processing failed in batch",
                                    job_index=i,
                                    error=str(result))
                    processed_results.append({
                        "success": False,
                        "error": str(result),
                        "job_id": jobs[i].get("external_id", f"job_{i}")
                    })
                else:
                    processed_results.append(result)
            
            # Sort by match score (highest first)
            successful_results = [r for r in processed_results if r.get("success", False)]
            successful_results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
            
            self.logger.info("Batch job processing completed",
                           total_jobs=len(jobs),
                           successful=len(successful_results))
            
            return processed_results
            
        except Exception as e:
            self.logger.error("Batch job processing failed",
                            user_id=user_id,
                            error=str(e))
            return []
    
    async def get_simple_ai_response(
        self,
        prompt: str,
        context: Dict[str, Any] = None,
        temperature: float = 0.3,
        model: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Get a simple AI response without full workflow orchestration
        Useful for quick queries and simple tasks
        """
        try:
            # Select appropriate LLM
            llm = self.balanced_llm if model == "balanced" else self.fast_llm
            
            # Prepare message
            messages = [HumanMessage(content=prompt)]
            
            # Add context if provided
            if context:
                context_str = f"Context: {context}\n\n{prompt}"
                messages = [HumanMessage(content=context_str)]
            
            # Get response
            start_time = datetime.utcnow()
            response = await llm.ainvoke(messages)
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Estimate cost (simplified)
            estimated_tokens = len(prompt.split()) + len(response.content.split())
            estimated_cost = estimated_tokens * 0.000002  # Rough estimate
            
            return {
                "success": True,
                "response": response.content,
                "processing_time": processing_time,
                "estimated_tokens": estimated_tokens,
                "estimated_cost": estimated_cost,
                "model": model
            }
            
        except Exception as e:
            self.logger.error("Simple AI response failed",
                            error=str(e))
            return {
                "success": False,
                "error": str(e),
                "response": None
            }
    
    async def analyze_job_match_only(
        self,
        job_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        user_tier: str = "free"
    ) -> Dict[str, Any]:
        """
        Analyze job match without full application workflow
        Useful for quick compatibility checking
        """
        try:
            from ..services.job_matcher import job_matching_engine, MatchingStrategy
            
            # Use existing job matching engine with hybrid strategy
            match_result = await job_matching_engine.match_job_to_user(
                job_data=job_data,
                user_profile=user_profile,
                strategy=MatchingStrategy.HYBRID,
                user_tier=user_tier
            )
            
            if match_result["success"]:
                return {
                    "success": True,
                    "match_score": match_result["overall_score"],
                    "recommendation": match_result["recommendation"],
                    "category_scores": match_result["category_scores"],
                    "success_probability": match_result.get("success_probability", 0.5),
                    "improvement_suggestions": match_result.get("improvement_suggestions", []),
                    "competitive_advantage": match_result.get("competitive_advantage", ""),
                    "red_flags": match_result.get("red_flags", []),
                    "processing_time": match_result.get("metadata", {}).get("processing_time_seconds", 0)
                }
            else:
                return {
                    "success": False,
                    "error": match_result.get("error", "Job matching failed"),
                    "match_score": 0
                }
                
        except Exception as e:
            self.logger.error("Job match analysis failed",
                            job_id=job_data.get("external_id"),
                            error=str(e))
            return {
                "success": False,
                "error": str(e),
                "match_score": 0
            }
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status and results of a running or completed workflow
        """
        try:
            execution_data = await workflow_db_manager.get_workflow_execution(workflow_id)
            
            if execution_data:
                return {
                    "workflow_id": execution_data["workflow_id"],
                    "status": execution_data["status"],
                    "started_at": execution_data["started_at"],
                    "completed_at": execution_data["completed_at"],
                    "current_node": execution_data["current_node"],
                    "match_score": execution_data["match_score"],
                    "processing_time": execution_data["processing_time_seconds"],
                    "ai_cost": execution_data["ai_cost_usd"],
                    "errors": execution_data["errors"],
                    "warnings": execution_data["warnings"],
                    "results": execution_data["results"]
                }
            else:
                return None
                
        except Exception as e:
            self.logger.error("Failed to get workflow status",
                            workflow_id=workflow_id,
                            error=str(e))
            return None
    
    async def get_user_workflow_history(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get workflow execution history for a user
        """
        try:
            history = await workflow_db_manager.get_user_workflow_history(user_id, limit)
            
            # Format for API response
            formatted_history = []
            for execution in history:
                formatted_history.append({
                    "workflow_id": execution["workflow_id"],
                    "workflow_type": execution["workflow_type"], 
                    "job_id": execution["job_id"],
                    "status": execution["status"],
                    "started_at": execution["started_at"],
                    "completed_at": execution["completed_at"],
                    "match_score": execution["match_score"],
                    "processing_time": execution["processing_time_seconds"],
                    "ai_cost": execution["ai_cost_usd"],
                    "application_submitted": any(
                        action.get("action") == "submit_application" 
                        for action in execution.get("actions_taken", [])
                    )
                })
            
            return formatted_history
            
        except Exception as e:
            self.logger.error("Failed to get user workflow history",
                            user_id=user_id,
                            error=str(e))
            return []
    
    async def get_user_analytics(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get analytics summary for a user
        """
        try:
            analytics = await workflow_db_manager.get_workflow_analytics_summary(user_id, days)
            
            return {
                "total_workflows": analytics.get("total_workflows", 0),
                "successful_workflows": analytics.get("successful_workflows", 0),
                "applications_submitted": analytics.get("applications_submitted", 0),
                "average_match_score": round(analytics.get("avg_match_score", 0), 1),
                "total_ai_spend": round(analytics.get("total_ai_spend", 0), 4),
                "average_processing_time": round(analytics.get("avg_processing_time", 0), 2),
                "success_rate": round(
                    analytics.get("successful_workflows", 0) / max(analytics.get("total_workflows", 1), 1),
                    2
                ),
                "application_rate": round(
                    analytics.get("applications_submitted", 0) / max(analytics.get("total_workflows", 1), 1),
                    2
                )
            }
            
        except Exception as e:
            self.logger.error("Failed to get user analytics",
                            user_id=user_id,
                            error=str(e))
            return {}


# Global service instance
langgraph_ai_service = LangGraphAIService()


# Export public interfaces
__all__ = [
    "LangGraphAIService",
    "langgraph_ai_service"
]