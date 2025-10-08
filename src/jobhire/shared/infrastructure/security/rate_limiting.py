"""
Rate limiting services.
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests: int
    window: int  # seconds
    burst: Optional[int] = None


@dataclass
class RateLimitState:
    """Rate limit state for a client."""
    requests: int
    window_start: float
    last_request: float


class RateLimitService:
    """In-memory rate limiting service."""

    def __init__(self):
        self._states: Dict[str, RateLimitState] = {}
        self._limits: Dict[str, RateLimit] = {}

    def configure_limit(self, key: str, limit: RateLimit) -> None:
        """Configure rate limit for a key pattern."""
        self._limits[key] = limit

    def is_allowed(self, client_id: str, endpoint: str = "default") -> bool:
        """Check if request is allowed."""
        limit_key = self._get_limit_key(endpoint)
        if limit_key not in self._limits:
            return True  # No limit configured

        limit = self._limits[limit_key]
        now = time.time()

        # Get or create state for this client
        state_key = f"{client_id}:{limit_key}"
        if state_key not in self._states:
            self._states[state_key] = RateLimitState(
                requests=0,
                window_start=now,
                last_request=now
            )

        state = self._states[state_key]

        # Check if we need to reset the window
        if now - state.window_start >= limit.window:
            state.requests = 0
            state.window_start = now

        # Check if request is allowed
        if state.requests >= limit.requests:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                endpoint=endpoint,
                requests=state.requests,
                limit=limit.requests
            )
            return False

        # Allow request and update state
        state.requests += 1
        state.last_request = now
        return True

    def get_remaining(self, client_id: str, endpoint: str = "default") -> Optional[int]:
        """Get remaining requests for client."""
        limit_key = self._get_limit_key(endpoint)
        if limit_key not in self._limits:
            return None

        limit = self._limits[limit_key]
        state_key = f"{client_id}:{limit_key}"

        if state_key not in self._states:
            return limit.requests

        state = self._states[state_key]
        now = time.time()

        # Check if window has reset
        if now - state.window_start >= limit.window:
            return limit.requests

        return max(0, limit.requests - state.requests)

    def _get_limit_key(self, endpoint: str) -> str:
        """Get the limit key for an endpoint."""
        # In a real implementation, you might have more sophisticated
        # pattern matching for different endpoints
        if endpoint in self._limits:
            return endpoint
        return "default"

    def cleanup_expired(self) -> None:
        """Clean up expired rate limit states."""
        now = time.time()
        expired_keys = []

        for key, state in self._states.items():
            if now - state.last_request > 3600:  # 1 hour cleanup threshold
                expired_keys.append(key)

        for key in expired_keys:
            del self._states[key]

        if expired_keys:
            logger.debug("Cleaned up expired rate limit states", count=len(expired_keys))