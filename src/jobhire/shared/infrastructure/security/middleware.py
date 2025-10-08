"""
Security middleware components.
"""

from typing import Callable, Optional
from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)


class SecurityMiddleware:
    """Security middleware for request processing."""

    def __init__(
        self,
        jwt_manager=None,
        rate_limit_service=None,
        encryption_service=None
    ):
        self.jwt_manager = jwt_manager
        self.rate_limit_service = rate_limit_service
        self.encryption_service = encryption_service
        self.bearer = HTTPBearer(auto_error=False)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process security middleware."""
        try:
            # Rate limiting
            if self.rate_limit_service:
                client_id = self._get_client_id(request)
                endpoint = str(request.url.path)

                if not self.rate_limit_service.is_allowed(client_id, endpoint):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded"}
                    )

            # Security headers
            response = await call_next(request)
            self._add_security_headers(response)

            return response

        except Exception as e:
            logger.error("Security middleware error", error=str(e))
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal security error"}
            )

    def _get_client_id(self, request: Request) -> str:
        """Extract client ID for rate limiting."""
        # Try to get user ID from JWT token
        if self.jwt_manager:
            try:
                token = self._extract_token(request)
                if token:
                    payload = self.jwt_manager.decode_token(token)
                    if payload and "user_id" in payload:
                        return f"user:{payload['user_id']}"
            except Exception:
                pass

        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from request."""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.split(" ")[1]
        return None

    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response."""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'"
        }

        for header, value in security_headers.items():
            response.headers[header] = value


class CORSMiddleware:
    """CORS middleware for cross-origin requests."""

    def __init__(
        self,
        allow_origins: list = None,
        allow_methods: list = None,
        allow_headers: list = None,
        allow_credentials: bool = True
    ):
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        self.allow_headers = allow_headers or ["*"]
        self.allow_credentials = allow_credentials

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process CORS middleware."""
        origin = request.headers.get("origin")

        if request.method == "OPTIONS":
            response = Response()
        else:
            response = await call_next(request)

        # Add CORS headers
        if origin and (self.allow_origins == ["*"] or origin in self.allow_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
        elif self.allow_origins == ["*"]:
            response.headers["Access-Control-Allow-Origin"] = "*"

        response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
        response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)

        if self.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response