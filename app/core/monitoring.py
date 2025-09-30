"""
Monitoring and metrics setup
"""

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time
import structlog

# Setup structured logging
logger = structlog.get_logger()

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

AI_PROCESSING_TIME = Histogram(
    'ai_processing_duration_seconds',
    'AI processing duration in seconds',
    ['model', 'operation']
)

JOB_MATCHING_ACCURACY = Histogram(
    'job_matching_accuracy',
    'Job matching accuracy scores',
    ['user_tier']
)

APPLICATION_SUCCESS_RATE = Counter(
    'application_success_total',
    'Successful job applications',
    ['user_tier', 'job_source']
)


def setup_monitoring(app: FastAPI):
    """Setup monitoring middleware and endpoints"""
    
    @app.middleware("http")
    async def monitoring_middleware(request: Request, call_next):
        """Monitor HTTP requests"""
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Record metrics
        process_time = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(process_time)
        
        # Add processing time to response headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    @app.get("/metrics")
    async def get_metrics():
        """Prometheus metrics endpoint"""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class PerformanceMonitor:
    """Performance monitoring utilities"""
    
    @staticmethod
    def record_ai_processing_time(model: str, operation: str, duration: float):
        """Record AI processing time"""
        AI_PROCESSING_TIME.labels(model=model, operation=operation).observe(duration)
    
    @staticmethod
    def record_job_matching_accuracy(user_tier: str, accuracy: float):
        """Record job matching accuracy"""
        JOB_MATCHING_ACCURACY.labels(user_tier=user_tier).observe(accuracy)
    
    @staticmethod
    def record_application_success(user_tier: str, job_source: str):
        """Record successful application"""
        APPLICATION_SUCCESS_RATE.labels(user_tier=user_tier, job_source=job_source).inc()


# Global performance monitor instance
performance_monitor = PerformanceMonitor()