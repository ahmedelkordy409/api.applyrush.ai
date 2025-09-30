"""
Webhook API endpoints
Handles external webhooks from various services (Stripe, etc.)
"""

from fastapi import APIRouter, HTTPException, Request, Header, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import hmac
import json
import logging

from app.core.database import database
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def verify_stripe_signature(
    body: bytes,
    signature: str,
    webhook_secret: str
) -> bool:
    """Verify Stripe webhook signature"""
    try:
        # Extract timestamp and signature from header
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

        # Create expected signature
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
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
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
        data = event.get("data", {})
        object_data = data.get("object", {})

        logger.info(f"Received Stripe webhook: {event_type}")

        # Handle different event types
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(object_data)

        elif event_type == "invoice.payment_succeeded":
            await handle_payment_succeeded(object_data)

        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(object_data)

        elif event_type == "customer.subscription.created":
            await handle_subscription_created(object_data)

        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(object_data)

        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(object_data)

        elif event_type == "customer.subscription.trial_will_end":
            await handle_trial_will_end(object_data)

        else:
            logger.info(f"Unhandled Stripe webhook event: {event_type}")

        # Log webhook event
        await log_webhook_event(event)

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
        subscription_id = session_data.get("subscription")
        client_reference_id = session_data.get("client_reference_id")

        if not client_reference_id:
            logger.warning("No client_reference_id in checkout session")
            return

        # Update user subscription
        update_query = """
            UPDATE users
            SET
                stripe_customer_id = :customer_id,
                stripe_subscription_id = :subscription_id,
                subscription_status = 'active',
                subscription_plan = 'premium',
                updated_at = :updated_at
            WHERE id = :user_id
        """

        await database.execute(
            query=update_query,
            values={
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "updated_at": datetime.utcnow(),
                "user_id": client_reference_id
            }
        )

        logger.info(f"Updated subscription for user {client_reference_id}")

    except Exception as e:
        logger.error(f"Error handling checkout completed: {str(e)}")


async def handle_payment_succeeded(invoice_data: Dict[str, Any]):
    """Handle successful payment"""
    try:
        subscription_id = invoice_data.get("subscription")
        customer_id = invoice_data.get("customer")
        amount_paid = invoice_data.get("amount_paid", 0) / 100  # Convert from cents

        if not subscription_id:
            return

        # Update subscription status
        update_query = """
            UPDATE users
            SET
                subscription_status = 'active',
                last_payment_date = :payment_date,
                updated_at = :updated_at
            WHERE stripe_subscription_id = :subscription_id
        """

        await database.execute(
            query=update_query,
            values={
                "payment_date": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "subscription_id": subscription_id
            }
        )

        # Log payment
        await log_payment(customer_id, subscription_id, amount_paid, "succeeded")

        logger.info(f"Payment succeeded for subscription {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling payment succeeded: {str(e)}")


async def handle_payment_failed(invoice_data: Dict[str, Any]):
    """Handle failed payment"""
    try:
        subscription_id = invoice_data.get("subscription")
        customer_id = invoice_data.get("customer")
        amount_due = invoice_data.get("amount_due", 0) / 100  # Convert from cents

        if not subscription_id:
            return

        # Update subscription status
        update_query = """
            UPDATE users
            SET
                subscription_status = 'past_due',
                updated_at = :updated_at
            WHERE stripe_subscription_id = :subscription_id
        """

        await database.execute(
            query=update_query,
            values={
                "updated_at": datetime.utcnow(),
                "subscription_id": subscription_id
            }
        )

        # Log failed payment
        await log_payment(customer_id, subscription_id, amount_due, "failed")

        logger.warning(f"Payment failed for subscription {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling payment failed: {str(e)}")


async def handle_subscription_created(subscription_data: Dict[str, Any]):
    """Handle subscription creation"""
    try:
        subscription_id = subscription_data.get("id")
        customer_id = subscription_data.get("customer")
        status = subscription_data.get("status")

        # Find user by customer ID and update subscription
        update_query = """
            UPDATE users
            SET
                stripe_subscription_id = :subscription_id,
                subscription_status = :status,
                updated_at = :updated_at
            WHERE stripe_customer_id = :customer_id
        """

        await database.execute(
            query=update_query,
            values={
                "subscription_id": subscription_id,
                "status": status,
                "updated_at": datetime.utcnow(),
                "customer_id": customer_id
            }
        )

        logger.info(f"Subscription created: {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling subscription created: {str(e)}")


async def handle_subscription_updated(subscription_data: Dict[str, Any]):
    """Handle subscription updates"""
    try:
        subscription_id = subscription_data.get("id")
        status = subscription_data.get("status")
        cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)

        # Update subscription
        update_query = """
            UPDATE users
            SET
                subscription_status = :status,
                cancel_at_period_end = :cancel_at_period_end,
                updated_at = :updated_at
            WHERE stripe_subscription_id = :subscription_id
        """

        await database.execute(
            query=update_query,
            values={
                "status": status,
                "cancel_at_period_end": cancel_at_period_end,
                "updated_at": datetime.utcnow(),
                "subscription_id": subscription_id
            }
        )

        logger.info(f"Subscription updated: {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling subscription updated: {str(e)}")


