"""
Base repository classes for the infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from jobhire.shared.domain.types import EntityId

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository."""

    @abstractmethod
    async def create(self, entity: T) -> None:
        """Create a new entity."""
        pass

    @abstractmethod
    async def update(self, entity: T) -> None:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def find_by_id(self, entity_id: EntityId) -> Optional[T]:
        """Find entity by ID."""
        pass

    @abstractmethod
    async def delete_by_id(self, entity_id: EntityId) -> bool:
        """Delete entity by ID."""
        pass


class BaseMongoRepository(BaseRepository[T]):
    """Base MongoDB repository implementation."""

    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str, entity_class: type):
        self.database = database
        self.collection: AsyncIOMotorCollection = database[collection_name]
        self.entity_class = entity_class

    async def delete_by_id(self, entity_id: EntityId) -> bool:
        """Delete entity by ID."""
        result = await self.collection.delete_one({"_id": str(entity_id)})
        return result.deleted_count > 0

    def _document_to_entity(self, document: Dict[str, Any]) -> T:
        """Convert MongoDB document to entity. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _document_to_entity")