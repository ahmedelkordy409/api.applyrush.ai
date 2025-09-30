"""
Health checking infrastructure.
"""

from typing import Dict, Any, List
from enum import Enum
import asyncio
import structlog

logger = structlog.get_logger(__name__)


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthCheck:
    """Individual health check."""

    def __init__(self, name: str, check_func, timeout: float = 5.0):
        self.name = name
        self.check_func = check_func
        self.timeout = timeout

    async def run(self) -> Dict[str, Any]:
        """Run the health check."""
        try:
            result = await asyncio.wait_for(self.check_func(), timeout=self.timeout)
            return {
                "name": self.name,
                "status": HealthStatus.HEALTHY.value,
                "result": result
            }
        except asyncio.TimeoutError:
            return {
                "name": self.name,
                "status": HealthStatus.UNHEALTHY.value,
                "error": "Health check timed out"
            }
        except Exception as e:
            return {
                "name": self.name,
                "status": HealthStatus.UNHEALTHY.value,
                "error": str(e)
            }


class HealthChecker:
    """Application health checker."""

    def __init__(self):
        self._checks: List[HealthCheck] = []

    def add_check(self, check: HealthCheck) -> None:
        """Add a health check."""
        self._checks.append(check)

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = []

        for check in self._checks:
            result = await check.run()
            results.append(result)

        # Determine overall status
        unhealthy_count = sum(1 for r in results if r["status"] == HealthStatus.UNHEALTHY.value)

        if unhealthy_count == 0:
            overall_status = HealthStatus.HEALTHY.value
        elif unhealthy_count < len(results):
            overall_status = HealthStatus.DEGRADED.value
        else:
            overall_status = HealthStatus.UNHEALTHY.value

        return {
            "status": overall_status,
            "checks": results,
            "timestamp": asyncio.get_event_loop().time()
        }

    async def check_readiness(self) -> bool:
        """Check if application is ready to serve requests."""
        result = await self.check_all()
        return result["status"] in [HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value]

    async def check_liveness(self) -> bool:
        """Check if application is alive."""
        return True  # Basic implementation