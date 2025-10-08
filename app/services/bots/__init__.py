"""
Bot adapters for external auto-apply services.
"""

from .base_bot_adapter import BaseBotAdapter
from .linkedin_aihawk_adapter import LinkedInAIHawkAdapter
from .bot_manager import BotManager

__all__ = [
    "BaseBotAdapter",
    "LinkedInAIHawkAdapter",
    "BotManager",
]
