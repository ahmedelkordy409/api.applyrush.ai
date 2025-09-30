"""
Main API router configuration.
"""

from fastapi import APIRouter

from .v1 import create_v1_router


def create_api_router() -> APIRouter:
    """Create the main API router with versioning."""
    router = APIRouter()

    # Include versioned API routes
    v1_router = create_v1_router()
    router.include_router(v1_router, prefix="/v1")

    return router