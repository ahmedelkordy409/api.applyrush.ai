"""
User Profile application service.
"""

import structlog
from typing import Optional, Dict, Any

from jobhire.shared.domain.types import EntityId
from jobhire.shared.application.exceptions import BusinessRuleException, NotFoundException
from jobhire.shared.infrastructure.events import DomainEventPublisher

from jobhire.domains.user.domain.entities.user import User
from jobhire.domains.user.infrastructure.repositories.user_repository import UserRepository
from jobhire.domains.user.domain.value_objects.preferences import JobSearchPreferences
from jobhire.domains.user.domain.value_objects.application_settings import JobApplicationConfiguration


logger = structlog.get_logger(__name__)


class UserProfileService:
    """Application service for user profile management."""

    def __init__(
        self,
        user_repository: UserRepository,
        event_publisher: DomainEventPublisher
    ):
        self.user_repository = user_repository
        self.event_publisher = event_publisher

    async def get_user_profile(self, user_id: EntityId) -> Optional[User]:
        """Get user profile by ID."""
        return await self.user_repository.find_by_id(user_id)

    async def update_search_preferences(
        self,
        user_id: EntityId,
        preferences_update: Dict[str, Any]
    ) -> None:
        """Update user's job search preferences."""
        logger.info(
            "Updating search preferences",
            user_id=str(user_id),
            updates=list(preferences_update.keys())
        )

        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Update preferences (this would be implemented based on your User entity structure)
        # For now, we'll assume the User entity has methods to update preferences

        # Create new preferences from update
        current_preferences = user.job_search_preferences or JobSearchPreferences()

        # Apply updates to create new preferences object
        updated_data = current_preferences.dict()
        updated_data.update(preferences_update)

        new_preferences = JobSearchPreferences(**updated_data)
        user.update_search_preferences(new_preferences)

        await self.user_repository.update(user)
        await self.event_publisher.publish_events(user.get_domain_events())

        logger.info(
            "Search preferences updated",
            user_id=str(user_id)
        )

    async def get_search_preferences(self, user_id: EntityId) -> Dict[str, Any]:
        """Get user's search preferences."""
        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        preferences = user.job_search_preferences or JobSearchPreferences()
        return preferences.dict()

    async def update_search_configuration(
        self,
        user_id: EntityId,
        config_update: Dict[str, Any]
    ) -> None:
        """Update user's search configuration."""
        logger.info(
            "Updating search configuration",
            user_id=str(user_id),
            updates=list(config_update.keys())
        )

        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Update configuration (implementation depends on User entity structure)
        # This would typically update fields like auto_search_enabled, search_frequency, etc.

        await self.user_repository.update(user)
        await self.event_publisher.publish_events(user.get_domain_events())

        logger.info(
            "Search configuration updated",
            user_id=str(user_id)
        )

    async def get_search_configuration(self, user_id: EntityId) -> Dict[str, Any]:
        """Get user's search configuration."""
        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Return search configuration
        return {
            "auto_search_enabled": getattr(user, 'auto_search_enabled', True),
            "search_frequency_hours": getattr(user, 'search_frequency_hours', 4),
            "minimum_match_score": getattr(user, 'minimum_match_score', 70.0),
            "auto_apply_threshold": getattr(user, 'auto_apply_threshold', 85.0),
            "require_manual_review": getattr(user, 'require_manual_review', True),
            "max_applications_per_day": getattr(user, 'max_applications_per_day', 10),
            "max_applications_per_week": getattr(user, 'max_applications_per_week', 50),
            "max_applications_per_month": getattr(user, 'max_applications_per_month', 200),
            "enabled_platforms": getattr(user, 'enabled_platforms', ["linkedin", "indeed"])
        }

    async def stop_automated_search(self, user_id: EntityId) -> None:
        """Stop automated search for user."""
        logger.info(
            "Stopping automated search",
            user_id=str(user_id)
        )

        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Stop automated search
        user.auto_search_enabled = False

        await self.user_repository.update(user)
        await self.event_publisher.publish_events(user.get_domain_events())

        logger.info(
            "Automated search stopped",
            user_id=str(user_id)
        )

    async def update_application_configuration(
        self,
        user_id: EntityId,
        configuration: Dict[str, Any]
    ) -> None:
        """Update user's application configuration."""
        logger.info(
            "Updating application configuration",
            user_id=str(user_id),
            config_keys=list(configuration.keys())
        )

        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        # Store application configuration
        # This would typically be stored as a JSON field or in a separate table
        user.application_configuration = configuration

        await self.user_repository.update(user)
        await self.event_publisher.publish_events(user.get_domain_events())

        logger.info(
            "Application configuration updated",
            user_id=str(user_id)
        )

    async def get_application_configuration(self, user_id: EntityId) -> Optional[Dict[str, Any]]:
        """Get user's application configuration."""
        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")

        return getattr(user, 'application_configuration', None)