"""
Job Application Email Service
Handles sending actual job applications via email with unique forwarding addresses
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import aiosmtplib
import os
from pathlib import Path

from app.core.config import settings
from app.services.email_forwarding_service import EmailForwardingService

logger = logging.getLogger(__name__)


class JobApplicationEmailService:
    """
    Service for sending actual job applications via email
    Creates unique forwarding emails per user for tracking responses
    """

    def __init__(self, db):
        self.db = db
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', '')
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
        self.from_email = getattr(settings, 'FROM_EMAIL', 'noreply@applyrush.ai')
        self.forwarding_service = EmailForwardingService(db)

    async def apply_via_email(
        self,
        user_id: str,
        job_data: Dict[str, Any],
        resume_path: Optional[str] = None,
        cover_letter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send job application via email

        Args:
            user_id: User's MongoDB ObjectId
            job_data: Job information including apply_email
            resume_path: Path to user's resume PDF
            cover_letter: Optional AI-generated cover letter

        Returns:
            Result dict with success status and details
        """
        try:
            from bson import ObjectId

            # Get user data
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"success": False, "error": "User not found"}

            # Extract job application email
            apply_email = self._extract_application_email(job_data)
            if not apply_email:
                return {"success": False, "error": "No application email found in job posting"}

            # Get or create user's unique forwarding email
            forwarding_email = await self._get_or_create_forwarding_email(user_id, user)

            # Compose application email
            subject = self._compose_subject(user, job_data)
            body = self._compose_body(user, job_data, cover_letter)

            # Send email with resume attachment
            email_sent = await self._send_application_email(
                to_email=apply_email,
                reply_to=forwarding_email,
                subject=subject,
                body=body,
                resume_path=resume_path,
                user=user
            )

            if email_sent:
                # Record the application email sent
                await self._record_application_email(
                    user_id=user_id,
                    job_data=job_data,
                    forwarding_email=forwarding_email,
                    apply_email=apply_email
                )

                logger.info(f"Application sent via email for user {user_id} to {apply_email}")

                return {
                    "success": True,
                    "method": "email",
                    "recipient": apply_email,
                    "forwarding_email": forwarding_email,
                    "sent_at": datetime.utcnow().isoformat()
                }
            else:
                return {"success": False, "error": "Failed to send email"}

        except Exception as e:
            logger.error(f"Error sending job application email: {e}")
            return {"success": False, "error": str(e)}

    def _extract_application_email(self, job_data: Dict[str, Any]) -> Optional[str]:
        """Extract application email from job data"""
        # Try multiple possible field names
        email_fields = ['apply_email', 'application_email', 'contact_email', 'email']

        for field in email_fields:
            email = job_data.get(field)
            if email:
                return email

        # Try to extract from apply_url if it's a mailto: link
        apply_url = job_data.get('apply_url', '')
        if apply_url.startswith('mailto:'):
            return apply_url.replace('mailto:', '').split('?')[0]

        return None

    async def _get_or_create_forwarding_email(self, user_id: str, user: Dict[str, Any]) -> str:
        """Get existing or create new forwarding email for user"""
        # IMPORTANT: For Gmail forwarding to work, we use the user's actual email
        # Gmail supports "+" aliases, so we can track which job the reply is for
        # Example: user+job123@gmail.com -> forwards to user@gmail.com

        user_email = user.get('email', '')

        if not user_email:
            return self.from_email

        # Use the user's real email for Reply-To
        # This ensures replies go directly to the user
        return user_email

    def _compose_subject(self, user: Dict[str, Any], job_data: Dict[str, Any]) -> str:
        """Compose professional email subject line"""
        profile = user.get('profile', {})
        first_name = profile.get('first_name', '')
        last_name = profile.get('last_name', '')
        user_name = f"{first_name} {last_name}".strip() or "Candidate"

        job_title = job_data.get('title', 'Position')

        return f"Application for {job_title} - {user_name}"

    def _compose_body(
        self,
        user: Dict[str, Any],
        job_data: Dict[str, Any],
        cover_letter: Optional[str] = None
    ) -> str:
        """Compose professional email body"""
        profile = user.get('profile', {})
        first_name = profile.get('first_name', '')
        last_name = profile.get('last_name', '')

        job_title = job_data.get('title', 'the position')
        company = job_data.get('company', 'your company')

        # Use AI-generated cover letter if available
        if cover_letter:
            body = f"{cover_letter}\n\n"
        else:
            # Use professional default template
            body = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company}.

