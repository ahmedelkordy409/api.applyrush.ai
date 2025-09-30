"""
API v1 router configuration.
"""

from fastapi import APIRouter

from .auth_endpoints import router as auth_router
from .user_endpoints import router as user_router
from .job_search_endpoints import router as job_search_router
from .job_queue_endpoints import router as job_queue_router
from .application_settings_endpoints import router as application_settings_router
from .user_settings_endpoints import router as user_settings_router
from .service_operation_endpoints import router as service_operation_router
from .specific_config_endpoints import router as specific_config_router
from .bulk_operations_endpoints import router as bulk_operations_router
from .user_profile_endpoints import router as user_profile_router
from .webhook_endpoints import router as webhook_router
from .health_endpoints import router as health_router
from jobhire.domains.interview.interfaces.api.interview_endpoints import router as interview_router
from jobhire.domains.cover_letter.interfaces.api.cover_letter_endpoints import router as cover_letter_router


def create_v1_router() -> APIRouter:
    """Create the v1 API router with all endpoints."""
    router = APIRouter()

    # Include all endpoint routers
    router.include_router(auth_router, prefix="/auth")
    router.include_router(user_router, prefix="/users")
    router.include_router(job_search_router)  # Already has /jobs prefix
    router.include_router(job_queue_router)  # Already has /queue prefix
    router.include_router(application_settings_router)  # Already has /application-settings prefix

    # AI Mock Interview endpoints
    router.include_router(interview_router)  # Already has /interviews prefix

    # AI Cover Letter Generator endpoints
    router.include_router(cover_letter_router)  # Already has /cover-letter prefix

    # User settings and configuration endpoints
    router.include_router(user_settings_router)  # Already has /users prefix
    router.include_router(service_operation_router)  # Already has /users prefix
    router.include_router(specific_config_router)  # Already has /users prefix
    router.include_router(bulk_operations_router)  # Already has /users prefix
    router.include_router(user_profile_router)  # Already has /users prefix

    # System endpoints
    router.include_router(webhook_router)  # Already has /webhooks prefix
    router.include_router(health_router)  # Health endpoints at root level

    return router