async def handle_subscription_deleted(subscription_data: Dict[str, Any]):
    """Handle subscription cancellation"""
    try:
        subscription_id = subscription_data.get("id")

        # Update subscription status to canceled
        update_query = """
            UPDATE users
            SET
                subscription_status = 'canceled',
                subscription_plan = 'free',
                stripe_subscription_id = NULL,
                updated_at = :updated_at
            WHERE stripe_subscription_id = :subscription_id
        """

        await database.execute(
            query=update_query,
            values={
                "updated_at": datetime.utcnow(),
                "subscription_id": subscription_id
            }
        )

        logger.info(f"Subscription canceled: {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling subscription deleted: {str(e)}")


async def handle_trial_will_end(subscription_data: Dict[str, Any]):
    """Handle trial ending soon notification"""
    try:
        subscription_id = subscription_data.get("id")
        trial_end = subscription_data.get("trial_end")

        # Get user email for notification
        user_query = """
            SELECT email FROM users
            WHERE stripe_subscription_id = :subscription_id
        """

        user = await database.fetch_one(
            query=user_query,
            values={"subscription_id": subscription_id}
        )

        if user:
            # Send trial ending notification email
            # This would integrate with your email service
            logger.info(f"Trial ending soon for user: {user['email']}")

    except Exception as e:
        logger.error(f"Error handling trial will end: {str(e)}")


async def log_webhook_event(event: Dict[str, Any]):
    """Log webhook event to database"""
    try:
        insert_query = """
            INSERT INTO webhook_events (
                event_id, event_type, processed_at, data
            ) VALUES (
                :event_id, :event_type, :processed_at, :data
            )
        """

        await database.execute(
            query=insert_query,
            values={
                "event_id": event.get("id"),
                "event_type": event.get("type"),
                "processed_at": datetime.utcnow(),
                "data": json.dumps(event)
            }
        )

    except Exception as e:
        logger.error(f"Error logging webhook event: {str(e)}")


async def log_payment(customer_id: str, subscription_id: str, amount: float, status: str):
    """Log payment attempt"""
    try:
        insert_query = """
            INSERT INTO payment_logs (
                stripe_customer_id, stripe_subscription_id, amount, status, created_at
            ) VALUES (
                :customer_id, :subscription_id, :amount, :status, :created_at
            )
        """

        await database.execute(
            query=insert_query,
            values={
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "amount": amount,
                "status": status,
                "created_at": datetime.utcnow()
            }
        )

    except Exception as e:
        logger.error(f"Error logging payment: {str(e)}")


@router.post("/general")
async def general_webhook(request: Request):
    """Handle general webhooks from other services"""
    try:
        body = await request.body()
        headers = dict(request.headers)

        # Log the webhook
        logger.info(f"Received general webhook: {headers}")

        # Parse JSON if possible
        try:
            data = json.loads(body.decode())
        except:
            data = body.decode()

        # Process based on user-agent or other headers
        user_agent = headers.get("user-agent", "")

        if "github" in user_agent.lower():
            await handle_github_webhook(data, headers)
        elif "mailgun" in user_agent.lower():
            await handle_mailgun_webhook(data, headers)
        else:
            # Generic webhook handling
            logger.info(f"Generic webhook received: {data}")

        return {"received": True}

    except Exception as e:
        logger.error(f"General webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


async def handle_github_webhook(data: Dict[str, Any], headers: Dict[str, str]):
    """Handle GitHub webhooks for CI/CD"""
    try:
        event_type = headers.get("x-github-event")

        if event_type == "push":
            # Handle code push events
            repository = data.get("repository", {})
            commits = data.get("commits", [])

            logger.info(f"GitHub push to {repository.get('name')}: {len(commits)} commits")

        elif event_type == "pull_request":
            # Handle pull request events
            action = data.get("action")
            pr = data.get("pull_request", {})

            logger.info(f"GitHub PR {action}: {pr.get('title')}")

    except Exception as e:
        logger.error(f"Error handling GitHub webhook: {str(e)}")


async def handle_mailgun_webhook(data: Dict[str, Any], headers: Dict[str, str]):
    """Handle Mailgun email webhooks"""
    try:
        event_type = data.get("event")
        recipient = data.get("recipient")

        if event_type in ["delivered", "opened", "clicked"]:
            # Log email events
            logger.info(f"Email {event_type} for {recipient}")

        elif event_type in ["bounced", "dropped", "complained"]:
            # Handle email failures
            logger.warning(f"Email {event_type} for {recipient}")

    except Exception as e:
        logger.error(f"Error handling Mailgun webhook: {str(e)}")


@router.get("/test")
async def webhook_test():
    """Test webhook endpoint"""
    return {
        "status": "ok",
        "message": "Webhook endpoint is working",
        "timestamp": datetime.utcnow()
    }