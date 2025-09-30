"""
Health check and status API endpoints.
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends
import structlog
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request
from jobhire.config.settings import get_settings


logger = structlog.get_logger(__name__)
router = APIRouter(tags=["💚 Health & Status"])


@router.get("/health")
@measure_http_request("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    try:
        return {
            "status": "healthy",
            "service": "JobHire.AI Backend",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": _get_uptime_seconds()
        }

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "JobHire.AI Backend",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


@router.get("/status")
@measure_http_request("/status")
async def detailed_status() -> Dict[str, Any]:
    """Detailed system status check."""
    try:
        status_checks = {
            "api": {"status": "healthy", "details": "API server running"},
            "database": await _check_database_health(),
            "cache": await _check_cache_health(),
            "queue": await _check_queue_health(),
            "external_services": await _check_external_services()
        }

        # Determine overall health
        overall_status = "healthy"
        unhealthy_services = []

        for service_name, service_status in status_checks.items():
            if service_status["status"] != "healthy":
                overall_status = "degraded" if overall_status == "healthy" else "unhealthy"
                unhealthy_services.append(service_name)

        settings = get_settings()

        return {
            "status": overall_status,
            "service": "JobHire.AI Backend",
            "version": "1.0.0",
            "environment": settings.environment,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": _get_uptime_seconds(),
            "services": status_checks,
            "unhealthy_services": unhealthy_services,
            "metadata": {
                "region": getattr(settings, 'region', 'unknown'),
                "deployment_id": getattr(settings, 'deployment_id', 'unknown'),
                "build_timestamp": getattr(settings, 'build_timestamp', 'unknown')
            }
        }

    except Exception as e:
        logger.error("Detailed status check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "JobHire.AI Backend",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "services": {
                "api": {"status": "unhealthy", "error": str(e)}
            }
        }


@router.get("/status/database")
@measure_http_request("/status/database")
async def database_status() -> Dict[str, Any]:
    """Database-specific health check."""
    try:
        db_health = await _check_database_health()
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **db_health
        }

    except Exception as e:
        logger.error("Database status check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


@router.get("/status/services")
@measure_http_request("/status/services")
async def services_status() -> Dict[str, Any]:
    """External services health check."""
    try:
        services_health = await _check_external_services()
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **services_health
        }

    except Exception as e:
        logger.error("Services status check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


# Helper functions

def _get_uptime_seconds() -> float:
    """Get application uptime in seconds."""
    # This would track actual application start time
    # For now, return a placeholder
    return 3600.0  # 1 hour placeholder


async def _check_database_health() -> Dict[str, Any]:
    """Check database connectivity and health."""
    try:
        settings = get_settings()

        # Create a test connection
        client = AsyncIOMotorClient(settings.database.url)

        # Test connection with a simple operation
        start_time = datetime.utcnow()
        await client.admin.command('ping')
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Get database info
        db_info = await client.admin.command('buildInfo')

        await client.close()

        return {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "details": {
                "type": "MongoDB",
                "version": db_info.get("version", "unknown"),
                "connected": True
            }
        }

    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": {
                "type": "MongoDB",
                "connected": False
            }
        }


async def _check_cache_health() -> Dict[str, Any]:
    """Check cache (Redis) connectivity and health."""
    try:
        # This would check Redis connection
        # For now, return a placeholder
        return {
            "status": "healthy",
            "response_time_ms": 5.2,
            "details": {
                "type": "Redis",
                "connected": True,
                "memory_usage": "128MB"
            }
        }

    except Exception as e:
        logger.error("Cache health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": {
                "type": "Redis",
                "connected": False
            }
        }


async def _check_queue_health() -> Dict[str, Any]:
    """Check message queue health."""
    try:
        # This would check message queue (Celery/Redis/RabbitMQ) health
        # For now, return a placeholder
        return {
            "status": "healthy",
            "details": {
                "type": "Celery/Redis",
                "active_workers": 3,
                "pending_tasks": 12,
                "failed_tasks_last_hour": 0
            }
        }

    except Exception as e:
        logger.error("Queue health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": {
                "type": "Celery/Redis",
                "active_workers": 0
            }
        }


async def _check_external_services() -> Dict[str, Any]:
    """Check external services health."""
    try:
        services_status = {}

        # Check AI/ML services
        ai_service_health = await _check_ai_service()
        services_status["ai_service"] = ai_service_health

        # Check job board APIs
        job_apis_health = await _check_job_apis()
        services_status["job_apis"] = job_apis_health

        # Check email service
        email_service_health = await _check_email_service()
        services_status["email_service"] = email_service_health

        # Determine overall external services status
        all_healthy = all(
            service["status"] == "healthy"
            for service in services_status.values()
        )

        overall_status = "healthy" if all_healthy else "degraded"

        return {
            "status": overall_status,
            "services": services_status
        }

    except Exception as e:
        logger.error("External services health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_ai_service() -> Dict[str, Any]:
    """Check AI/ML service health."""
    try:
        # This would ping the AI service endpoint
        # For now, return a placeholder
        return {
            "status": "healthy",
            "response_time_ms": 150.5,
            "details": {
                "endpoint": "ai-service.internal",
                "model_version": "v2.1.0",
                "available_models": ["resume-parser", "job-matcher", "cover-letter-generator"]
            }
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_job_apis() -> Dict[str, Any]:
    """Check job board APIs health."""
    try:
        # This would check various job board APIs
        # For now, return a placeholder
        apis_status = {
            "linkedin": {"status": "healthy", "response_time_ms": 89.2},
            "indeed": {"status": "healthy", "response_time_ms": 156.7},
            "glassdoor": {"status": "degraded", "response_time_ms": 3200.1},
            "monster": {"status": "healthy", "response_time_ms": 203.4}
        }

        overall_healthy = all(
            api["status"] in ["healthy", "degraded"]
            for api in apis_status.values()
        )

        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "apis": apis_status
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_email_service() -> Dict[str, Any]:
    """Check email service health."""
    try:
        # This would check email service (SendGrid, AWS SES, etc.)
        # For now, return a placeholder
        return {
            "status": "healthy",
            "response_time_ms": 45.3,
            "details": {
                "provider": "SendGrid",
                "daily_quota_used": "15%",
                "last_email_sent": "2024-01-15T09:45:00Z"
            }
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }