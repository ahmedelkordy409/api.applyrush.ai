"""
Email Forwarding Service
Manages forwarding email addresses for job applications
Integrates with existing ApplyRush.AI email service
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from ..email import email_service

logger = logging.getLogger(__name__)


@dataclass
class ForwardingEmail:
    """Forwarding email configuration"""
    forwarding_address: str  # e.g., user123.job456.20250104@apply.applyrush.ai
    user_id: str
    job_id: str
    real_email: str  # User's actual email address
    created_at: datetime
    expires_at: datetime
    status: str  # active, expired, disabled
    application_id: Optional[str] = None
    emails_received: int = 0
    last_email_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['expires_at'] = self.expires_at.isoformat() if self.expires_at else None
        data['last_email_at'] = self.last_email_at.isoformat() if self.last_email_at else None
        return data


class EmailForwarderService:
    """
    Manage email forwarding for job applications
    Integrates with existing email service and MongoDB
    """

    def __init__(self, forwarding_domain: str = "apply.applyrush.ai"):
        """Initialize email forwarder service"""
        self.forwarding_domain = forwarding_domain
        self.default_expiry_days = 90

    def generate_forwarding_email(
        self,
        user_id: str,
        job_id: str,
        real_email: str,
        application_id: Optional[str] = None
    ) -> ForwardingEmail:
        """
        Generate unique forwarding email address

        Args:
            user_id: User ID
            job_id: Job ID
            real_email: User's real email address
            application_id: Optional application ID

        Returns:
            ForwardingEmail object
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        forwarding_address = f"{user_id}.{job_id}.{timestamp}@{self.forwarding_domain}"

        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(days=self.default_expiry_days)

        return ForwardingEmail(
            forwarding_address=forwarding_address,
            user_id=user_id,
            job_id=job_id,
            real_email=real_email,
            created_at=created_at,
            expires_at=expires_at,
            status="active",
            application_id=application_id,
            emails_received=0
        )

    async def process_incoming_email(
        self,
        forwarding_address: str,
        from_address: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process incoming email to forwarding address

        Steps:
        1. Parse forwarding address to get user_id and job_id
        2. Look up forwarding email configuration
        3. Check if expired
        4. Parse email content for application status
        5. Update application status in database
        6. Forward email to user's real address

        Args:
            forwarding_address: The forwarding email that received the message
            from_address: Sender's email
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)

        Returns:
            Processing result
        """
        try:
            logger.info(f"Processing email to {forwarding_address} from {from_address}")

            # Parse forwarding address
            parsed = self._parse_forwarding_address(forwarding_address)
            if not parsed:
                logger.error(f"Invalid forwarding address: {forwarding_address}")
                return {"success": False, "error": "Invalid forwarding address"}

            user_id = parsed['user_id']
            job_id = parsed['job_id']

            # Get forwarding email config from database
            # In production, query MongoDB for the forwarding email record
            forwarding_config = await self._get_forwarding_config(forwarding_address)

            if not forwarding_config:
                logger.warning(f"Forwarding config not found for {forwarding_address}")
                # Still try to forward to user
                real_email = None  # Would need to look up user's email from user_id
            else:
                # Check if expired
                if forwarding_config['status'] != 'active':
                    logger.warning(f"Forwarding address is {forwarding_config['status']}")
                    return {"success": False, "error": f"Forwarding address is {forwarding_config['status']}"}

                real_email = forwarding_config['real_email']

            # Parse email for application updates
            from .email_parser import ApplicationEmailParser
            parser = ApplicationEmailParser()
            parsed_email = parser.parse_application_email(
                from_address=from_address,
                subject=subject,
                body=body,
                html_body=html_body
            )

            # Update application status if status change detected
            if parsed_email['status_update']:
                await self._update_application_status(
                    user_id=user_id,
                    job_id=job_id,
                    status=parsed_email['detected_status'],
                    email_data=parsed_email
                )

            # Update forwarding email stats
            await self._update_forwarding_stats(forwarding_address)

            # Forward email to user's real address
            if real_email:
                forwarding_result = await self._forward_to_user(
                    real_email=real_email,
                    from_address=from_address,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                    metadata=parsed_email
                )

                return {
                    "success": True,
                    "forwarded": forwarding_result,
                    "status_update": parsed_email['status_update'],
                    "detected_status": parsed_email.get('detected_status')
                }
            else:
                return {
                    "success": True,
                    "forwarded": False,
                    "error": "Real email address not found"
                }

        except Exception as e:
            logger.error(f"Email processing error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _forward_to_user(
        self,
        real_email: str,
        from_address: str,
        subject: str,
        body: str,
        html_body: Optional[str],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Forward email to user's real address

        Adds header indicating this is a forwarded application email
        """
        try:
            # Add forwarding header to body
            forwarding_note = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Forwarded Application Email - ApplyRush.AI
