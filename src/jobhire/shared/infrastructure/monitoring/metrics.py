"""
Enterprise metrics collection with Prometheus integration.
"""

import time
from typing import Dict, Any, Optional, List
from functools import wraps
from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
import structlog

from jobhire.config.settings import get_settings


logger = structlog.get_logger(__name__)


class MetricsCollector:
    """Central metrics collector for the application."""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self._setup_metrics()

    def _setup_metrics(self):
        """Setup all application metrics."""

        # HTTP Metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry
        )

        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            registry=self.registry
        )

        self.http_requests_in_progress = Gauge(
            "http_requests_in_progress",
            "HTTP requests currently being processed",
            registry=self.registry
        )

        # Database Metrics
        self.database_operations_total = Counter(
            "database_operations_total",
            "Total database operations",
            ["operation", "collection", "status"],
            registry=self.registry
        )

        self.database_operation_duration = Histogram(
            "database_operation_duration_seconds",
            "Database operation duration in seconds",
            ["operation", "collection"],
            registry=self.registry
        )

        self.database_connections_active = Gauge(
            "database_connections_active",
            "Active database connections",
            registry=self.registry
        )

        # AI Service Metrics
        self.ai_requests_total = Counter(
            "ai_requests_total",
            "Total AI service requests",
            ["provider", "model", "operation", "status"],
            registry=self.registry
        )

        self.ai_request_duration = Histogram(
            "ai_request_duration_seconds",
            "AI request duration in seconds",
            ["provider", "model"],
            registry=self.registry
        )

        self.ai_tokens_used_total = Counter(
            "ai_tokens_used_total",
            "Total AI tokens consumed",
            ["provider", "model"],
            registry=self.registry
        )

        self.ai_cost_usd_total = Counter(
            "ai_cost_usd_total",
            "Total AI costs in USD",
            ["provider", "model"],
            registry=self.registry
        )

        # Business Metrics
        self.user_registrations_total = Counter(
            "user_registrations_total",
            "Total user registrations",
            ["subscription_tier"],
            registry=self.registry
        )

        self.job_applications_total = Counter(
            "job_applications_total",
            "Total job applications",
            ["method", "status"],
            registry=self.registry
        )

        self.subscription_changes_total = Counter(
            "subscription_changes_total",
            "Total subscription changes",
            ["from_tier", "to_tier"],
            registry=self.registry
        )

        self.active_users = Gauge(
            "active_users",
            "Currently active users",
            registry=self.registry
        )

        # System Metrics
        self.memory_usage_bytes = Gauge(
            "memory_usage_bytes",
            "Current memory usage in bytes",
            registry=self.registry
        )

        self.cpu_usage_percent = Gauge(
            "cpu_usage_percent",
            "Current CPU usage percentage",
            registry=self.registry
        )

        # Queue Metrics
        self.queue_size = Gauge(
            "queue_size",
            "Current queue size",
            ["queue_name"],
            registry=self.registry
        )

        self.queue_processing_duration = Histogram(
            "queue_processing_duration_seconds",
            "Queue task processing duration",
            ["queue_name", "task_type"],
            registry=self.registry
        )

        # Error Metrics
        self.errors_total = Counter(
            "errors_total",
            "Total errors",
            ["error_type", "component"],
            registry=self.registry
        )

        # Application Info
        self.app_info = Info(
            "app_info",
            "Application information",
            registry=self.registry
        )

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float
    ):
        """Record HTTP request metrics."""
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()

        self.http_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

    def record_database_operation(
        self,
        operation: str,
        collection: str,
        duration: float,
        success: bool
    ):
        """Record database operation metrics."""
        status = "success" if success else "error"

        self.database_operations_total.labels(
            operation=operation,
            collection=collection,
            status=status
        ).inc()

        self.database_operation_duration.labels(
            operation=operation,
            collection=collection
        ).observe(duration)

    def record_ai_request(
        self,
        provider: str,
        model: str,
        operation: str,
        duration: float,
        tokens_used: int,
        cost_usd: float,
        success: bool
    ):
        """Record AI service request metrics."""
        status = "success" if success else "error"

        self.ai_requests_total.labels(
            provider=provider,
            model=model,
            operation=operation,
            status=status
        ).inc()

        self.ai_request_duration.labels(
            provider=provider,
            model=model
        ).observe(duration)

        if success:
            self.ai_tokens_used_total.labels(
                provider=provider,
                model=model
            ).inc(tokens_used)

            self.ai_cost_usd_total.labels(
                provider=provider,
                model=model
            ).inc(cost_usd)

    def record_user_registration(self, subscription_tier: str):
        """Record user registration."""
        self.user_registrations_total.labels(
            subscription_tier=subscription_tier
        ).inc()

    def record_job_application(self, method: str, success: bool):
        """Record job application."""
        status = "success" if success else "error"
        self.job_applications_total.labels(
            method=method,
            status=status
        ).inc()

    def record_subscription_change(self, from_tier: str, to_tier: str):
        """Record subscription change."""
        self.subscription_changes_total.labels(
            from_tier=from_tier,
            to_tier=to_tier
        ).inc()

    def update_active_users(self, count: int):
        """Update active users count."""
        self.active_users.set(count)

    def update_queue_size(self, queue_name: str, size: int):
        """Update queue size."""
        self.queue_size.labels(queue_name=queue_name).set(size)

    def record_error(self, error_type: str, component: str):
        """Record an error."""
        self.errors_total.labels(
            error_type=error_type,
            component=component
        ).inc()

    def set_app_info(self, version: str, environment: str):
        """Set application information."""
        self.app_info.info({
            "version": version,
            "environment": environment
        })


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def setup_metrics():
    """Initialize metrics collection."""
    settings = get_settings()
    collector = get_metrics_collector()

    # Set application info
    collector.set_app_info(
        version=settings.app_version,
        environment=settings.app_environment
    )

    logger.info("Metrics collection initialized")


