"""
Base domain classes for DDD implementation.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Generic
from uuid import uuid4
from pydantic import BaseModel, Field
from bson import ObjectId


EntityId = TypeVar("EntityId")


class DomainEvent(BaseModel):
    """Base class for domain events."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str = Field(...)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    entity_id: str = Field(...)
    version: int = Field(default=1)
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        frozen = True


class Entity(ABC, Generic[EntityId]):
    """Base entity class with identity."""

    def __init__(self, entity_id: EntityId):
        self._id = entity_id
        self._events: List[DomainEvent] = []

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def events(self) -> List[DomainEvent]:
        return self._events.copy()

    def clear_events(self) -> None:
        """Clear all domain events."""
        self._events.clear()

    def add_event(self, event: DomainEvent) -> None:
        """Add a domain event."""
        self._events.append(event)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class ValueObject(BaseModel, ABC):
    """Base value object class."""

    class Config:
        frozen = True
        allow_mutation = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.dict() == other.dict()

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.dict().items())))


class AggregateRoot(Entity[EntityId], ABC):
    """Base aggregate root class."""

    def __init__(self, entity_id: EntityId):
        super().__init__(entity_id)
        self._version = 0

    @property
    def version(self) -> int:
        return self._version

    def increment_version(self) -> None:
        """Increment the aggregate version."""
        self._version += 1

    @abstractmethod
    def apply_event(self, event: DomainEvent) -> None:
        """Apply a domain event to the aggregate."""
        pass


class Repository(ABC, Generic[EntityId]):
    """Base repository interface."""

    @abstractmethod
    async def find_by_id(self, entity_id: EntityId) -> Optional[AggregateRoot]:
        """Find an aggregate by ID."""
        pass

    @abstractmethod
    async def save(self, aggregate: AggregateRoot) -> None:
        """Save an aggregate."""
        pass

    @abstractmethod
    async def delete(self, entity_id: EntityId) -> None:
        """Delete an aggregate."""
        pass


class DomainService(ABC):
    """Base domain service class."""
    pass


class Specification(ABC):
    """Base specification pattern implementation."""

    @abstractmethod
    def is_satisfied_by(self, candidate: Any) -> bool:
        """Check if the candidate satisfies the specification."""
        pass

    def and_(self, other: "Specification") -> "AndSpecification":
        return AndSpecification(self, other)

    def or_(self, other: "Specification") -> "OrSpecification":
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification":
        return NotSpecification(self)


class AndSpecification(Specification):
    """AND specification."""

    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)


class OrSpecification(Specification):
    """OR specification."""

    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)


class NotSpecification(Specification):
    """NOT specification."""

    def __init__(self, specification: Specification):
        self.specification = specification

    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self.specification.is_satisfied_by(candidate)