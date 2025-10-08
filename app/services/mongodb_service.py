"""
MongoDB service for handling database operations
"""
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
import logging

logger = logging.getLogger(__name__)


class MongoDBService:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    async def connect(self):
        """Connect to MongoDB"""
        try:
            mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
            mongodb_database = os.getenv("MONGODB_DATABASE", "jobhire_ai")

            self.client = AsyncIOMotorClient(mongodb_url)
            self.db = self.client[mongodb_database]

            # Test connection
            await self.client.server_info()
            logger.info(f"Connected to MongoDB database: {mongodb_database}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            # Don't raise - allow app to continue without MongoDB
            self.db = None

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    # Subscription operations
    async def create_or_update_subscription(
        self,
        user_id: str,
        user_email: str,
        stripe_customer_id: str,
        stripe_subscription_id: Optional[str] = None,
        subscription_status: str = "active",
        subscription_plan: str = "starter",
        billing_cycle: str = "monthly",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create or update subscription in MongoDB"""
        if not self.db:
            logger.warning("MongoDB not connected")
            return {}

        try:
            subscriptions = self.db.subscriptions

            # Check if subscription exists
            existing = await subscriptions.find_one({"user_email": user_email})

            subscription_data = {
                "user_id": user_id,
                "user_email": user_email,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": stripe_subscription_id,
                "subscription_status": subscription_status,
                "subscription_plan": subscription_plan,
                "billing_cycle": billing_cycle,
                "updated_at": datetime.utcnow(),
                "metadata": metadata or {}
            }

            if existing:
                # Update existing subscription
                await subscriptions.update_one(
                    {"user_email": user_email},
                    {"$set": subscription_data}
                )
                logger.info(f"Updated subscription for user {user_email}")
            else:
                # Create new subscription
                subscription_data["created_at"] = datetime.utcnow()
                subscription_data["subscription_start_date"] = datetime.utcnow()
                subscription_data["addons"] = []

                await subscriptions.insert_one(subscription_data)
                logger.info(f"Created subscription for user {user_email}")

            return subscription_data
        except Exception as e:
            logger.error(f"Error creating/updating subscription: {str(e)}")
            return {}

    async def add_addon_to_subscription(
        self,
        user_email: str,
        addon_key: str
    ) -> bool:
        """Add an add-on to user's subscription"""
        if not self.db:
            return False

        try:
            subscriptions = self.db.subscriptions

            result = await subscriptions.update_one(
                {"user_email": user_email},
                {
                    "$addToSet": {"addons": addon_key},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            logger.info(f"Added addon {addon_key} to subscription for {user_email}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error adding addon: {str(e)}")
            return False

    async def get_subscription(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Get subscription by user email"""
        if not self.db:
            return None

        try:
            subscriptions = self.db.subscriptions
            subscription = await subscriptions.find_one({"user_email": user_email})
            return subscription
        except Exception as e:
            logger.error(f"Error getting subscription: {str(e)}")
            return None

    # Payment operations
    async def log_payment(
        self,
        user_id: str,
        user_email: str,
        stripe_customer_id: str,
        amount: float,
        status: str,
        payment_type: str = "subscription",
        stripe_payment_intent_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        product_key: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Log a payment transaction"""
        if not self.db:
            return {}

        try:
            payments = self.db.payments

            payment_data = {
                "user_id": user_id,
                "user_email": user_email,
                "stripe_customer_id": stripe_customer_id,
                "stripe_payment_intent_id": stripe_payment_intent_id,
                "stripe_subscription_id": stripe_subscription_id,
                "amount": amount,
                "currency": "usd",
                "status": status,
                "payment_type": payment_type,
                "product_key": product_key,
                "description": description,
                "created_at": datetime.utcnow(),
                "metadata": metadata or {}
            }

            await payments.insert_one(payment_data)
            logger.info(f"Logged {status} payment of ${amount} for {user_email}")

            return payment_data
        except Exception as e:
            logger.error(f"Error logging payment: {str(e)}")
            return {}

    # Webhook event logging
    async def log_webhook_event(
        self,
        event_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> bool:
        """Log a webhook event"""
        if not self.db:
            return False

        try:
            webhook_events = self.db.webhook_events

            # Check if event already processed (idempotency)
            existing = await webhook_events.find_one({"event_id": event_id})
            if existing:
                logger.info(f"Webhook event {event_id} already processed")
                return False

            event_doc = {
                "event_id": event_id,
                "event_type": event_type,
                "event_data": event_data,
                "processed": True,
                "processed_at": datetime.utcnow(),
                "created_at": datetime.utcnow()
            }

            await webhook_events.insert_one(event_doc)
            logger.info(f"Logged webhook event: {event_type}")

            return True
        except Exception as e:
            logger.error(f"Error logging webhook event: {str(e)}")
            return False


    # User operations
    async def create_or_update_user(
        self,
        email: str,
        full_name: Optional[str] = None,
        user_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        onboarding_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create or update user in MongoDB"""
        if not self.db:
            logger.warning("MongoDB not connected")
            return {}

        try:
            users = self.db.users

            # Check if user exists
            existing = await users.find_one({"email": email})

            user_data = {
                "email": email,
                "full_name": full_name,
                "stripe_customer_id": stripe_customer_id,
                "updated_at": datetime.utcnow(),
                "metadata": metadata or {}
            }

            if user_id:
                user_data["external_id"] = user_id

            if onboarding_data:
                user_data.update(onboarding_data)

            if existing:
                # Update existing user
                await users.update_one(
                    {"email": email},
                    {"$set": user_data}
                )
                logger.info(f"Updated user {email}")
                user_data["_id"] = existing["_id"]
            else:
                # Create new user
                user_data["created_at"] = datetime.utcnow()
                user_data["auto_apply_enabled"] = False
                user_data["skills"] = []
                user_data["preferences"] = {}

                result = await users.insert_one(user_data)
                user_data["_id"] = result.inserted_id
                logger.info(f"Created user {email}")

            return user_data
        except Exception as e:
            logger.error(f"Error creating/updating user: {str(e)}")
            return {}

    async def get_user(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        if not self.db:
            return None

        try:
            users = self.db.users
            user = await users.find_one({"email": email})
            return user
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            return None

    async def update_user_profile(
        self,
        email: str,
        profile_data: Dict[str, Any]
    ) -> bool:
        """Update user profile data"""
        if not self.db:
            return False

        try:
            users = self.db.users

            profile_data["updated_at"] = datetime.utcnow()

            result = await users.update_one(
                {"email": email},
                {"$set": profile_data}
            )

            logger.info(f"Updated profile for {email}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            return False

    async def save_onboarding_progress(
        self,
        email: str,
        step: str,
        data: Dict[str, Any]
    ) -> bool:
        """Save user onboarding progress"""
        if not self.db:
            return False

        try:
            users = self.db.users

            onboarding_update = {
                f"onboarding_data.{step}": data,
                "onboarding_current_step": step,
                "updated_at": datetime.utcnow()
            }

            result = await users.update_one(
                {"email": email},
                {"$set": onboarding_update}
            )

            logger.info(f"Saved onboarding progress for {email} at step {step}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error saving onboarding progress: {str(e)}")
            return False


# Global instance
mongodb_service = MongoDBService()
