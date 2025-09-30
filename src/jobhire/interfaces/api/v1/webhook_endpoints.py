"""
Webhook and callback API endpoints.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.security import HTTPBearer
import structlog
from pydantic import BaseModel, Field
import hmac
import hashlib

from jobhire.shared.infrastructure.monitoring.metrics import measure_http_request
from jobhire.shared.application.exceptions import BusinessRuleException


logger = structlog.get_logger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/webhooks", tags=["🔗 Webhooks & Callbacks"])


# Request models
class EmailReceivedWebhook(BaseModel):
    email_id: str = Field(..., description="Email identifier")
    from_address: str = Field(..., description="Sender email address")
    to_address: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")
    received_at: datetime = Field(..., description="When email was received")
    email_type: Optional[str] = Field(None, description="Type of email (interview, rejection, etc.)")
    job_application_id: Optional[str] = Field(None, description="Related job application ID")
    company_name: Optional[str] = Field(None, description="Company name")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ApplicationStatusChangedWebhook(BaseModel):
    application_id: str = Field(..., description="Application identifier")
    user_id: str = Field(..., description="User identifier")
    job_id: str = Field(..., description="Job identifier")
    old_status: str = Field(..., description="Previous application status")
    new_status: str = Field(..., description="New application status")
    changed_at: datetime = Field(..., description="When status changed")
    change_reason: Optional[str] = Field(None, description="Reason for status change")
    company_name: Optional[str] = Field(None, description="Company name")
    job_title: Optional[str] = Field(None, description="Job title")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


@router.post("/email-received")
@measure_http_request("/webhooks/email-received")
async def handle_email_received(
    webhook_data: EmailReceivedWebhook,
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_webhook_source: Optional[str] = Header(None, alias="X-Webhook-Source")
) -> Dict[str, Any]:
    """Handle email received webhook."""
    try:
        logger.info(
            "Received email webhook",
            email_id=webhook_data.email_id,
            from_address=webhook_data.from_address,
            to_address=webhook_data.to_address,
            email_type=webhook_data.email_type,
            source=x_webhook_source
        )

        # Verify webhook signature if provided
        if x_signature and x_webhook_source:
            await _verify_webhook_signature(request, x_signature, x_webhook_source)

        # Process email based on type
        if webhook_data.email_type == "interview_invitation":
            await _process_interview_invitation_email(webhook_data)
        elif webhook_data.email_type == "rejection":
            await _process_rejection_email(webhook_data)
        elif webhook_data.email_type == "application_acknowledgement":
            await _process_acknowledgement_email(webhook_data)
        elif webhook_data.email_type == "additional_info_request":
            await _process_info_request_email(webhook_data)
        elif webhook_data.email_type == "position_status_update":
            await _process_status_update_email(webhook_data)
        else:
            # Generic email processing
            await _process_generic_email(webhook_data)

        logger.info(
            "Email webhook processed successfully",
            email_id=webhook_data.email_id,
            email_type=webhook_data.email_type
        )

        return {
            "success": True,
            "message": "Email webhook processed successfully",
            "email_id": webhook_data.email_id,
            "processed_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error(
            "Failed to process email webhook",
            email_id=webhook_data.email_id,
            error=str(e),
            error_type=type(e).__name__
        )

        if isinstance(e, BusinessRuleException):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to process email webhook")


@router.post("/application-status-changed")
@measure_http_request("/webhooks/application-status-changed")
async def handle_application_status_changed(
    webhook_data: ApplicationStatusChangedWebhook,
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_webhook_source: Optional[str] = Header(None, alias="X-Webhook-Source")
) -> Dict[str, Any]:
    """Handle application status changed webhook."""
    try:
        logger.info(
            "Received application status change webhook",
            application_id=webhook_data.application_id,
            user_id=webhook_data.user_id,
            old_status=webhook_data.old_status,
            new_status=webhook_data.new_status,
            source=x_webhook_source
        )

        # Verify webhook signature if provided
        if x_signature and x_webhook_source:
            await _verify_webhook_signature(request, x_signature, x_webhook_source)

        # Process status change
        await _process_application_status_change(webhook_data)

        # Trigger notifications based on new status
        await _trigger_status_change_notifications(webhook_data)

        logger.info(
            "Application status change webhook processed successfully",
            application_id=webhook_data.application_id,
            new_status=webhook_data.new_status
        )

        return {
            "success": True,
            "message": "Application status change webhook processed successfully",
            "application_id": webhook_data.application_id,
            "new_status": webhook_data.new_status,
            "processed_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error(
            "Failed to process application status change webhook",
            application_id=webhook_data.application_id,
            error=str(e),
            error_type=type(e).__name__
        )

        if isinstance(e, BusinessRuleException):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail="Failed to process application status change webhook")


# Helper functions for webhook processing

async def _verify_webhook_signature(request: Request, signature: str, source: str) -> None:
    """Verify webhook signature for security."""
    try:
        # Get the raw request body
        body = await request.body()

        # This would use the actual webhook secret for the source
        # For now, we'll just log the verification attempt
        logger.info(
            "Verifying webhook signature",
            source=source,
            signature_provided=bool(signature)
        )

        # In production, implement actual HMAC verification:
        # expected_signature = hmac.new(
        #     webhook_secret.encode(),
        #     body,
        #     hashlib.sha256
        # ).hexdigest()

        # if not hmac.compare_digest(signature, expected_signature):
        #     raise BusinessRuleException("Invalid webhook signature")

    except Exception as e:
        logger.error("Webhook signature verification failed", error=str(e))
        raise BusinessRuleException(f"Webhook signature verification failed: {str(e)}")


async def _process_interview_invitation_email(webhook_data: EmailReceivedWebhook) -> None:
    """Process interview invitation email."""
    logger.info(
        "Processing interview invitation email",
        email_id=webhook_data.email_id,
        job_application_id=webhook_data.job_application_id
    )

    # Implementation would:
    # 1. Update job application status to "interview_scheduled"
    # 2. Extract interview details from email
    # 3. Create calendar event
    # 4. Notify user if enabled
    # 5. Update application queue status


async def _process_rejection_email(webhook_data: EmailReceivedWebhook) -> None:
    """Process rejection email."""
    logger.info(
        "Processing rejection email",
        email_id=webhook_data.email_id,
        job_application_id=webhook_data.job_application_id
    )

    # Implementation would:
    # 1. Update job application status to "rejected"
    # 2. Extract rejection reason if available
    # 3. Update application queue status
    # 4. Notify user if enabled


async def _process_acknowledgement_email(webhook_data: EmailReceivedWebhook) -> None:
    """Process application acknowledgement email."""
    logger.info(
        "Processing acknowledgement email",
        email_id=webhook_data.email_id,
        job_application_id=webhook_data.job_application_id
    )

    # Implementation would:
    # 1. Update job application status to "acknowledged"
    # 2. Extract application reference number
    # 3. Update application queue status


async def _process_info_request_email(webhook_data: EmailReceivedWebhook) -> None:
    """Process additional info request email."""
    logger.info(
        "Processing info request email",
        email_id=webhook_data.email_id,
        job_application_id=webhook_data.job_application_id
    )

    # Implementation would:
    # 1. Update job application status to "info_requested"
    # 2. Extract requested information details
    # 3. Create task for user response
    # 4. Notify user immediately


async def _process_status_update_email(webhook_data: EmailReceivedWebhook) -> None:
    """Process position status update email."""
    logger.info(
        "Processing status update email",
        email_id=webhook_data.email_id,
        job_application_id=webhook_data.job_application_id
    )

    # Implementation would:
    # 1. Parse status update from email
    # 2. Update job application status
    # 3. Log status history
    # 4. Notify user if enabled


async def _process_generic_email(webhook_data: EmailReceivedWebhook) -> None:
    """Process generic email."""
    logger.info(
        "Processing generic email",
        email_id=webhook_data.email_id,
        from_address=webhook_data.from_address
    )

    # Implementation would:
    # 1. Store email for later review
    # 2. Attempt to classify email type using AI
    # 3. Extract relevant information
    # 4. Create notification for user


async def _process_application_status_change(webhook_data: ApplicationStatusChangedWebhook) -> None:
    """Process application status change."""
    logger.info(
        "Processing application status change",
        application_id=webhook_data.application_id,
        old_status=webhook_data.old_status,
        new_status=webhook_data.new_status
    )

    # Implementation would:
    # 1. Update application record
    # 2. Log status change history
    # 3. Update related queue item
    # 4. Update metrics and analytics


async def _trigger_status_change_notifications(webhook_data: ApplicationStatusChangedWebhook) -> None:
    """Trigger notifications based on status change."""
    logger.info(
        "Triggering status change notifications",
        application_id=webhook_data.application_id,
        new_status=webhook_data.new_status
    )

    # Implementation would:
    # 1. Check user notification preferences
    # 2. Send appropriate notifications (email, SMS, push)
    # 3. Update notification log