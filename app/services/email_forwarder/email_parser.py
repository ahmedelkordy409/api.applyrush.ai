"""
Application Email Parser
Parse job application-related emails to detect status updates
"""

from typing import Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class ApplicationEmailParser:
    """Parse emails to detect job application status updates"""

    # Status detection patterns
    STATUS_PATTERNS = {
        'confirmed': [
            r'application\s+(has\s+been\s+)?received',
            r'thank you for (your )?applying',
            r'we.*received your application',
            r'application\s+(has\s+been\s+)?submitted',
            r'confirmation\s+(number|code)',
        ],
        'rejected': [
            r'unfortunately',
            r'not\s+(be\s+)?moving forward',
            r'not\s+(be\s+)?selected',
            r'decided to (pursue|move forward with) other candidates',
            r'regret to inform',
            r'application\s+(has\s+been\s+)?declined',
        ],
        'interview': [
            r'interview',
            r'schedule.*call',
            r'would like to (speak|talk|meet) with you',
            r'next steps.*conversation',
            r'phone\s+screen',
        ],
        'offer': [
            r'job offer',
            r'offer.*employment',
            r'pleased to offer',
            r'extend.*offer',
            r'offer letter',
        ],
        'pending': [
            r'under review',
            r'reviewing your application',
            r'currently reviewing',
            r'will be in touch',
        ]
    }

    def parse_application_email(
        self,
        from_address: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse email to detect application status

        Args:
            from_address: Sender email address
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)

        Returns:
            Dictionary with parsing results
        """
        try:
            # Combine subject and body for analysis
            full_text = f"{subject} {body}".lower()

            # Detect status
            detected_status = self._detect_status(full_text)

            # Extract confirmation number
            confirmation_number = self._extract_confirmation_number(body)

            # Check if this is an automated response
            is_automated = self._is_automated_email(from_address, subject, body)

            # Extract company name
            company_name = self._extract_company_name(from_address, body)

            return {
                "from_address": from_address,
                "subject": subject,
                "detected_status": detected_status,
                "status_update": detected_status is not None,
                "confirmation_number": confirmation_number,
                "is_automated": is_automated,
                "company_name": company_name,
                "parsed_successfully": True
            }

        except Exception as e:
            logger.error(f"Email parsing error: {str(e)}")
            return {
                "from_address": from_address,
                "subject": subject,
                "detected_status": None,
                "status_update": False,
                "error": str(e),
                "parsed_successfully": False
            }

    def _detect_status(self, text: str) -> Optional[str]:
        """
        Detect application status from email text

        Args:
            text: Email text (subject + body, lowercase)

        Returns:
            Detected status or None
        """
        # Priority order: offer > interview > rejected > confirmed > pending
        priority_order = ['offer', 'interview', 'rejected', 'confirmed', 'pending']

        for status in priority_order:
            patterns = self.STATUS_PATTERNS.get(status, [])
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    logger.info(f"Detected status '{status}' from pattern '{pattern}'")
                    return status

        return None

    def _extract_confirmation_number(self, body: str) -> Optional[str]:
        """
        Extract confirmation number from email body

        Common patterns:
        - "Confirmation #: ABC-123-XYZ"
        - "Application ID: 123456"
        - "Reference Number: REF-789"
        """
        patterns = [
            r'confirmation\s*(?:number|code|#)?\s*:?\s*([A-Z0-9-]+)',
            r'application\s*(?:id|number)?\s*:?\s*([A-Z0-9-]+)',
            r'reference\s*(?:number|code|#)?\s*:?\s*([A-Z0-9-]+)',
            r'tracking\s*(?:number|code|#)?\s*:?\s*([A-Z0-9-]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                confirmation = match.group(1)
                logger.info(f"Extracted confirmation number: {confirmation}")
                return confirmation

        return None

    def _is_automated_email(self, from_address: str, subject: str, body: str) -> bool:
        """Check if email is automated (vs from human recruiter)"""
        automated_indicators = [
            'noreply',
            'no-reply',
            'donotreply',
            'automated',
            'auto-reply',
            'system@',
            'notifications@',
        ]

        from_lower = from_address.lower()
        for indicator in automated_indicators:
            if indicator in from_lower:
                return True

        # Check for automated signatures in body
        automated_signatures = [
            'this is an automated message',
            'do not reply to this email',
            'this mailbox is not monitored',
        ]

        body_lower = body.lower()
        for signature in automated_signatures:
            if signature in body_lower:
                return True

        return False

    def _extract_company_name(self, from_address: str, body: str) -> Optional[str]:
        """Extract company name from email"""
        try:
            # Try to get from email domain
            if '@' in from_address:
                domain = from_address.split('@')[1]
                # Remove common email providers
                if not any(provider in domain.lower() for provider in ['gmail', 'yahoo', 'outlook', 'hotmail']):
                    # Extract company name from domain
                    company = domain.split('.')[0]
                    return company.capitalize()

            # Try to extract from email signature
            # Look for common patterns like "Best regards, Company Name"
            # This is a simple implementation - could be enhanced with NLP

            return None

        except:
            return None


__all__ = ["ApplicationEmailParser"]
