"""
Application layer exceptions.
"""

from typing import Any, Dict, Optional


class ApplicationException(Exception):
    """Base application exception."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class BusinessRuleException(ApplicationException):
    """Exception raised when a business rule is violated."""

    def __init__(self, rule: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.rule = rule


class NotFoundException(ApplicationException):
    """Exception raised when a resource is not found."""

    def __init__(self, resource_type: str, identifier: str, details: Optional[Dict[str, Any]] = None):
        message = f"{resource_type} with identifier '{identifier}' not found"
        super().__init__(message, details)
        self.resource_type = resource_type
        self.identifier = identifier


class ConflictException(ApplicationException):
    """Exception raised when there's a conflict (e.g., duplicate resource)."""

    def __init__(self, resource_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.resource_type = resource_type


class ValidationException(ApplicationException):
    """Exception raised when validation fails."""

    def __init__(self, field: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.field = field


class UnauthorizedException(ApplicationException):
    """Exception raised when user is not authorized."""

    def __init__(self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class ForbiddenException(ApplicationException):
    """Exception raised when access is forbidden."""

    def __init__(self, message: str = "Forbidden", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class RateLimitException(ApplicationException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class ExternalServiceException(ApplicationException):
    """Exception raised when external service fails."""

    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.service = service


class DomainException(ApplicationException):
    """Exception raised for domain-specific errors."""
    pass