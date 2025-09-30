"""
Domain event infrastructure.
"""

import asyncio
from typing import List, Dict, Any
from abc import ABC, abstractmethod
import structlog

from jobhire.shared.domain.events import DomainEvent

logger = structlog.get_logger(__name__)


class EventHandler(ABC):
    """Abstract event handler."""

    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Handle the event."""
        pass


class DomainEventPublisher:
    """Domain event publisher."""

    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish_events(self, events: List[DomainEvent]) -> None:
        """Publish a list of domain events."""
        for event in events:
            await self.publish_event(event)

    async def publish_event(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        event_type = type(event).__name__

        if event_type in self._handlers:
            handlers = self._handlers[event_type]

            # Execute all handlers concurrently
            tasks = [handler.handle(event) for handler in handlers]
            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    logger.info("Domain event published", event_type=event_type)
                except Exception as e:
                    logger.error("Error publishing event", event_type=event_type, error=str(e))
        else:
            logger.debug("No handlers for event", event_type=event_type)


class EventBus:
    """Simple event bus for application events."""

    def __init__(self):
        self._running = False

    async def start(self) -> None:
        """Start the event bus."""
        self._running = True
        logger.info("Event bus started")

    async def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
        logger.info("Event bus stopped")

    async def health_check(self) -> bool:
        """Check if event bus is healthy."""
        return self._running