"""
Enterprise structured logging configuration with correlation IDs and security audit trails.
"""

import sys
import json
import logging
from typing import Any, Dict, Optional
from contextvars import ContextVar
from datetime import datetime
import structlog
from structlog.types import EventDict

from jobhire.config.settings import get_settings


# Context variables for request correlation
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


class SecurityAuditLogger:
    """Dedicated logger for security audit trails."""

    def __init__(self):
        self.logger = structlog.get_logger("security_audit")

    def log_authentication_attempt(
        self,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        failure_reason: Optional[str] = None
    ):
        """Log authentication attempts."""
        self.logger.info(
            "authentication_attempt",
            event_type="auth_attempt",
            email=email,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_authorization_failure(
        self,
        user_id: str,
        resource: str,
        action: str,
        ip_address: str
    ):
        """Log authorization failures."""
        self.logger.warning(
            "authorization_failure",
            event_type="auth_failure",
            user_id=user_id,
            resource=resource,
            action=action,
            ip_address=ip_address,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_sensitive_data_access(
        self,
        user_id: str,
        data_type: str,
        record_id: str,
        action: str
    ):
        """Log access to sensitive data."""
        self.logger.info(
            "sensitive_data_access",
            event_type="data_access",
            user_id=user_id,
            data_type=data_type,
            record_id=record_id,
            action=action,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[str],
        details: Dict[str, Any]
    ):
        """Log general security events."""
        self.logger.warning(
            "security_event",
            event_type=event_type,
            user_id=user_id,
            details=details,
            timestamp=datetime.utcnow().isoformat()
        )


def add_correlation_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add correlation IDs to log events."""
    request_id = request_id_var.get()
    user_id = user_id_var.get()
    trace_id = trace_id_var.get()

    if request_id:
        event_dict["request_id"] = request_id
    if user_id:
        event_dict["user_id"] = user_id
    if trace_id:
        event_dict["trace_id"] = trace_id

    return event_dict


def add_timestamp(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add ISO timestamp to log events."""
    event_dict["timestamp"] = datetime.utcnow().isoformat()
    return event_dict


def add_log_level(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add log level to log events."""
    event_dict["level"] = method_name.upper()
    return event_dict


def filter_sensitive_data(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Filter out sensitive data from logs."""
    sensitive_fields = {
        "password", "token", "secret", "key", "authorization",
        "credit_card", "ssn", "api_key", "private_key"
    }

    def _filter_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        filtered = {}
        for key, value in d.items():
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                filtered[key] = "[REDACTED]"
            elif isinstance(value, dict):
                filtered[key] = _filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [
                    _filter_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value
        return filtered

    return _filter_dict(event_dict)


def json_serializer(obj: Any) -> str:
    """Custom JSON serializer for structlog."""
    def default(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)

    return json.dumps(obj, default=default, ensure_ascii=False)


def setup_structured_logging():
    """Configure structured logging for the application."""
    settings = get_settings()

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.monitoring.log_level.upper()),
    )

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)

    # Configure processors based on environment
    processors = [
        add_correlation_id,
        add_timestamp,
        add_log_level,
        filter_sensitive_data,
        # structlog.stdlib.add_logger_name,  # Disabled - incompatible with current setup
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.monitoring.log_format == "json":
        processors.extend([
            structlog.processors.JSONRenderer()
        ])
    else:
        # Console format for development
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True)
        ])

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.monitoring.log_level.upper())
        ),
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Setup file logging if configured
    if settings.monitoring.log_file_path:
        file_handler = logging.FileHandler(settings.monitoring.log_file_path)
        file_handler.setLevel(getattr(logging, settings.monitoring.log_level.upper()))
        file_handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        logging.getLogger().addHandler(file_handler)


class RequestLogger:
    """Request-specific logger with context management."""

    def __init__(self, request_id: str, user_id: Optional[str] = None):
        self.request_id = request_id
        self.user_id = user_id
        self.logger = structlog.get_logger()

    def __enter__(self):
        request_id_var.set(self.request_id)
        if self.user_id:
            user_id_var.set(self.user_id)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        request_id_var.set(None)
        user_id_var.set(None)


class PerformanceLogger:
    """Logger for performance metrics and profiling."""

    def __init__(self):
        self.logger = structlog.get_logger("performance")

    def log_request_duration(
        self,
        method: str,
        path: str,
        duration_ms: float,
        status_code: int,
        user_id: Optional[str] = None
    ):
        """Log HTTP request performance."""
        self.logger.info(
            "request_performance",
            method=method,
            path=path,
            duration_ms=duration_ms,
            status_code=status_code,
            user_id=user_id
        )

    def log_database_query(
        self,
        operation: str,
        collection: str,
        duration_ms: float,
        query_size: Optional[int] = None,
        result_count: Optional[int] = None
    ):
        """Log database query performance."""
        self.logger.info(
            "database_performance",
            operation=operation,
            collection=collection,
            duration_ms=duration_ms,
            query_size=query_size,
            result_count=result_count
        )

    def log_ai_request(
        self,
        model: str,
        operation: str,
        duration_ms: float,
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None
    ):
        """Log AI service performance."""
        self.logger.info(
            "ai_performance",
            model=model,
            operation=operation,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )


class BusinessLogger:
    """Logger for business events and analytics."""

    def __init__(self):
        self.logger = structlog.get_logger("business")

    def log_user_registration(self, user_id: str, email: str, subscription_tier: str):
        """Log new user registration."""
        self.logger.info(
            "user_registered",
            event_type="user_registration",
            user_id=user_id,
            email=email,
            subscription_tier=subscription_tier
        )

    def log_job_application(
        self,
        user_id: str,
        job_id: str,
        application_method: str,
        success: bool
    ):
        """Log job application events."""
        self.logger.info(
            "job_application",
            event_type="job_application",
            user_id=user_id,
            job_id=job_id,
            application_method=application_method,
            success=success
        )

    def log_subscription_change(
        self,
        user_id: str,
        old_tier: str,
        new_tier: str,
        amount_usd: Optional[float] = None
    ):
        """Log subscription changes."""
        self.logger.info(
            "subscription_change",
            event_type="subscription_change",
            user_id=user_id,
            old_tier=old_tier,
            new_tier=new_tier,
            amount_usd=amount_usd
        )

    def log_ai_usage(
        self,
        user_id: str,
        feature: str,
        tokens_used: int,
        cost_usd: float
    ):
        """Log AI feature usage."""
        self.logger.info(
            "ai_usage",
            event_type="ai_usage",
            user_id=user_id,
            feature=feature,
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )