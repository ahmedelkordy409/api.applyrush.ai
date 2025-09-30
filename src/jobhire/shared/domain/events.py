"""
Domain events base classes.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from abc import ABC


class DomainEvent(ABC):
    """Base class for all domain events."""

    def __init__(self, event_data: Optional[Dict[str, Any]] = None):
        self.event_id = str(uuid.uuid4())
        self.occurred_at = datetime.utcnow()
        self.event_data = event_data or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.__class__.__name__,
            "occurred_at": self.occurred_at.isoformat(),
            "event_data": self.event_data
        }