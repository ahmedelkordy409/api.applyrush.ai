"""
Error handling middleware for the FastAPI application
Provides consistent error responses and logging
"""

import logging
import traceback
from typing import Union
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware to handle errors and provide consistent error responses"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)

            # Log request processing time
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except Exception as exc:
            process_time = time.time() - start_time

            # Log the error
            logger.error(
                f"Unhandled error in {request.method} {request.url}: {str(exc)}",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "process_time": process_time,
                    "traceback": traceback.format_exc()
                }
            )

            # Return generic error response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "detail": "An unexpected error occurred. Please try again later.",
                    "timestamp": time.time()
                }
            )


def create_error_handler():
    """Create error handlers for the FastAPI application"""

    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        logger.warning(
            f"HTTP {exc.status_code} error in {request.method} {request.url}: {exc.detail}",
            extra={
                "method": request.method,
                "url": str(request.url),
                "status_code": exc.status_code,
                "detail": exc.detail
            }
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": get_error_message(exc.status_code),
                "detail": exc.detail,
                "timestamp": time.time()
            }
        )

    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle Starlette HTTP exceptions"""
        logger.warning(
            f"Starlette HTTP {exc.status_code} error in {request.method} {request.url}: {exc.detail}",
            extra={
                "method": request.method,
                "url": str(request.url),
                "status_code": exc.status_code,
                "detail": exc.detail
            }
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": get_error_message(exc.status_code),
                "detail": exc.detail,
                "timestamp": time.time()
            }
        )

    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors"""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": " -> ".join(str(x) for x in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        logger.warning(
            f"Validation error in {request.method} {request.url}: {errors}",
            extra={
                "method": request.method,
                "url": str(request.url),
                "validation_errors": errors
            }
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "detail": "Request validation failed",
                "errors": errors,
                "timestamp": time.time()
            }
        )

    return http_exception_handler, starlette_http_exception_handler, validation_exception_handler


def get_error_message(status_code: int) -> str:
    """Get user-friendly error message based on status code"""
    error_messages = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        422: "Validation Error",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout"
    }

    return error_messages.get(status_code, "Unknown Error")


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class BusinessLogicError(Exception):
    """Custom business logic error"""
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class AuthenticationError(Exception):
    """Custom authentication error"""
    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(self.message)


class AuthorizationError(Exception):
    """Custom authorization error"""
    def __init__(self, message: str = "Insufficient permissions"):
        self.message = message
        super().__init__(self.message)


class ExternalServiceError(Exception):
    """Error from external service"""
    def __init__(self, message: str, service: str = None, status_code: int = None):
        self.message = message
        self.service = service
        self.status_code = status_code
        super().__init__(self.message)


def handle_database_error(error: Exception) -> HTTPException:
    """Convert database errors to appropriate HTTP exceptions"""
    error_str = str(error).lower()

    if "unique constraint" in error_str or "duplicate key" in error_str:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource already exists"
        )
    elif "foreign key constraint" in error_str:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reference to related resource"
        )
    elif "not null constraint" in error_str:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Required field is missing"
        )
    elif "check constraint" in error_str:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid field value"
        )
    else:
        logger.error(f"Database error: {str(error)}")
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        )


def handle_external_service_error(error: ExternalServiceError) -> HTTPException:
    """Convert external service errors to appropriate HTTP exceptions"""
    if error.status_code:
        if error.status_code >= 500:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            detail = f"{error.service} service is temporarily unavailable"
        elif error.status_code == 429:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            detail = f"Rate limit exceeded for {error.service} service"
        elif error.status_code >= 400:
            status_code = status.HTTP_502_BAD_GATEWAY
            detail = f"Invalid response from {error.service} service"
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            detail = f"Error communicating with {error.service} service"
    else:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = f"{error.service} service is unavailable"

    return HTTPException(status_code=status_code, detail=detail)


def safe_error_response(error: Exception, default_message: str = "An error occurred") -> dict:
    """Create a safe error response that doesn't leak sensitive information"""
    return {
        "error": default_message,
        "detail": str(error) if isinstance(error, (ValidationError, BusinessLogicError)) else default_message,
        "timestamp": time.time()
    }


def log_error_context(request: Request, error: Exception, user_id: str = None):
    """Log error with additional context"""
    context = {
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "error_type": type(error).__name__,
        "error_message": str(error)
    }

    if user_id:
        context["user_id"] = user_id

    logger.error(f"Error processing request: {str(error)}", extra=context)