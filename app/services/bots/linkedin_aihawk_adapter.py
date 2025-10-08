"""
Adapter for LinkedIn_AIHawk bot.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
import logging

# Add bot to Python path
bot_path = Path(__file__).parent.parent.parent.parent / "external_bots" / "LinkedIn_AIHawk"
sys.path.insert(0, str(bot_path))

from .base_bot_adapter import BaseBotAdapter

logger = logging.getLogger(__name__)


class LinkedInAIHawkAdapter(BaseBotAdapter):
    """Adapter for LinkedIn_AIHawk bot"""

    def __init__(self):
        self.config = None
        self.bot = None
        self._setup_done = False

    async def setup(self, config: Dict[str, Any]) -> bool:
        """
        Setup LinkedIn_AIHawk with configuration.

        Args:
            config: Configuration dictionary with:
                - linkedin_email: str
                - linkedin_password: str
                - desired_positions: List[str]
                - preferred_locations: List[str]
                - openai_api_key: str (optional)
                - anthropic_api_key: str (optional)
        """
        try:
            # Convert our format to AIHawk YAML format
            aihawk_config = self._convert_to_aihawk_config(config)

            # Write to YAML file (AIHawk expects YAML)
            config_path = "/tmp/aihawk_config.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(aihawk_config, f)

            # Set environment variables for bot
            if "linkedin_email" in config:
                os.environ["LINKEDIN_EMAIL"] = config["linkedin_email"]
            if "linkedin_password" in config:
                os.environ["LINKEDIN_PASSWORD"] = config["linkedin_password"]
            if "openai_api_key" in config:
                os.environ["OPENAI_API_KEY"] = config["openai_api_key"]
            if "anthropic_api_key" in config:
                os.environ["ANTHROPIC_API_KEY"] = config["anthropic_api_key"]

            # Initialize AIHawk bot
            try:
                from main import LinkedInBotFacade
                self.bot = LinkedInBotFacade(config_path)
                self._setup_done = True
                logger.info("✅ LinkedIn AIHawk bot initialized")
                return True
            except ImportError as e:
                logger.error(f"❌ Failed to import AIHawk bot: {e}")
                logger.info("ℹ️ AIHawk bot may need additional dependencies")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to setup AIHawk: {e}")
            return False

    async def apply_to_job(
        self,
        job_url: str,
        user_data: Dict[str, Any],
        resume_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply to single LinkedIn Easy Apply job.

        Args:
            job_url: LinkedIn job URL
            user_data: User profile data
            resume_path: Path to resume file
        """
        try:
            if not self._setup_done:
                setup_success = await self.setup(user_data)
                if not setup_success:
                    return {
                        "success": False,
                        "error": "Bot setup failed",
                        "provider": "linkedin"
                    }

            # AIHawk expects job search criteria, not direct URLs
            # We'll use their search functionality
            result = await self.bot.apply_to_jobs({
                "positions": user_data.get("desired_position", ["software engineer"]),
                "locations": user_data.get("location", ["USA"]),
                "job_url": job_url  # Custom parameter we add
            })

            return {
                "success": True,
                "provider": "linkedin",
                "bot_used": "aihawk",
                "result": result
            }

        except Exception as e:
            logger.error(f"❌ AIHawk application failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "linkedin"
            }

    async def apply_batch(
        self,
        job_urls: List[str],
        user_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Apply to multiple LinkedIn jobs.

        Args:
            job_urls: List of LinkedIn job URLs
            user_data: User profile data
        """
        results = []
        for url in job_urls:
            result = await self.apply_to_job(url, user_data)
            results.append(result)
        return results

    def get_supported_platforms(self) -> List[str]:
        """Return supported platforms"""
        return ["linkedin"]

    async def cleanup(self):
        """Cleanup browser resources"""
        if self.bot:
            try:
                await self.bot.cleanup()
            except Exception as e:
                logger.warning(f"⚠️ Cleanup warning: {e}")

    def _convert_to_aihawk_config(self, config: Dict) -> Dict:
        """
        Convert our config format to AIHawk YAML format.

        Args:
            config: Our configuration dictionary

        Returns:
            AIHawk-compatible configuration dictionary
        """
        return {
            "remote": True,
            "experienceLevel": {
                "internship": False,
                "entry": True,
                "associate": True,
                "mid-senior level": True,
                "director": False,
                "executive": False
            },
            "jobTypes": {
                "full-time": True,
                "contract": config.get("allow_contract", False),
                "part-time": config.get("allow_part_time", False),
                "temporary": False,
                "internship": False,
                "other": False,
                "volunteer": False
            },
            "date": {
                "all time": False,
                "month": False,
                "week": True,
                "24 hours": False
            },
            "positions": config.get("desired_positions", ["software engineer"]),
            "locations": config.get("preferred_locations", ["United States"]),
            "distance": 25,
            "companyBlacklist": config.get("excluded_companies", []),
            "titleBlacklist": config.get("excluded_titles", []),
            "llm_model_type": config.get("llm_type", "openai"),
            "llm_model": config.get("llm_model", "gpt-4")
        }
