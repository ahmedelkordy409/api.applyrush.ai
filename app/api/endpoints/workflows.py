"""
API endpoints for LangGraph workflows
Provides REST API access to workflow orchestration capabilities
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from datetime import datetime

from ...ai.langgraph_service import langgraph_ai_service
from ...core.monitoring import performance_monitor
from ...models.api_models import UserProfile, JobData
import structlog

logger = structlog.get_logger()

router = APIRouter()


class JobApplicationRequest(BaseModel):
    """Request model for job application processing"""
    user_id: str = Field(..., description="User identifier")
    job_data: Dict[str, Any] = Field(..., description="Job posting data")
    user_profile: Dict[str, Any] = Field(..., description="User profile information")
    user_preferences: Optional[Dict[str, Any]] = Field(default={}, description="User preferences")
    user_tier: str = Field(default="free", description="User subscription tier")


class BatchJobApplicationRequest(BaseModel):
    """Request model for batch job application processing"""
    user_id: str = Field(..., description="User identifier")
    jobs: List[Dict[str, Any]] = Field(..., description="List of job postings")
    user_profile: Dict[str, Any] = Field(..., description="User profile information")
    user_preferences: Optional[Dict[str, Any]] = Field(default={}, description="User preferences")
    user_tier: str = Field(default="free", description="User subscription tier")
    max_concurrent: int = Field(default=5, description="Maximum concurrent processing")


class JobMatchRequest(BaseModel):
    """Request model for job matching analysis"""
    job_data: Dict[str, Any] = Field(..., description="Job posting data")
    user_profile: Dict[str, Any] = Field(..., description="User profile information")
    user_tier: str = Field(default="free", description="User subscription tier")


class SimpleAIRequest(BaseModel):
    """Request model for simple AI queries"""
    prompt: str = Field(..., description="AI prompt")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    temperature: float = Field(default=0.3, description="AI temperature setting")
    model: str = Field(default="balanced", description="Model preference")


@router.post("/job-application", response_model=Dict[str, Any])
async def process_job_application(
    request: JobApplicationRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Process a complete job application using LangGraph workflow
    
    This endpoint handles the entire job application pipeline:
    - Job analysis and matching
    - Company research  
    - Application decision making
    - Resume optimization
    - Cover letter generation
    - Application submission
    - Follow-up scheduling
    """
    try:
        logger.info("Processing job application",
                   user_id=request.user_id,
                   job_id=request.job_data.get("external_id"))
        
        # Record API usage
        performance_monitor.record_api_call("job_application_workflow")
        
        # Process the job application
        result = await langgraph_ai_service.process_job_application(
            user_id=request.user_id,
            job_data=request.job_data,
            user_profile=request.user_profile,
            user_preferences=request.user_preferences,
            user_tier=request.user_tier
        )
        
        # Record metrics in background
        background_tasks.add_task(
            performance_monitor.record_workflow_completion,
            workflow_type="job_application",
            success=result["success"],
            processing_time=result.get("processing_time", 0),
            user_tier=request.user_tier
        )
        
        return {
            "status": "success" if result["success"] else "failed",
            "data": result,
            "message": "Job application processed successfully" if result["success"] else "Job application processing failed"
        }
        
    except Exception as e:
        logger.error("Job application processing failed",
                    user_id=request.user_id,
                    error=str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"Job application processing failed: {str(e)}"
        )


