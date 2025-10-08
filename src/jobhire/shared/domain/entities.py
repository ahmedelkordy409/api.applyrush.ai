"""
Domain entities base classes.
"""

from abc import ABC
from typing import TypeVar, Generic, List
from datetime import datetime

from .types import EntityId
from .events import DomainEvent

T = TypeVar('T')


class Entity(Generic[T]):
    """Base entity class."""

    def __init__(self, entity_id: T):
        self._id = entity_id
        self.version = 1

    @property
    def id(self) -> T:
        return self._id

    def __eq__(self, other) -> bool:
        if not isinstance(other, Entity):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)


class AggregateRoot(Entity[T]):
    """Base aggregate root class."""

    def __init__(self, entity_id: T):
        super().__init__(entity_id)
        self._domain_events: List[DomainEvent] = []

    def add_domain_event(self, event: DomainEvent) -> None:
        """Add a domain event."""
        self._domain_events.append(event)

    def get_domain_events(self) -> List[DomainEvent]:
        """Get and clear domain events."""
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events

    def clear_domain_events(self) -> None:
        """Clear domain events."""
        self._domain_events.clear()

    def increment_version(self) -> None:
        """Increment the aggregate version."""
        self.version += 1