With my background and experience, I believe I would be an excellent fit for this role. I have attached my resume for your review, which provides detailed information about my qualifications and accomplishments.

I am excited about the opportunity to contribute to {company} and would welcome the chance to discuss how my skills align with your needs.

Thank you for considering my application. I look forward to hearing from you.

Best regards,
{first_name} {last_name}
"""

        # Add signature
        body += f"\n\n---\n"
        body += f"Email: {user.get('email')}\n"
        if phone := profile.get('phone'):
            body += f"Phone: {phone}\n"
        if linkedin := profile.get('linkedin_url'):
            body += f"LinkedIn: {linkedin}\n"
        if portfolio := profile.get('portfolio_url'):
            body += f"Portfolio: {portfolio}\n"

        body += f"\nThis application was submitted via ApplyRush.AI\n"

        return body

    async def _send_application_email(
        self,
        to_email: str,
        reply_to: str,
        subject: str,
        body: str,
        resume_path: Optional[str],
        user: Dict[str, Any]
    ) -> bool:
        """Send the actual application email with resume attachment"""
        try:
            # Create message
            message = MIMEMultipart()
            message['From'] = self.from_email
            message['To'] = to_email
            message['Reply-To'] = reply_to  # Unique forwarding email for tracking
            message['Subject'] = subject

            # Add body
            body_part = MIMEText(body, 'plain')
            message.attach(body_part)

            # Attach resume if available
            if resume_path and os.path.exists(resume_path):
                with open(resume_path, 'rb') as resume_file:
                    resume_attachment = MIMEApplication(resume_file.read(), _subtype='pdf')

                    # Get user name for filename
                    profile = user.get('profile', {})
                    first_name = profile.get('first_name', 'Resume')
                    last_name = profile.get('last_name', '')
                    filename = f"{first_name}_{last_name}_Resume.pdf".replace(' ', '_')

                    resume_attachment.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=filename
                    )
                    message.attach(resume_attachment)

            # Send via SMTP
            async with aiosmtplib.SMTP(hostname=self.smtp_server, port=self.smtp_port) as smtp:
                await smtp.starttls()
                if self.smtp_username and self.smtp_password:
                    await smtp.login(self.smtp_username, self.smtp_password)
                await smtp.send_message(message)

            logger.info(f"Application email sent to {to_email} with reply-to {reply_to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send application email: {e}")
            return False

    async def _record_application_email(
        self,
        user_id: str,
        job_data: Dict[str, Any],
        forwarding_email: str,
        apply_email: str
    ):
        """Record the sent application email for tracking"""
        from bson import ObjectId

        email_record = {
            "user_id": ObjectId(user_id),
            "job_id": job_data.get('id'),
            "job_title": job_data.get('title'),
            "company": job_data.get('company'),
            "sent_to": apply_email,
            "reply_to_forwarding": forwarding_email,
            "sent_at": datetime.utcnow(),
            "email_type": "job_application",
            "status": "sent"
        }

        self.db.sent_emails.insert_one(email_record)

        # Update forwarding email stats
        self.db.forwarding_emails.update_one(
            {"forwarding_address": forwarding_email},
            {
                "$push": {"applications_using": job_data.get('id')},
                "$set": {"last_used_at": datetime.utcnow()}
            }
        )


async def send_job_application_email(
    db,
    user_id: str,
    job_data: Dict[str, Any],
    resume_path: Optional[str] = None,
    cover_letter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper function to send job application email

    Args:
        db: MongoDB database connection
        user_id: User's ObjectId as string
        job_data: Job information dict
        resume_path: Optional path to resume PDF
        cover_letter: Optional AI-generated cover letter

    Returns:
        Result dict with success status
    """
    service = JobApplicationEmailService(db)
    return await service.apply_via_email(user_id, job_data, resume_path, cover_letter)