# Decorators for automatic metrics collection

def measure_http_request(endpoint: str):
    """Decorator to measure HTTP request metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()

            # Extract request info (this is simplified)
            method = kwargs.get("method", "GET")
            status_code = 200

            try:
                collector.http_requests_in_progress.inc()
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                collector.record_error(
                    error_type=type(e).__name__,
                    component="api"
                )
                raise
            finally:
                duration = time.time() - start_time
                collector.http_requests_in_progress.dec()
                collector.record_http_request(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    duration=duration
                )
        return wrapper
    return decorator


def measure_database_operation(operation: str, collection: str):
    """Decorator to measure database operation metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()
            success = True

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                collector.record_error(
                    error_type=type(e).__name__,
                    component="database"
                )
                raise
            finally:
                duration = time.time() - start_time
                collector.record_database_operation(
                    operation=operation,
                    collection=collection,
                    duration=duration,
                    success=success
                )
        return wrapper
    return decorator


def measure_ai_request(provider: str, model: str, operation: str):
    """Decorator to measure AI request metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()
            success = True
            tokens_used = 0
            cost_usd = 0.0

            try:
                result = await func(*args, **kwargs)
                # Extract metrics from result if available
                if isinstance(result, dict):
                    tokens_used = result.get("tokens_used", 0)
                    cost_usd = result.get("cost_usd", 0.0)
                return result
            except Exception as e:
                success = False
                collector.record_error(
                    error_type=type(e).__name__,
                    component="ai_service"
                )
                raise
            finally:
                duration = time.time() - start_time
                collector.record_ai_request(
                    provider=provider,
                    model=model,
                    operation=operation,
                    duration=duration,
                    tokens_used=tokens_used,
                    cost_usd=cost_usd,
                    success=success
                )
        return wrapper
    return decorator


class MetricsMiddleware:
    """ASGI middleware for automatic metrics collection."""

    def __init__(self, app):
        self.app = app
        self.collector = get_metrics_collector()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.time()
            method = scope["method"]
            path = scope["path"]
            status_code = 200

            self.collector.http_requests_in_progress.inc()

            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as e:
                status_code = 500
                self.collector.record_error(
                    error_type=type(e).__name__,
                    component="http"
                )
                raise
            finally:
                duration = time.time() - start_time
                self.collector.http_requests_in_progress.dec()
                self.collector.record_http_request(
                    method=method,
                    endpoint=path,
                    status_code=status_code,
                    duration=duration
                )
        else:
            await self.app(scope, receive, send)