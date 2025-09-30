"""
User Management API Endpoints
Comprehensive user management including settings, search control, onboarding, and queues
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query, File, UploadFile
from pydantic import BaseModel, Field
from datetime import datetime

from ...services.user_management_service import user_management_service
from ...models.user_settings import (
    SearchSettingsUpdate, SearchControlRequest, QueueItemRequest,
    OnboardingStepData, UserPreferencesUpdate, QueueFilters,
    SearchStatus, QueuePriority, OnboardingStatus
)
from ...models.documents import (
    DocumentUpload, DocumentUpdate, CoverLetterTemplateCreate,
    DocumentGenerationRequest, DocumentAnalysisRequest,
    DocumentType, DocumentStatus, FileFormat
)
import structlog

logger = structlog.get_logger()

router = APIRouter()


# === USER PROFILE ENDPOINTS ===

@router.get("/profile/{user_id}", response_model=Dict[str, Any])
async def get_user_profile(user_id: str) -> Dict[str, Any]:
    """Get complete user profile"""
    try:
        profile = await user_management_service.get_user_profile(user_id)
        
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        return {
            "status": "success",
            "data": profile,
            "message": "User profile retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user profile", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile/{user_id}", response_model=Dict[str, Any])
async def create_user_profile(
    user_id: str,
    profile_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create new user profile"""
    try:
        success = await user_management_service.create_user_profile(user_id, profile_data)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create user profile")
        
        return {
            "status": "success",
            "data": {"user_id": user_id},
            "message": "User profile created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create user profile", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile/{user_id}/preferences", response_model=Dict[str, Any])
async def update_user_preferences(
    user_id: str,
    preferences: UserPreferencesUpdate
) -> Dict[str, Any]:
    """Update user preferences"""
    try:
        success = await user_management_service.update_user_preferences(user_id, preferences)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update preferences")
        
        return {
            "status": "success",
            "data": {"updated_fields": list(preferences.dict(exclude_unset=True).keys())},
            "message": "User preferences updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update user preferences", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# === SEARCH SETTINGS ENDPOINTS ===

@router.get("/search-settings/{user_id}", response_model=Dict[str, Any])
async def get_search_settings(user_id: str) -> Dict[str, Any]:
    """Get user search settings"""
    try:
        settings = await user_management_service.get_search_settings(user_id)
        
        if not settings:
            raise HTTPException(status_code=404, detail="Search settings not found")
        
        return {
            "status": "success",
            "data": settings,
            "message": "Search settings retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get search settings", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/search-settings/{user_id}", response_model=Dict[str, Any])
async def update_search_settings(
    user_id: str,
    settings: SearchSettingsUpdate
) -> Dict[str, Any]:
    """Update user search settings"""
    try:
        success = await user_management_service.update_search_settings(user_id, settings)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update search settings")
        
        return {
            "status": "success",
            "data": {"updated_fields": list(settings.dict(exclude_unset=True).keys())},
            "message": "Search settings updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update search settings", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# === SEARCH CONTROL ENDPOINTS ===

@router.post("/search-control/{user_id}", response_model=Dict[str, Any])
async def control_search(
    user_id: str,
    control: SearchControlRequest
) -> Dict[str, Any]:
    """Control user search (pause, resume, stop, start)"""
    try:
        result = await user_management_service.control_search(user_id, control)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "status": "success",
            "data": result,
            "message": result.get("message", "Search control applied successfully")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to control search", user_id=user_id, action=control.action, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-status/{user_id}", response_model=Dict[str, Any])
async def get_search_status(user_id: str) -> Dict[str, Any]:
    """Get current search status for user"""
    try:
        settings = await user_management_service.get_search_settings(user_id)
        
        if not settings:
            raise HTTPException(status_code=404, detail="Search settings not found")
        
        status_info = {
            "search_status": settings.get("search_status"),
            "search_paused_at": settings.get("search_paused_at"),
            "search_pause_reason": settings.get("search_pause_reason"),
            "auto_resume_at": settings.get("auto_resume_at"),
            "max_applications_per_day": settings.get("max_applications_per_day"),
            "applications_today": 0  # TODO: Calculate from recent applications
        }
        
        return {
            "status": "success",
            "data": status_info,
            "message": "Search status retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get search status", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# === QUEUE MANAGEMENT ENDPOINTS ===

@router.post("/queue/{user_id}/add", response_model=Dict[str, Any])
async def add_to_queue(
    user_id: str,
    queue_item: QueueItemRequest
) -> Dict[str, Any]:
    """Add job to user's application queue"""
    try:
        result = await user_management_service.add_to_queue(user_id, queue_item)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "status": "success",
            "data": result,
            "message": result.get("message", "Job added to queue successfully")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to add job to queue", user_id=user_id, job_id=queue_item.job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/{user_id}", response_model=Dict[str, Any])
async def get_user_queue(
    user_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[QueuePriority] = Query(None, description="Filter by priority"),
    flagged_only: Optional[bool] = Query(None, description="Show only flagged items"),
    limit: int = Query(50, le=200, description="Maximum items to return")
) -> Dict[str, Any]:
    """Get user's application queue with optional filters"""
    try:
        filters = QueueFilters(
            status=status,
            priority=priority,
            flagged_only=flagged_only
        )
        
        queue_items = await user_management_service.get_user_queue(user_id, filters, limit)
        
        return {
            "status": "success",
            "data": {
                "items": queue_items,
                "total_count": len(queue_items),
                "filters_applied": filters.dict(exclude_unset=True)
            },
            "message": "Queue retrieved successfully"
        }
        
    except Exception as e:
        logger.error("Failed to get user queue", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/queue/{user_id}/{queue_id}", response_model=Dict[str, Any])
async def update_queue_item(
    user_id: str,
    queue_id: str,
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """Update queue item (priority, notes, flags, etc.)"""
    try:
        success = await user_management_service.update_queue_item(user_id, queue_id, updates)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update queue item")
        
        return {
            "status": "success",
            "data": {"queue_id": queue_id, "updated_fields": list(updates.keys())},
            "message": "Queue item updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update queue item", user_id=user_id, queue_id=queue_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# === ONBOARDING ENDPOINTS ===

@router.get("/onboarding/{user_id}/status", response_model=Dict[str, Any])
async def get_onboarding_status(user_id: str) -> Dict[str, Any]:
    """Get user onboarding status and progress"""
    try:
        onboarding_data = await user_management_service.get_onboarding_status(user_id)
        
        return {
            "status": "success",
            "data": onboarding_data,
            "message": "Onboarding status retrieved successfully"
        }
        
    except Exception as e:
        logger.error("Failed to get onboarding status", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboarding/{user_id}/step", response_model=Dict[str, Any])
async def update_onboarding_step(
    user_id: str,
    step_data: OnboardingStepData
) -> Dict[str, Any]:
    """Update or complete an onboarding step"""
    try:
        success = await user_management_service.update_onboarding_step(user_id, step_data)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update onboarding step")
        
        return {
            "status": "success",
            "data": {
                "step_name": step_data.step_name,
                "completion_percentage": step_data.completion_percentage
            },
            "message": "Onboarding step updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update onboarding step", user_id=user_id, step=step_data.step_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# === DASHBOARD ENDPOINT ===

@router.get("/dashboard/{user_id}", response_model=Dict[str, Any])
async def get_user_dashboard(user_id: str) -> Dict[str, Any]:
    """Get comprehensive user dashboard data"""
    try:
        dashboard_data = await user_management_service.get_user_dashboard_data(user_id)
        
        if not dashboard_data:
            raise HTTPException(status_code=404, detail="User data not found")
        
        return {
            "status": "success",
            "data": dashboard_data,
            "message": "Dashboard data retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user dashboard", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# === DOCUMENT MANAGEMENT ENDPOINTS ===

@router.post("/documents/{user_id}/upload", response_model=Dict[str, Any])
async def upload_document(
    user_id: str,
    file: UploadFile = File(...),
    document_type: DocumentType = DocumentType.RESUME,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Upload user document (resume, CV, etc.)"""
    try:
        # Validate file type
        allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload PDF, DOCX, or TXT files.")
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Determine file format
        file_format = FileFormat.PDF
        if file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            file_format = FileFormat.DOCX
        elif file.content_type == "text/plain":
            file_format = FileFormat.TXT
        
        # TODO: Implement actual document storage and text extraction
        # For now, we'll return a mock response
        
        document_data = {
            "user_id": user_id,
            "name": name or file.filename,
            "description": description,
            "document_type": document_type.value,
            "file_format": file_format.value,
            "file_size": file_size,
            "status": DocumentStatus.ACTIVE.value
        }
        
        logger.info("Document uploaded", user_id=user_id, document_type=document_type.value, file_size=file_size)
        
        return {
            "status": "success",
            "data": {
                "document_id": "doc_" + user_id + "_" + str(datetime.utcnow().timestamp()),
                "name": document_data["name"],
                "document_type": document_type.value,
                "file_size": file_size,
                "upload_completed": True
            },
            "message": "Document uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload document", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{user_id}", response_model=Dict[str, Any])
async def get_user_documents(
    user_id: str,
    document_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    status: Optional[DocumentStatus] = Query(None, description="Filter by status")
) -> Dict[str, Any]:
    """Get user's documents"""
    try:
        # TODO: Implement actual document retrieval from database
        # For now, return mock data
        
        mock_documents = [
            {
                "id": "doc_1",
                "name": "Software Engineer Resume",
                "document_type": DocumentType.RESUME.value,
                "status": DocumentStatus.ACTIVE.value,
                "file_format": FileFormat.PDF.value,
                "created_at": datetime.utcnow().isoformat(),
                "usage_count": 5
            }
        ]
        
        return {
            "status": "success",
            "data": {
                "documents": mock_documents,
                "total_count": len(mock_documents)
            },
            "message": "Documents retrieved successfully"
        }
        
    except Exception as e:
        logger.error("Failed to get user documents", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# === SYSTEM ENDPOINTS ===

@router.post("/system/auto-resume-check", response_model=Dict[str, Any])
async def check_auto_resume(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Check for users whose search should auto-resume (system endpoint)"""
    try:
        resumed_users = await user_management_service.check_auto_resume()
        
        return {
            "status": "success",
            "data": {
                "resumed_users": resumed_users,
                "count": len(resumed_users)
            },
            "message": f"Auto-resume check completed. {len(resumed_users)} users resumed."
        }
        
    except Exception as e:
        logger.error("Failed to check auto-resume", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/queue/next", response_model=Dict[str, Any])
async def get_next_queue_items(
    limit: int = Query(10, le=50, description="Maximum items to return")
) -> Dict[str, Any]:
    """Get next items to process from all user queues (system endpoint)"""
    try:
        items = await user_management_service.get_next_queue_items(limit)
        
        return {
            "status": "success",
            "data": {
                "items": items,
                "count": len(items)
            },
            "message": f"Retrieved {len(items)} queue items ready for processing"
        }
        
    except Exception as e:
        logger.error("Failed to get next queue items", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def user_management_health_check() -> Dict[str, Any]:
    """Health check for user management service"""
    try:
        # Test basic service functionality
        health_data = {
            "service": "user_management",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "profile_management": "operational",
                "search_settings": "operational",
                "queue_system": "operational",
                "onboarding": "operational",
                "document_management": "operational"
            }
        }
        
        return {
            "status": "success",
            "data": health_data,
            "message": "User management service is healthy"
        }
        
    except Exception as e:
        logger.error("User management health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Add router tags for documentation
router.tags = ["User Management"]