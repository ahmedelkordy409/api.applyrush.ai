"""
Webhooks - Email receiving, Stripe events
Handles incoming emails and payment webhooks
"""

import hashlib
import hmac
import json
import logging
from typing import Dict
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from bson import ObjectId
from datetime import datetime

from app.core.database_new import get_db
from app.core.config import settings
from app.services.email_forwarding_service import EmailForwardingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/email/ses")
async def ses_email_webhook(request: Request, db = Depends(get_db)):
    """
    AWS SES Email Receiving Webhook
    Triggered when email is sent to @apply.applyrush.ai
    """
    try:
        body = await request.json()

        # AWS SNS message type handling
        message_type = request.headers.get("x-amz-sns-message-type")

        if message_type == "SubscriptionConfirmation":
            # Auto-confirm SNS subscription
            subscribe_url = body.get("SubscribeURL")
            logger.info(f"SNS Subscription confirmation: {subscribe_url}")
            # In production, you'd make a request to this URL
            return {"message": "Subscription confirmation received"}

        if message_type == "Notification":
            # Parse SES notification
            message = json.loads(body.get("Message", "{}"))

            if message.get("notificationType") == "Received":
                # Extract email data
                mail = message.get("mail", {})
                content = message.get("content", "")

                email_data = {
                    "to": mail.get("destination", [])[0] if mail.get("destination") else "",
                    "from": mail.get("source", ""),
                    "subject": mail.get("commonHeaders", {}).get("subject", ""),
                    "body": content,  # Raw email content
                    "html": "",  # Parse from content
                    "received_at": mail.get("timestamp"),
                    "message_id": mail.get("messageId")
                }

                # Save email using service
                email_service = EmailForwardingService(db)
                saved_email = email_service.save_received_email(email_data)

                logger.info(f"Saved email {saved_email['_id']} from SES webhook")

                return {"message": "Email received and processed", "email_id": str(saved_email["_id"])}

        return {"message": "Webhook received"}

    except Exception as e:
        logger.error(f"Error processing SES webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/sendgrid")
async def sendgrid_email_webhook(request: Request, db = Depends(get_db)):
    """
    SendGrid Inbound Parse Webhook
    Alternative to AWS SES
    """
    try:
        # SendGrid sends multipart/form-data
        form_data = await request.form()

        email_data = {
            "to": form_data.get("to", ""),
            "from": form_data.get("from", ""),
            "subject": form_data.get("subject", ""),
            "body": form_data.get("text", ""),
            "html": form_data.get("html", ""),
            "attachments": []
        }

        # Parse attachments
        attachment_info = form_data.get("attachment-info")
        if attachment_info:
            attachments_data = json.loads(attachment_info)
            for att in attachments_data.values():
                email_data["attachments"].append({
                    "filename": att.get("filename"),
                    "type": att.get("type"),
                    "size": att.get("content-length")
                })

        # Save email
        email_service = EmailForwardingService(db)
        saved_email = email_service.save_received_email(email_data)

        logger.info(f"Saved email {saved_email['_id']} from SendGrid webhook")

        return {"message": "Email received"}

    except Exception as e:
        logger.error(f"Error processing SendGrid webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/postfix")