From: {from_address}
Status: {metadata.get('detected_status', 'Unknown')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            forwarded_body = forwarding_note + body

            # Prepare HTML if available
            forwarded_html = None
            if html_body:
                html_note = f"""
<div style="background: #f3f4f6; padding: 15px; border-left: 4px solid #2563eb; margin-bottom: 20px;">
    <h3 style="margin: 0 0 10px 0;">📧 Forwarded Application Email - ApplyRush.AI</h3>
    <p style="margin: 5px 0;"><strong>From:</strong> {from_address}</p>
    <p style="margin: 5px 0;"><strong>Status:</strong> {metadata.get('detected_status', 'Unknown')}</p>
</div>
"""
                forwarded_html = html_note + html_body

            # Send via existing email service
            success = await email_service.send_email(
                to_email=real_email,
                subject=f"[Application Update] {subject}",
                html_content=forwarded_html or forwarded_body,
                text_content=forwarded_body
            )

            if success:
                logger.info(f"Forwarded email to {real_email}")
            else:
                logger.error(f"Failed to forward email to {real_email}")

            return success

        except Exception as e:
            logger.error(f"Email forwarding error: {str(e)}")
            return False

    def _parse_forwarding_address(self, forwarding_address: str) -> Optional[Dict[str, str]]:
        """
        Parse forwarding email address to extract components

        Format: {user_id}.{job_id}.{timestamp}@{domain}

        Args:
            forwarding_address: Full forwarding email address

        Returns:
            Dictionary with user_id, job_id, timestamp, domain
        """
        try:
            # Split email address
            local_part, domain = forwarding_address.split('@')

            # Split local part
            parts = local_part.split('.')

            if len(parts) < 3:
                return None

            user_id = parts[0]
            job_id = parts[1]
            timestamp = parts[2] if len(parts) > 2 else None

            return {
                'user_id': user_id,
                'job_id': job_id,
                'timestamp': timestamp,
                'domain': domain
            }

        except Exception as e:
            logger.error(f"Forwarding address parsing error: {str(e)}")
            return None

    async def _get_forwarding_config(self, forwarding_address: str) -> Optional[Dict[str, Any]]:
        """
        Get forwarding email configuration from database

        In production, query MongoDB:
        db.forwarding_emails.find_one({"forwarding_address": forwarding_address})
        """
        # Placeholder - implement MongoDB query
        logger.debug(f"Looking up forwarding config for {forwarding_address}")
        return None

    async def _update_forwarding_stats(self, forwarding_address: str) -> None:
        """
        Update forwarding email statistics

        Increment emails_received count
        Update last_email_at timestamp
        """
        try:
            # Placeholder - implement MongoDB update
            logger.debug(f"Updating stats for {forwarding_address}")
            pass
        except Exception as e:
            logger.error(f"Stats update error: {str(e)}")

    async def _update_application_status(
        self,
        user_id: str,
        job_id: str,
        status: str,
        email_data: Dict[str, Any]
    ) -> None:
        """
        Update application status based on email content

        Updates MongoDB application record with new status
        """
        try:
            logger.info(f"Updating application status for user {user_id}, job {job_id} to {status}")

            # Placeholder - implement MongoDB update
            # db.applications.update_one(
            #     {"user_id": user_id, "job_id": job_id},
            #     {
            #         "$set": {
            #             "status": status,
            #             "last_email_at": datetime.utcnow(),
            #             "confirmation_number": email_data.get('confirmation_number')
            #         },
            #         "$push": {
            #             "email_history": {
            #                 "timestamp": datetime.utcnow(),
            #                 "from": email_data.get('from_address'),
            #                 "subject": email_data.get('subject'),
            #                 "status": status
            #             }
            #         }
            #     }
            # )

        except Exception as e:
            logger.error(f"Application status update error: {str(e)}")


__all__ = ["EmailForwarderService", "ForwardingEmail"]
