"""
Email Applicator - Handle job applications via email forwarding
Integrates with ApplyRush.AI email forwarding system
"""

from typing import Dict, Any, Optional
import logging
from .base_applicator import BaseApplicator, ATSType, ApplicationResult, ApplicationStatus
from ..email import email_service

logger = logging.getLogger(__name__)


class EmailApplicator(BaseApplicator):
    """
    Handle job applications that use "Apply via Email" functionality
    Uses ApplyRush.AI email forwarding to track responses
    """

    async def detect_ats_type(self) -> ATSType:
        """Detect if job uses email application"""
        try:
            # Check for email application indicators
            email_indicators = [
                'apply by email',
                'send resume to',
                'email your resume',
                'submit via email',
                'mailto:',
            ]

            page_text = await self.page.inner_text('body')
            page_html = await self.page.content()

            for indicator in email_indicators:
                if indicator in page_text.lower() or indicator in page_html.lower():
                    return ATSType.EMAIL

            return ATSType.GENERIC

        except Exception as e:
            logger.error(f"ATS detection failed: {str(e)}")
            return ATSType.GENERIC

    async def fill_form(self, user_data: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        """
        Handle email-based application

        For email applications:
        1. Extract recipient email address
        2. Compose email with resume
        3. Send via our email service with forwarding address as reply-to
        """
        try:
            # Extract email address from page
            recipient_email = await self._extract_email_address()

            if not recipient_email:
                self.errors.append("Could not find recipient email address")
                return {"success": False, "error": "No email address found"}

            # Prepare email content
            email_subject = self._compose_subject(user_data)
            email_body = self._compose_body(user_data)

            # Get forwarding email for tracking
            forwarding_email = user_data.get('application_email', user_data.get('email'))

            # Metadata for tracking
            metadata = {
                "recipient_email": recipient_email,
                "forwarding_email": forwarding_email,
                "job_url": user_data.get('job_url', ''),
                "job_id": user_data.get('job_id', ''),
                "resume_path": resume_path,
            }

            self.steps_completed.append("email_prepared")

            return {
                "success": True,
                "method": "email",
                "recipient": recipient_email,
                "subject": email_subject,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Email application preparation failed: {str(e)}")
            self.errors.append(str(e))
            return {"success": False, "error": str(e)}

    async def submit_application(self) -> Dict[str, Any]:
        """
        Submit application via email

        Note: Actual email sending is handled by email service
        This method prepares the submission data
        """
        try:
            self.steps_completed.append("email_submission_prepared")
            return {
                "success": True,
                "method": "email",
                "note": "Email will be sent via email service"
            }

        except Exception as e:
            logger.error(f"Email submission failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _extract_email_address(self) -> Optional[str]:
        """Extract hiring manager email address from page"""
        import re

        try:
            # Get page content
            page_html = await self.page.content()
            page_text = await self.page.inner_text('body')

            # Look for mailto: links
            mailto_pattern = r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            mailto_match = re.search(mailto_pattern, page_html)

            if mailto_match:
                return mailto_match.group(1)

            # Look for email addresses in text
            email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
            email_match = re.search(email_pattern, page_text)

            if email_match:
                email = email_match.group(0)
                # Exclude common non-hiring emails
                excluded_domains = ['noreply', 'no-reply', 'donotreply']
                if not any(excluded in email.lower() for excluded in excluded_domains):
                    return email

            return None

        except Exception as e:
            logger.error(f"Email extraction failed: {str(e)}")
            return None

    def _compose_subject(self, user_data: Dict[str, Any]) -> str:
        """Compose email subject line"""
        job_title = user_data.get('job_title', 'Position')
        user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

        return f"Application for {job_title} - {user_name}"

    def _compose_body(self, user_data: Dict[str, Any]) -> str:
        """Compose professional email body"""
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        job_title = user_data.get('job_title', 'the position')
        company_name = user_data.get('company_name', 'your company')

        # Use cover letter if available
        cover_letter = user_data.get('cover_letter', '')
        if cover_letter:
            return cover_letter

        # Default professional template
        body = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company_name}.

With my background and experience, I believe I would be an excellent fit for this role. I have attached my resume for your review, which provides detailed information about my qualifications and accomplishments.

I am excited about the opportunity to contribute to {company_name} and would welcome the chance to discuss how my skills align with your needs.

Thank you for considering my application. I look forward to hearing from you.

Best regards,
{first_name} {last_name}

---
This application was submitted via ApplyRush.AI
"""
        return body


__all__ = ["EmailApplicator"]
