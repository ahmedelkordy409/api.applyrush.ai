"""
MongoDB models for subscriptions and payments
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class SubscriptionModel(BaseModel):
    """User subscription data"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    user_email: str
    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    subscription_status: str = "free"  # free, active, past_due, canceled, trialing
    subscription_plan: str = "free"  # free, starter, pro, pro-plus
    billing_cycle: str = "monthly"  # monthly, yearly

    # Add-ons
    addons: List[str] = []  # List of addon keys: coverLetterAddon, resumeCustomizationAddon, etc.

    # Dates
    subscription_start_date: Optional[datetime] = None
    subscription_end_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    last_payment_date: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class PaymentModel(BaseModel):
    """Payment transaction record"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    user_email: str
    stripe_customer_id: str
    stripe_payment_intent_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

    # Payment details
    amount: float  # in dollars
    currency: str = "usd"
    status: str  # succeeded, failed, pending, canceled
    payment_type: str  # subscription, addon, one_time
    product_key: Optional[str] = None  # For add-ons: coverLetterAddon, etc.

    # Metadata
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class WebhookEventModel(BaseModel):
    """Stripe webhook event log"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    event_id: str  # Stripe event ID
    event_type: str
    event_data: Dict[str, Any]
    processed: bool = False
    processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
