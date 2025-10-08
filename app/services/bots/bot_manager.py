"""
Bot Manager - Orchestrates multiple auto-apply bots and selects appropriate one.
"""

from typing import Dict, Any, Optional, List
import logging
from urllib.parse import urlparse

from .linkedin_aihawk_adapter import LinkedInAIHawkAdapter

logger = logging.getLogger(__name__)


class BotManager:
    """Manages multiple auto-apply bots and selects appropriate one"""

    def __init__(self):
        self.bots = {
            "linkedin": LinkedInAIHawkAdapter(),
            "indeed": None,  # No good Indeed bot available
            "greenhouse": None,  # Could add specific ATS bots
            "lever": None,
            "workday": None
        }

    async def detect_platform(self, job_url: str) -> str:
        """
        Detect job platform from URL.

        Args:
            job_url: Job posting URL

        Returns:
            Platform name (linkedin, indeed, greenhouse, etc.)
        """
        domain = urlparse(job_url).netloc.lower()

        if "linkedin.com" in domain:
            return "linkedin"
        elif "indeed.com" in domain:
            return "indeed"
        elif "greenhouse.io" in domain:
            return "greenhouse"
        elif "lever.co" in domain:
            return "lever"
        elif "workday" in domain or "myworkdayjobs.com" in domain:
            return "workday"
        else:
            return "generic"

    async def apply_to_job(
        self,
        job_url: str,
        user_data: Dict[str, Any],
        resume_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route to appropriate bot based on job URL.

        Args:
            job_url: Job posting URL
            user_data: User profile data
            resume_path: Path to resume file

        Returns:
            Result dictionary from bot
        """

        # Detect platform
        platform = await self.detect_platform(job_url)
        logger.info(f"🔍 Detected platform: {platform} for {job_url}")

        # Get bot for platform
        bot = self.bots.get(platform)

        if not bot:
            logger.warning(f"⚠️ No bot available for {platform}, falling back to browser automation")
            # Fallback to our custom browser automation
            from app.services.browser_auto_apply_service import BrowserAutoApplyService
            browser_service = BrowserAutoApplyService()
            return await browser_service.apply_to_job(
                job_url=job_url,
                user_data=user_data,
                job_data={},
                resume_path=resume_path
            )

        # Use bot
        try:
            # Setup bot if not already setup
            if not hasattr(bot, '_setup_done') or not bot._setup_done:
                await bot.setup(user_data)

            # Apply
            result = await bot.apply_to_job(job_url, user_data, resume_path)
            return result

        except Exception as e:
            logger.error(f"❌ Bot application failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": platform
            }

    async def apply_batch(
        self,
        jobs: List[Dict[str, Any]],
        user_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Apply to multiple jobs efficiently.

        Groups jobs by platform and uses platform-specific batch methods.

        Args:
            jobs: List of job dictionaries with "url" key
            user_data: User profile data

        Returns:
            List of result dictionaries
        """

        # Group jobs by platform
        grouped = {}
        for job in jobs:
            platform = await self.detect_platform(job["url"])
            if platform not in grouped:
                grouped[platform] = []
            grouped[platform].append(job)

        # Apply per platform
        results = []
        for platform, platform_jobs in grouped.items():
            bot = self.bots.get(platform)

            if bot:
                # Use bot's batch apply (more efficient)
                job_urls = [j["url"] for j in platform_jobs]
                platform_results = await bot.apply_batch(job_urls, user_data)
                results.extend(platform_results)
            else:
                # Fallback to one-by-one
                for job in platform_jobs:
                    result = await self.apply_to_job(job["url"], user_data)
                    results.append(result)

        return results

    async def cleanup_all(self):
        """Cleanup all bot resources"""
        for platform, bot in self.bots.items():
            if bot:
                try:
                    await bot.cleanup()
                except Exception as e:
                    logger.warning(f"⚠️ Cleanup warning for {platform}: {e}")
