"""
JobHire.AI Enterprise Backend - Main Application
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Any
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import PlainTextResponse

from .config.settings import get_settings
from .shared.infrastructure.database import DatabaseManager
from .shared.infrastructure.monitoring import (
    setup_structured_logging,
    setup_metrics,
    setup_tracing,
    setup_error_tracking
)
# from .shared.infrastructure.security import SecurityMiddleware  # Not used yet
from .interfaces.api import create_api_router
from .interfaces.api.swagger_config import (
    get_openapi_config,
    get_swagger_ui_parameters,
    get_redoc_parameters
)
from .shared.infrastructure.events import EventBus
from .shared.infrastructure.container import get_container, cleanup_container

# Import legacy subscriptions and onboarding routers
sys.path.insert(0, str((Path(__file__).parent.parent.parent / "app").resolve()))
from app.api.endpoints.subscriptions import router as subscriptions_router
from app.api.endpoints.onboarding import router as onboarding_router


# Configure structured logging
setup_structured_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    settings = get_settings()
    logger.info("Starting JobHire.AI Enterprise Backend", version=settings.app_version)

    # Initialize core services
    try:
        # Initialize dependency injection container
        container = await get_container()
        logger.info("Dependency injection container initialized")

        # Database connections (optional for development)
        database_manager = DatabaseManager(
            connection_string=settings.database.mongodb_url,
            database_name=settings.database.mongodb_database
        )
        try:
            await database_manager.connect()
            logger.info("Database connections established")
        except Exception as e:
            logger.warning("Database connection failed - running without database", error=str(e))
            database_manager = None

        # Event bus
        event_bus = EventBus()
        await event_bus.start()
        logger.info("Event bus started")

        # Metrics and monitoring
        if settings.monitoring.enable_metrics:
            setup_metrics()
            logger.info("Metrics collection enabled")

        # Distributed tracing
        if settings.monitoring.enable_tracing:
            setup_tracing()
            logger.info("Distributed tracing enabled")

        # Error tracking
        if settings.monitoring.sentry_dsn:
            setup_error_tracking()
            logger.info("Error tracking enabled")

        # Store services in app state
        app.state.container = container
        app.state.database_manager = database_manager
        app.state.event_bus = event_bus

        logger.info("Application startup completed successfully")

    except Exception as e:
        logger.error("Application startup failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down application")
    try:
        if hasattr(app.state, "event_bus"):
            await app.state.event_bus.stop()
            logger.info("Event bus stopped")

        if hasattr(app.state, "database_manager"):
            await app.state.database_manager.disconnect()
            logger.info("Database connections closed")

        # Cleanup dependency injection container
        await cleanup_container()
        logger.info("Dependency injection container cleaned up")

        logger.info("Application shutdown completed")

    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Get comprehensive documentation configuration
    openapi_config = get_openapi_config()
    swagger_params = get_swagger_ui_parameters()
    redoc_params = get_redoc_parameters()

    # Create FastAPI instance with comprehensive documentation
    app = FastAPI(
        title=openapi_config["title"],
        description=openapi_config["description"],
        version=openapi_config["version"],
        contact=openapi_config["contact"],
        license_info=openapi_config["license"],
        servers=openapi_config["servers"],
        openapi_tags=openapi_config["tags"],
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        # lifespan=lifespan,  # Disabled - subscriptions API doesn't need database
        **swagger_params,
        **redoc_params
    )

    # Security middleware (must be first) - TODO: Fix SecurityMiddleware ASGI interface
    # app.add_middleware(SecurityMiddleware)

    # Trusted host middleware (for production)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.jobhire.ai", "jobhire.ai"]
        )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.allowed_origins,
        allow_credentials=True,
        allow_methods=settings.security.allowed_methods,
        allow_headers=settings.security.allowed_headers,
    )

    # Compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Include API routes
    api_router = create_api_router()
    app.include_router(api_router, prefix="/api")

    # Include legacy routers
    app.include_router(subscriptions_router, prefix="/api/subscriptions", tags=["Subscriptions"])
    app.include_router(onboarding_router, prefix="/api/onboarding", tags=["Onboarding"])

    # Health check endpoints
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Application health check."""
        try:
            # Check database connectivity
            database_healthy = True
            if hasattr(app.state, "database_manager"):
                database_healthy = await app.state.database_manager.health_check()

            # Check event bus
            event_bus_healthy = True
            if hasattr(app.state, "event_bus"):
                event_bus_healthy = await app.state.event_bus.health_check()

            status = "healthy" if (database_healthy and event_bus_healthy) else "unhealthy"

            return {
                "status": status,
                "version": settings.app_version,
                "environment": settings.app_environment,
                "services": {
                    "database": "healthy" if database_healthy else "unhealthy",
                    "event_bus": "healthy" if event_bus_healthy else "unhealthy",
                }
            }

        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {"status": "unhealthy", "error": str(e)}

    @app.get("/health/ready", tags=["Health"])
    async def readiness_check():
        """Readiness probe for Kubernetes."""
        return {"status": "ready"}

    @app.get("/health/live", tags=["Health"])
    async def liveness_check():
        """Liveness probe for Kubernetes."""
        return {"status": "alive"}

    # Metrics endpoint
    if settings.monitoring.enable_metrics:
        @app.get("/metrics", tags=["Monitoring"])
        async def metrics():
            """Prometheus metrics endpoint."""
            return PlainTextResponse(
                generate_latest(),
                media_type=CONTENT_TYPE_LATEST
            )

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "JobHire.AI Enterprise Backend",
            "version": settings.app_version,
            "environment": settings.app_environment,
            "docs": "/docs" if settings.is_development else None,
            "health": "/health"
        }

    return app


# Create the application instance
app = create_application()


if __name__ == "__main__":
    settings = get_settings()

    # Configure uvicorn for production
    uvicorn_config = {
        "host": settings.app_host,
        "port": settings.app_port,
        "log_level": settings.monitoring.log_level.lower(),
        "access_log": settings.is_development,
        "loop": "uvloop" if sys.platform != "win32" else "asyncio",
        "http": "httptools" if sys.platform != "win32" else "h11",
    }

    if settings.is_development:
        uvicorn_config.update({
            "reload": True,
            "reload_dirs": ["src"],
        })
    else:
        uvicorn_config.update({
            "workers": 1,  # Use with gunicorn for multi-worker
        })

    logger.info(
        "Starting server",
        host=settings.app_host,
        port=settings.app_port,
        environment=settings.app_environment
    )

    uvicorn.run("src.jobhire.main:app", **uvicorn_config)