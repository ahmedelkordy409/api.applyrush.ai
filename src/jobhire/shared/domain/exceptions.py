"""
Domain-specific exceptions for the JobHire.AI platform.
"""


class DomainException(Exception):
    """Base exception for domain-related errors."""

    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__


class BusinessRuleException(DomainException):
    """Exception raised when a business rule is violated."""
    pass


class EntityNotFoundException(DomainException):
    """Exception raised when an entity is not found."""
    pass


class DuplicateEntityException(DomainException):
    """Exception raised when trying to create a duplicate entity."""
    pass


class InvalidStateException(DomainException):
    """Exception raised when an entity is in an invalid state."""
    pass


class SecurityException(DomainException):
    """Exception raised for security violations."""
    pass


class ValidationException(DomainException):
    """Exception raised for validation errors."""
    pass


class ConcurrencyException(DomainException):
    """Exception raised for concurrency conflicts."""
    pass


class ExternalServiceException(DomainException):
    """Exception raised when external service calls fail."""
    pass


class ResourceLimitExceededException(DomainException):
    """Exception raised when resource limits are exceeded."""
    pass