@router.post("/batch-job-applications", response_model=Dict[str, Any])
async def process_batch_job_applications(
    request: BatchJobApplicationRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Process multiple job applications concurrently
    
    Ideal for bulk job processing and automated application submission
    """
    try:
        logger.info("Processing batch job applications",
                   user_id=request.user_id,
                   job_count=len(request.jobs))
        
        # Validate batch size
        if len(request.jobs) > 50:  # Reasonable limit
            raise HTTPException(
                status_code=400,
                detail="Batch size too large. Maximum 50 jobs per batch."
            )
        
        # Record API usage
        performance_monitor.record_api_call("batch_job_application")
        
        # Process batch
        results = await langgraph_ai_service.batch_process_jobs(
            user_id=request.user_id,
            jobs=request.jobs,
            user_profile=request.user_profile,
            user_preferences=request.user_preferences,
            user_tier=request.user_tier,
            max_concurrent=request.max_concurrent
        )
        
        # Calculate summary statistics
        successful_count = sum(1 for r in results if r.get("success", False))
        total_applications = sum(1 for r in results if r.get("should_apply", False))
        average_match_score = sum(r.get("match_score", 0) for r in results) / len(results) if results else 0
        
        summary = {
            "total_jobs": len(request.jobs),
            "successful_processing": successful_count,
            "applications_to_submit": total_applications,
            "average_match_score": round(average_match_score, 1),
            "processing_success_rate": round(successful_count / len(request.jobs), 2) if request.jobs else 0,
            "application_rate": round(total_applications / len(request.jobs), 2) if request.jobs else 0
        }
        
        return {
            "status": "success",
            "data": {
                "results": results,
                "summary": summary
            },
            "message": f"Processed {len(request.jobs)} jobs successfully"
        }
        
    except Exception as e:
        logger.error("Batch job processing failed",
                    user_id=request.user_id,
                    error=str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"Batch job processing failed: {str(e)}"
        )


@router.post("/job-match-analysis", response_model=Dict[str, Any])
async def analyze_job_match(request: JobMatchRequest) -> Dict[str, Any]:
    """
    Analyze job compatibility without full application workflow
    
    Useful for quick job filtering and compatibility assessment
    """
    try:
        logger.info("Analyzing job match",
                   job_id=request.job_data.get("external_id"))
        
        # Record API usage
        performance_monitor.record_api_call("job_match_analysis")
        
        # Analyze job match
        result = await langgraph_ai_service.analyze_job_match_only(
            job_data=request.job_data,
            user_profile=request.user_profile,
            user_tier=request.user_tier
        )
        
        return {
            "status": "success" if result["success"] else "failed",
            "data": result,
            "message": "Job match analysis completed"
        }
        
    except Exception as e:
        logger.error("Job match analysis failed",
                    error=str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"Job match analysis failed: {str(e)}"
        )


@router.post("/ai-query", response_model=Dict[str, Any])
async def simple_ai_query(request: SimpleAIRequest) -> Dict[str, Any]:
    """
    Simple AI query endpoint for quick responses
    
    Useful for general AI assistance without workflow orchestration
    """
    try:
        logger.info("Processing simple AI query")
        
        # Record API usage
        performance_monitor.record_api_call("simple_ai_query")
        
        # Get AI response
        result = await langgraph_ai_service.get_simple_ai_response(
            prompt=request.prompt,
            context=request.context,
            temperature=request.temperature,
            model=request.model
        )
        
        return {
            "status": "success" if result["success"] else "failed",
            "data": result,
            "message": "AI query processed successfully"
        }
        
    except Exception as e:
        logger.error("Simple AI query failed",
                    error=str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"AI query failed: {str(e)}"
        )


@router.get("/workflow/{workflow_id}/status", response_model=Dict[str, Any])
async def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """
    Get the status and results of a workflow execution
    """
    try:
        logger.info("Getting workflow status",
                   workflow_id=workflow_id)
        
        status = await langgraph_ai_service.get_workflow_status(workflow_id)
        
        if status:
            return {
                "status": "success",
                "data": status,
                "message": "Workflow status retrieved successfully"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Workflow not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get workflow status",
                    workflow_id=workflow_id,
                    error=str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow status: {str(e)}"
        )


@router.get("/user/{user_id}/workflow-history", response_model=Dict[str, Any])
async def get_user_workflow_history(
    user_id: str,
    limit: int = Query(default=50, le=100, description="Maximum number of records to return")
) -> Dict[str, Any]:
    """
    Get workflow execution history for a user
    """
    try:
        logger.info("Getting user workflow history",
                   user_id=user_id)
        
        history = await langgraph_ai_service.get_user_workflow_history(user_id, limit)
        
        return {
            "status": "success",
            "data": {
                "history": history,
                "total_count": len(history)
            },
            "message": "Workflow history retrieved successfully"
        }
        
    except Exception as e:
        logger.error("Failed to get workflow history",
                    user_id=user_id,
                    error=str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow history: {str(e)}"
        )


@router.get("/user/{user_id}/analytics", response_model=Dict[str, Any])
async def get_user_analytics(
    user_id: str,
    days: int = Query(default=30, le=365, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Get workflow analytics and performance metrics for a user
    """
    try:
        logger.info("Getting user analytics",
                   user_id=user_id,
                   days=days)
        
        analytics = await langgraph_ai_service.get_user_analytics(user_id, days)
        
        return {
            "status": "success",
            "data": analytics,
            "message": "User analytics retrieved successfully",
            "period": f"Last {days} days"
        }
        
    except Exception as e:
        logger.error("Failed to get user analytics",
                    user_id=user_id,
                    error=str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user analytics: {str(e)}"
        )


@router.get("/health", response_model=Dict[str, Any])
async def workflow_health_check() -> Dict[str, Any]:
    """
    Health check for workflow services
    """
    try:
        # Test basic workflow functionality
        test_result = await langgraph_ai_service.get_simple_ai_response(
            prompt="Test prompt for health check",
            model="fast"
        )
        
        return {
            "status": "healthy",
            "workflow_service": "operational",
            "ai_service": "operational" if test_result["success"] else "degraded",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Workflow health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Add router tags for documentation
router.tags = ["Workflows"]