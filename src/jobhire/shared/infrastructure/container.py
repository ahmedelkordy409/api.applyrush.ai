"""
Dependency injection container for the application.
"""

from typing import Dict, Any, TypeVar, Type, Optional
from functools import lru_cache
import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from jobhire.config.settings import get_settings
from jobhire.shared.infrastructure.events import DomainEventPublisher
from jobhire.shared.infrastructure.database import DatabaseManager

# Domain services and repositories
from jobhire.domains.user.infrastructure.repositories.user_repository import UserRepository
from jobhire.domains.user.application.services.user_profile_service import UserProfileService

from jobhire.domains.job.infrastructure.repositories.job_search_repository import JobSearchRepository
from jobhire.domains.job.infrastructure.repositories.job_queue_repository import JobQueueRepository
from jobhire.domains.job.application.services.job_search_service import JobSearchService
from jobhire.domains.job.application.services.job_queue_service import JobQueueService


logger = structlog.get_logger(__name__)
T = TypeVar('T')


class Container:
    """Dependency injection container."""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._settings = get_settings()
        self._database: Optional[AsyncIOMotorDatabase] = None

    async def initialize(self):
        """Initialize the container and all services."""
        logger.info("Initializing dependency container")

        try:
            # Initialize database connection
            await self._initialize_database()

            # Initialize core infrastructure services
            await self._initialize_infrastructure()

            # Initialize domain services
            await self._initialize_domain_services()

            logger.info("Dependency container initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize dependency container", error=str(e))
            raise

    async def cleanup(self):
        """Cleanup all services and connections."""
        logger.info("Cleaning up dependency container")

        try:
            # Close database connections
            if self._database:
                self._database.client.close()

            # Clear service caches
            self._services.clear()
            self._singletons.clear()

            logger.info("Dependency container cleaned up successfully")

        except Exception as e:
            logger.error("Error during container cleanup", error=str(e))

    async def _initialize_database(self):
        """Initialize database connections."""
        logger.info("Initializing database connections")

        # MongoDB connection
        mongodb_client = AsyncIOMotorClient(
            self._settings.database.mongodb_url,
            minPoolSize=self._settings.database.mongodb_min_pool_size,
            maxPoolSize=self._settings.database.mongodb_max_pool_size
        )

        self._database = mongodb_client[self._settings.database.mongodb_database]

        # Test connection
        await self._database.command('ping')
        logger.info("Database connection established")

    async def _initialize_infrastructure(self):
        """Initialize infrastructure services."""
        logger.info("Initializing infrastructure services")

        # Event publisher
        event_publisher = DomainEventPublisher()
        self._singletons['event_publisher'] = event_publisher

    async def _initialize_domain_services(self):
        """Initialize domain services and repositories."""
        logger.info("Initializing domain services")

        # Get shared dependencies
        event_publisher = self._singletons['event_publisher']

        # User domain
        user_repository = UserRepository(self._database)
        user_profile_service = UserProfileService(user_repository, event_publisher)

        self._singletons['user_repository'] = user_repository
        self._singletons['user_profile_service'] = user_profile_service

        # Job domain
        job_search_repository = JobSearchRepository(self._database)
        job_queue_repository = JobQueueRepository(self._database)

        job_search_service = JobSearchService(
            job_search_repository=job_search_repository,
            user_repository=user_repository,
            event_publisher=event_publisher
        )

        job_queue_service = JobQueueService(
            job_queue_repository=job_queue_repository,
            user_repository=user_repository,
            event_publisher=event_publisher
        )

        self._singletons['job_search_repository'] = job_search_repository
        self._singletons['job_queue_repository'] = job_queue_repository
        self._singletons['job_search_service'] = job_search_service
        self._singletons['job_queue_service'] = job_queue_service

    def get(self, service_name: str) -> Any:
        """Get a service by name."""
        if service_name in self._singletons:
            return self._singletons[service_name]

        if service_name in self._services:
            return self._services[service_name]

        raise ValueError(f"Service '{service_name}' not found in container")

    def get_database(self) -> AsyncIOMotorDatabase:
        """Get the database instance."""
        if not self._database:
            raise RuntimeError("Database not initialized")
        return self._database

    def register_singleton(self, name: str, service: Any):
        """Register a singleton service."""
        self._singletons[name] = service

    def register_service(self, name: str, service: Any):
        """Register a transient service."""
        self._services[name] = service


# Global container instance
_container: Optional[Container] = None


async def get_container() -> Container:
    """Get the global container instance."""
    global _container
    if _container is None:
        _container = Container()
        await _container.initialize()
    return _container


async def cleanup_container():
    """Cleanup the global container."""
    global _container
    if _container:
        await _container.cleanup()
        _container = None


# Dependency functions for FastAPI
async def get_user_profile_service() -> UserProfileService:
    """Get UserProfileService dependency."""
    container = await get_container()
    return container.get('user_profile_service')


async def get_job_search_service() -> JobSearchService:
    """Get JobSearchService dependency."""
    container = await get_container()
    return container.get('job_search_service')


async def get_job_queue_service() -> JobQueueService:
    """Get JobQueueService dependency."""
    container = await get_container()
    return container.get('job_queue_service')


async def get_database() -> AsyncIOMotorDatabase:
    """Get database dependency."""
    container = await get_container()
    return container.get_database()


async def get_event_publisher() -> DomainEventPublisher:
    """Get event publisher dependency."""
    container = await get_container()
    return container.get('event_publisher')