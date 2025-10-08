"""
Webhook API endpoints - MongoDB Only
Handles Stripe webhooks and saves to MongoDB
"""

from fastapi import APIRouter, HTTPException, Request, Header, status
from typing import Dict, Any
from datetime import datetime
import hashlib
import hmac
import json
import logging

from app.core.config import settings
from app.services.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)

router = APIRouter()


async def verify_stripe_signature(
    body: bytes,
    signature: str,
    webhook_secret: str
) -> bool:
    """Verify Stripe webhook signature"""
    try:
        elements = signature.split(',')
        timestamp = None
        signature_hash = None

        for element in elements:
            key, value = element.split('=')
            if key == 't':
                timestamp = value
            elif key == 'v1':
                signature_hash = value

        if not timestamp or not signature_hash:
            return False

        payload = timestamp.encode() + b'.' + body
        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature_hash, expected_signature)

    except Exception as e:
        logger.error(f"Stripe signature verification error: {str(e)}")
        return False


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """Handle Stripe webhooks"""
    try:
        body = await request.body()

        # Verify webhook signature
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        if webhook_secret and stripe_signature:
            if not await verify_stripe_signature(body, stripe_signature, webhook_secret):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid signature"
                )

        # Parse webhook event
        try:
            event = json.loads(body.decode())
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON"
            )

        event_type = event.get("type")
        event_id = event.get("id")
        data = event.get("data", {})
        object_data = data.get("object", {})

        logger.info(f"Received Stripe webhook: {event_type}")

        # Log webhook event to MongoDB
        await mongodb_service.log_webhook_event(
            event_id=event_id,
            event_type=event_type,
            event_data=event
        )

        # Handle different event types
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(object_data)

        elif event_type == "payment_intent.succeeded":
            await handle_payment_succeeded(object_data)

        elif event_type == "customer.subscription.created":
            await handle_subscription_created(object_data)

        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(object_data)

        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(object_data)

        else:
            logger.info(f"Unhandled Stripe webhook event: {event_type}")

        return {"received": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


async def handle_checkout_completed(session_data: Dict[str, Any]):
    """Handle successful checkout session"""
    try:
        customer_id = session_data.get("customer")
        customer_email = session_data.get("customer_details", {}).get("email")
        subscription_id = session_data.get("subscription")
        metadata = session_data.get("metadata", {})

        if not customer_email:
            logger.warning("No customer email in checkout session")
            return

        # Update subscription in MongoDB
        await mongodb_service.create_or_update_subscription(
            user_id=metadata.get("user_id", "unknown"),
            user_email=customer_email,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            subscription_status="active",
            subscription_plan=metadata.get("plan_id", "starter"),
            billing_cycle=metadata.get("billing_cycle", "monthly"),
            metadata=metadata
        )

        logger.info(f"Updated subscription for {customer_email}")

    except Exception as e:
        logger.error(f"Error handling checkout completed: {str(e)}")


async def handle_payment_succeeded(payment_intent_data: Dict[str, Any]):
    """Handle successful payment"""
    try:
        customer_id = payment_intent_data.get("customer")
        amount = payment_intent_data.get("amount", 0) / 100  # Convert to dollars
        metadata = payment_intent_data.get("metadata", {})
        
        # Get customer email from Stripe or metadata
        customer_email = metadata.get("customerEmail", "unknown@example.com")

        # Log payment to MongoDB
        await mongodb_service.log_payment(
            user_id=metadata.get("userId", "unknown"),
            user_email=customer_email,
            stripe_customer_id=customer_id,
            amount=amount,
            status="succeeded",
            payment_type=metadata.get("payment_type", "subscription"),
            stripe_payment_intent_id=payment_intent_data.get("id"),
            product_key=metadata.get("productKey"),
            metadata=metadata
        )

        logger.info(f"Payment succeeded: ${amount} for {customer_email}")

    except Exception as e:
        logger.error(f"Error handling payment succeeded: {str(e)}")


async def handle_subscription_created(subscription_data: Dict[str, Any]):
    """Handle subscription creation"""
    try:
        customer_id = subscription_data.get("customer")
        subscription_id = subscription_data.get("id")
        status_val = subscription_data.get("status")
        metadata = subscription_data.get("metadata", {})

        # Update in MongoDB
        await mongodb_service.create_or_update_subscription(
            user_id=metadata.get("user_id", "unknown"),
            user_email=metadata.get("user_email", "unknown@example.com"),
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            subscription_status=status_val,
            subscription_plan=metadata.get("plan_id", "starter"),
            billing_cycle=metadata.get("billing_cycle", "monthly"),
            metadata=metadata
        )

        logger.info(f"Subscription created: {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling subscription created: {str(e)}")


async def handle_subscription_updated(subscription_data: Dict[str, Any]):
    """Handle subscription update"""
    try:
        subscription_id = subscription_data.get("id")
        status_val = subscription_data.get("status")

        # Update subscription status in MongoDB by subscription_id
        # (This would need a new method in mongodb_service)
        logger.info(f"Subscription updated: {subscription_id} - {status_val}")

    except Exception as e:
        logger.error(f"Error handling subscription updated: {str(e)}")


async def handle_subscription_deleted(subscription_data: Dict[str, Any]):
    """Handle subscription deletion"""
    try:
        subscription_id = subscription_data.get("id")

        # Mark subscription as canceled in MongoDB
        logger.info(f"Subscription deleted: {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling subscription deleted: {str(e)}")