async def postfix_email_webhook(request: Request, db = Depends(get_db)):
    """
    Postfix/Custom SMTP Webhook
    For self-hosted email receiving
    """
    try:
        email_data = await request.json()

        # Validate required fields
        required_fields = ["to", "from", "subject", "body"]
        for field in required_fields:
            if field not in email_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        # Save email
        email_service = EmailForwardingService(db)
        saved_email = email_service.save_received_email(email_data)

        logger.info(f"Saved email {saved_email['_id']} from Postfix webhook")

        return {"message": "Email received", "email_id": str(saved_email["_id"])}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing Postfix webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db = Depends(get_db)
):
    """
    Stripe Payment Webhook
    Handles subscription events
    """
    try:
        payload = await request.body()

        # Verify webhook signature
        if settings.STRIPE_WEBHOOK_SECRET:
            try:
                import stripe
                event = stripe.Webhook.construct_event(
                    payload,
                    stripe_signature,
                    settings.STRIPE_WEBHOOK_SECRET
                )
            except stripe.error.SignatureVerificationError:
                raise HTTPException(status_code=400, detail="Invalid signature")
        else:
            event = json.loads(payload)

        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})

        # Handle different event types
        if event_type == "checkout.session.completed":
            # Payment successful
            session = event_data
            customer_email = session.get("customer_email")
            subscription_id = session.get("subscription")

            # Find user by email
            user = db.users.find_one({"email": customer_email})
            if user:
                # Create subscription record
                subscription_doc = {
                    "user_id": user["_id"],
                    "stripe_subscription_id": subscription_id,
                    "stripe_customer_id": session.get("customer"),
                    "plan": session.get("metadata", {}).get("plan", "pro"),
                    "status": "active",
                    "current_period_start": datetime.utcnow(),
                    "created_at": datetime.utcnow()
                }

                db.subscriptions.insert_one(subscription_doc)

                # Update user subscription status
                db.users.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "subscription_tier": subscription_doc["plan"],
                            "subscription_status": "active"
                        }
                    }
                )

                logger.info(f"Created subscription for user {user['_id']}")

        elif event_type == "customer.subscription.updated":
            # Subscription updated
            subscription = event_data
            subscription_id = subscription.get("id")

            db.subscriptions.update_one(
                {"stripe_subscription_id": subscription_id},
                {
                    "$set": {
                        "status": subscription.get("status"),
                        "current_period_start": datetime.fromtimestamp(subscription.get("current_period_start")),
                        "current_period_end": datetime.fromtimestamp(subscription.get("current_period_end"))
                    }
                }
            )

        elif event_type == "customer.subscription.deleted":
            # Subscription cancelled
            subscription = event_data
            subscription_id = subscription.get("id")

            subscription_doc = db.subscriptions.find_one({"stripe_subscription_id": subscription_id})
            if subscription_doc:
                db.subscriptions.update_one(
                    {"_id": subscription_doc["_id"]},
                    {"$set": {"status": "cancelled", "cancelled_at": datetime.utcnow()}}
                )

                # Update user
                db.users.update_one(
                    {"_id": subscription_doc["user_id"]},
                    {"$set": {"subscription_status": "cancelled"}}
                )

        elif event_type == "invoice.payment_failed":
            # Payment failed
            invoice = event_data
            subscription_id = invoice.get("subscription")

            subscription_doc = db.subscriptions.find_one({"stripe_subscription_id": subscription_id})
            if subscription_doc:
                db.subscriptions.update_one(
                    {"_id": subscription_doc["_id"]},
                    {"$set": {"status": "past_due"}}
                )

                db.users.update_one(
                    {"_id": subscription_doc["user_id"]},
                    {"$set": {"subscription_status": "past_due"}}
                )

        return {"message": "Webhook processed"}

    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email/test")
async def test_email_webhook(db = Depends(get_db)):
    """
    Test endpoint to simulate email receiving
    """
    test_email = {
        "to": "john.67a1b2c3@apply.applyrush.ai",
        "from": "recruiter@techcorp.com",
        "subject": "Interview Invitation - Software Engineer Position",
        "body": """
        Hi John,

        We were impressed with your application for the Software Engineer position at TechCorp.

        We'd like to schedule an interview with you. Are you available for a Zoom call on January 20, 2025 at 2:00 PM PST?

        Join Zoom Meeting: https://zoom.us/j/123456789

        Looking forward to speaking with you!

        Best regards,
        Jane Smith
        Senior Recruiter, TechCorp
        """,
        "html": ""
    }

    try:
        email_service = EmailForwardingService(db)
        saved_email = email_service.save_received_email(test_email)

        return {
            "message": "Test email processed",
            "email_id": str(saved_email["_id"]),
            "email_type": saved_email["email_type"],
            "parsed_data": saved_email["parsed_data"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
