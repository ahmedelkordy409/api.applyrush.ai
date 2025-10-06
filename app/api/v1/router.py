"""
API V1 Router - Central routing for all endpoints
Connects onboarding → user profile → job matching → auto-apply
"""

from fastapi import APIRouter

# Import working endpoint routers
from app.api.v1.endpoints import (
    auth,
    onboarding,
    resumes,
    matching,
    webhooks,
    subscriptions,
    dashboard
)
from app.api.endpoints import users, inbox, cover_letters, interviews, background_jobs, applications_queue, applications_database

# Create main API router
api_router = APIRouter()

# Include working endpoint routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    onboarding.router,
    prefix="/onboarding",
    tags=["Onboarding"]
)

api_router.include_router(
    resumes.router,
    prefix="/resumes",
    tags=["Resumes"]
)

api_router.include_router(
    matching.router,
    prefix="/matching",
    tags=["Job Matching"]
)

api_router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["Webhooks"]
)

api_router.include_router(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["Subscriptions"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"]
)

api_router.include_router(
    inbox.router,
    prefix="/inbox",
    tags=["Inbox"]
)

api_router.include_router(
    cover_letters.router,
    prefix="/cover-letters",
    tags=["Cover Letters"]
)

api_router.include_router(
    interviews.router,
    prefix="/interviews",
    tags=["Interviews"]
)

api_router.include_router(
    background_jobs.router,
    prefix="/background-jobs",
    tags=["Background Jobs"]
)

api_router.include_router(
    applications_queue.router,
    prefix="/applications",
    tags=["Applications Queue"]
)

api_router.include_router(
    applications_database.router,
    prefix="/applications",
    tags=["Applications"]
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"]
)
