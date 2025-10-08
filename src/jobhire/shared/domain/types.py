"""
Shared domain types and value objects.
"""

import re
from datetime import datetime
from typing import Any, NewType
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, validator
from bson import ObjectId

from .base import ValueObject
from .exceptions import ValidationException


# Type aliases
ID = NewType("ID", str)
Email = NewType("Email", str)
Timestamp = NewType("Timestamp", datetime)


class EntityId(ValueObject):
    """Value object for entity identifiers."""

    value: str = Field(...)

    @validator("value")
    def validate_id(cls, v):
        if not v or not v.strip():
            raise ValidationException("ID cannot be empty")
        return v.strip()

    @classmethod
    def generate(cls) -> "EntityId":
        """Generate a new unique ID."""
        return cls(value=str(uuid4()))

    @classmethod
    def from_string(cls, value: str) -> "EntityId":
        """Create EntityId from string."""
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class EmailAddress(ValueObject):
    """Value object for email addresses."""

    value: str = Field(...)

    @validator("value")
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValidationException("Email cannot be empty")

        email_pattern = re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )
        if not email_pattern.match(v.strip().lower()):
            raise ValidationException("Invalid email format")

        return v.strip().lower()

    def __str__(self) -> str:
        return self.value


class PhoneNumber(ValueObject):
    """Value object for phone numbers."""

    value: str = Field(...)

    @validator("value")
    def validate_phone(cls, v):
        if not v or not v.strip():
            raise ValidationException("Phone number cannot be empty")

        # Remove all non-digit characters
        digits = re.sub(r"\D", "", v)

        # Validate length (10-15 digits)
        if len(digits) < 10 or len(digits) > 15:
            raise ValidationException("Phone number must be 10-15 digits")

        return digits

    def __str__(self) -> str:
        return self.value

    @property
    def formatted(self) -> str:
        """Get formatted phone number."""
        if len(self.value) == 10:
            return f"({self.value[:3]}) {self.value[3:6]}-{self.value[6:]}"
        return self.value


class Money(ValueObject):
    """Value object for monetary amounts."""

    amount: float = Field(...)
    currency: str = Field(default="USD")

    @validator("amount")
    def validate_amount(cls, v):
        if v < 0:
            raise ValidationException("Amount cannot be negative")
        return round(v, 2)

    @validator("currency")
    def validate_currency(cls, v):
        valid_currencies = {"USD", "EUR", "GBP", "CAD", "AUD"}
        if v.upper() not in valid_currencies:
            raise ValidationException(f"Unsupported currency: {v}")
        return v.upper()

    def add(self, other: "Money") -> "Money":
        """Add two money amounts."""
        if self.currency != other.currency:
            raise ValidationException("Cannot add different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def subtract(self, other: "Money") -> "Money":
        """Subtract two money amounts."""
        if self.currency != other.currency:
            raise ValidationException("Cannot subtract different currencies")
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def multiply(self, factor: float) -> "Money":
        """Multiply money by a factor."""
        return Money(amount=self.amount * factor, currency=self.currency)

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:.2f}"


class DateRange(ValueObject):
    """Value object for date ranges."""

    start_date: datetime = Field(...)
    end_date: datetime = Field(...)

    @validator("end_date")
    def validate_date_range(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValidationException("End date must be after start date")
        return v

    def contains(self, date: datetime) -> bool:
        """Check if date is within the range."""
        return self.start_date <= date <= self.end_date

    def overlaps(self, other: "DateRange") -> bool:
        """Check if this range overlaps with another."""
        return (
            self.start_date <= other.end_date and
            self.end_date >= other.start_date
        )

    @property
    def duration_days(self) -> int:
        """Get duration in days."""
        return (self.end_date - self.start_date).days


class Address(ValueObject):
    """Value object for addresses."""

    street: str = Field(...)
    city: str = Field(...)
    state: str = Field(...)
    country: str = Field(...)
    postal_code: str = Field(...)

    @validator("street", "city", "state", "country")
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValidationException("Address field cannot be empty")
        return v.strip()

    @validator("postal_code")
    def validate_postal_code(cls, v):
        if not v or not v.strip():
            raise ValidationException("Postal code cannot be empty")
        # Basic validation - can be enhanced for specific countries
        if len(v.strip()) < 3:
            raise ValidationException("Postal code too short")
        return v.strip()

    def __str__(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.postal_code}, {self.country}"


class Percentage(ValueObject):
    """Value object for percentage values."""

    value: float = Field(...)

    @validator("value")
    def validate_percentage(cls, v):
        if v < 0 or v > 100:
            raise ValidationException("Percentage must be between 0 and 100")
        return round(v, 2)

    def as_decimal(self) -> float:
        """Get percentage as decimal (0.0 - 1.0)."""
        return self.value / 100

    def __str__(self) -> str:
        return f"{self.value}%"


class SkillLevel(ValueObject):
    """Value object for skill proficiency levels."""

    level: str = Field(...)

    @validator("level")
    def validate_level(cls, v):
        valid_levels = {"beginner", "intermediate", "advanced", "expert"}
        if v.lower() not in valid_levels:
            raise ValidationException(f"Invalid skill level: {v}")
        return v.lower()

    @property
    def numeric_value(self) -> int:
        """Get numeric representation of skill level."""
        mapping = {
            "beginner": 1,
            "intermediate": 2,
            "advanced": 3,
            "expert": 4
        }
        return mapping[self.level]

    def __str__(self) -> str:
        return self.level.title()