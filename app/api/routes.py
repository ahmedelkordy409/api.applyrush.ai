"""
Main API router for JobHire.AI
Combines all API endpoints
"""

from fastapi import APIRouter
from app.api.endpoints import (
    auth, profiles, jobs, matching, applications, users,
    analytics, user_management, payments, ai_automation,
    cover_letters, interviews, subscriptions, upselling, admin, webhook, auto_apply,
    resumes, skills, queue_management, database_operations, onboarding
)
# workflows temporarily commented out due to missing dependencies
from app.api import monitoring

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(profiles.router, prefix="/users", tags=["user-profiles"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(matching.router, prefix="/matching", tags=["matching"])
api_router.include_router(applications.router, prefix="/applications", tags=["applications"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(ai_automation.router, prefix="/ai", tags=["ai-automation"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
# api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(user_management.router, prefix="/user-management", tags=["user-management"])
api_router.include_router(cover_letters.router, prefix="/cover-letters", tags=["cover-letters"])
api_router.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(upselling.router, prefix="/upselling", tags=["upselling"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(webhook.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(auto_apply.router, prefix="/auto-apply", tags=["auto-apply"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(queue_management.router, prefix="/applications/queue", tags=["queue-management"])
api_router.include_router(database_operations.router, prefix="/database", tags=["database-operations"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(monitoring.router, tags=["monitoring"])

# Additional routes for specific Next.js API compatibility
api_router.include_router(database_operations.router, prefix="/jobs/database", tags=["database-operations"])
api_router.include_router(database_operations.router, prefix="/setup-database", tags=["database-operations"])