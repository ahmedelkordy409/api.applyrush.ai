"""
Base adapter interface for auto-apply bots.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class BaseBotAdapter(ABC):
    """Abstract base class for auto-apply bot adapters"""

    @abstractmethod
    async def setup(self, config: Dict[str, Any]) -> bool:
        """
        Initialize bot with configuration.

        Args:
            config: Configuration dictionary containing credentials and settings

        Returns:
            True if setup successful, False otherwise
        """
        pass

    @abstractmethod
    async def apply_to_job(
        self,
        job_url: str,
        user_data: Dict[str, Any],
        resume_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply to a single job.

        Args:
            job_url: URL of the job posting
            user_data: User profile data for form filling
            resume_path: Path to resume file

        Returns:
            Dictionary with result:
            {
                "success": bool,
                "provider": str,
                "bot_used": str,
                "error": str (optional),
                "result": Any (optional)
            }
        """
        pass

    @abstractmethod
    async def apply_batch(
        self,
        job_urls: List[str],
        user_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Apply to multiple jobs efficiently.

        Args:
            job_urls: List of job URLs
            user_data: User profile data

        Returns:
            List of result dictionaries
        """
        pass

    @abstractmethod
    def get_supported_platforms(self) -> List[str]:
        """
        Return list of supported platforms.

        Returns:
            List of platform names (e.g., ["linkedin", "indeed"])
        """
        pass

    @abstractmethod
    async def cleanup(self):
        """
        Cleanup resources (close browser, etc.).
        """
        pass
