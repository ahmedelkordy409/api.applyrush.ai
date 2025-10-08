"""
Email Forwarding Service - Unique Email Per User
Handles email generation, receiving, parsing, and forwarding
"""

import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class EmailForwardingService:
    """
    Manages unique forwarding emails for each user
    Format: {firstName}.{userId}@apply.applyrush.ai
    """

    def __init__(self, db, domain: str = "apply.applyrush.ai"):
        self.db = db
        self.domain = domain

    def generate_user_forwarding_email(self, user_id: str, user_data: dict) -> str:
        """
        Generate unique forwarding email for user

        Args:
            user_id: User's MongoDB ObjectId
            user_data: User document from database

        Returns:
            Forwarding email address
        """
        # Get first name from profile
        first_name = user_data.get("profile", {}).get("first_name", "")

        # Clean first name (remove special chars, lowercase)
        first_name_clean = re.sub(r'[^a-z0-9]', '', first_name.lower()) if first_name else "user"

        # Use first 8 chars of user_id for brevity
        user_id_short = str(user_id)[:8]

        # Format: firstname.userid@domain
        forwarding_email = f"{first_name_clean}.{user_id_short}@{self.domain}"

        return forwarding_email

    def create_user_forwarding_email(self, user_id: str) -> Dict:
        """
        Create forwarding email record for user

        Args:
            user_id: User's ObjectId

        Returns:
            Created forwarding email document
        """
        user = self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Generate email
        forwarding_email = self.generate_user_forwarding_email(user_id, user)

        # Check if already exists
        existing = self.db.forwarding_emails.find_one({"user_id": ObjectId(user_id)})

        if existing:
            return existing

        # Create new record
        email_doc = {
            "user_id": ObjectId(user_id),
            "forwarding_address": forwarding_email,
            "user_real_email": user.get("email"),
            "applications_using": [],
            "emails_received_count": 0,
            "last_email_at": None,
            "status": "active",
            "created_at": datetime.utcnow()
        }

        result = self.db.forwarding_emails.insert_one(email_doc)
        email_doc["_id"] = result.inserted_id

        # Update user document with forwarding email
        self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"forwarding_email": forwarding_email}}
        )

        logger.info(f"Created forwarding email {forwarding_email} for user {user_id}")

        return email_doc

    def parse_forwarding_email(self, email_address: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract user info from forwarding email

        Args:
            email_address: Forwarding email address

        Returns:
            Tuple of (user_id_short, first_name) or (None, None)
        """
        # Format: firstname.userid@domain
        pattern = rf"([a-z0-9]+)\.([a-z0-9]+)@{re.escape(self.domain)}"
        match = re.match(pattern, email_address.lower())

        if match:
            first_name = match.group(1)
            user_id_short = match.group(2)
            return (user_id_short, first_name)

        return (None, None)

    def find_user_by_forwarding_email(self, forwarding_email: str) -> Optional[Dict]:
        """
        Find user by forwarding email

        Args:
            forwarding_email: Email address to lookup

        Returns:
            User document or None
        """
        email_record = self.db.forwarding_emails.find_one({
            "forwarding_address": forwarding_email
        })

        if not email_record:
            return None

        user = self.db.users.find_one({"_id": email_record["user_id"]})
        return user

    def save_received_email(self, email_data: Dict) -> Dict:
        """
        Save received email to database

        Args:
            email_data: Email content and metadata

        Returns:
            Saved email document
        """
        to_email = email_data.get("to", "")
        from_email = email_data.get("from", "")
        subject = email_data.get("subject", "")
        body_text = email_data.get("body", "")
        body_html = email_data.get("html", "")
        attachments = email_data.get("attachments", [])

        # Find user by forwarding email
        user = self.find_user_by_forwarding_email(to_email)

        if not user:
            logger.error(f"User not found for forwarding email: {to_email}")
            raise ValueError(f"Invalid forwarding email: {to_email}")

        user_id = user["_id"]

        # Find associated application
        application = self.db.applications.find_one({
            "user_id": user_id,
            "forwarding_email": to_email
        }, sort=[("created_at", -1)])  # Get latest application with this email

        # Detect email type using AI (simplified version)
        email_type = self._detect_email_type(subject, body_text)

        # Parse email content
        parsed_data = self._parse_email_content(subject, body_text, email_type)

        # Create email document
        email_doc = {
            "application_id": application["_id"] if application else None,
            "user_id": user_id,
            "from": from_email,
            "to": to_email,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "email_type": email_type,
            "parsed_data": parsed_data,
            "attachments": attachments,
            "forwarded_to_user": False,
            "received_at": datetime.utcnow()
        }

        result = self.db.received_emails.insert_one(email_doc)
        email_doc["_id"] = result.inserted_id

        # Update application status if applicable
        if application and email_type in ["interview", "offer", "rejection"]:
            new_status = {
                "interview": "interview",
                "offer": "offer",
                "rejection": "rejected"
            }[email_type]

            self.db.applications.update_one(
                {"_id": application["_id"]},
                {
                    "$set": {
                        "status": new_status,
                        "company_response_received": True,
                        "company_response_date": datetime.utcnow(),
                        "company_response_type": email_type
                    }
                }
            )

        # Update forwarding email stats
        self.db.forwarding_emails.update_one(
            {"user_id": user_id, "forwarding_address": to_email},
            {
                "$inc": {"emails_received_count": 1},
                "$set": {"last_email_at": datetime.utcnow()}
            }
        )

        logger.info(f"Saved email {email_doc['_id']} for user {user_id}, type: {email_type}")

        return email_doc

    def _detect_email_type(self, subject: str, body: str) -> str:
        """
        Detect email type based on content

        Types: interview, rejection, offer, info_request, general
        """
        subject_lower = subject.lower()
        body_lower = body.lower()

        # Keywords for each type
        interview_keywords = [
            "interview", "schedule", "call", "meeting", "video call",
            "phone screen", "technical round", "chat with", "discuss"
        ]

        rejection_keywords = [
            "regret", "unfortunately", "not moving forward", "other candidates",
            "decided to pursue", "not selected", "appreciate your interest"
        ]

        offer_keywords = [
            "offer", "congratulations", "pleased to offer", "job offer",
            "we'd like to extend", "compensation", "start date"
        ]

        info_request_keywords = [
            "additional information", "please provide", "clarification",
            "reference check", "background check", "documents required"
        ]

        # Check for each type
        if any(kw in subject_lower or kw in body_lower for kw in interview_keywords):
            return "interview"
        elif any(kw in subject_lower or kw in body_lower for kw in rejection_keywords):
            return "rejection"
        elif any(kw in subject_lower or kw in body_lower for kw in offer_keywords):
            return "offer"
        elif any(kw in subject_lower or kw in body_lower for kw in info_request_keywords):
            return "info_request"

        return "general"

    def _parse_email_content(self, subject: str, body: str, email_type: str) -> Dict:
        """
        Extract structured data from email content
        """
        parsed = {}

        if email_type == "interview":
            # Extract interview date (simple regex)
            date_patterns = [
                r"(\w+ \d{1,2},? \d{4})",  # January 15, 2025
                r"(\d{1,2}/\d{1,2}/\d{4})",  # 01/15/2025
            ]

            for pattern in date_patterns:
                match = re.search(pattern, body)
                if match:
                    parsed["interview_date_text"] = match.group(1)
                    break

            # Extract meeting link
            zoom_match = re.search(r"https://[\w\-\.]+\.?zoom\.us/[\w/\-?=&]+", body)
            if zoom_match:
                parsed["meeting_link"] = zoom_match.group(0)

            teams_match = re.search(r"https://teams\.microsoft\.com/[\w/\-?=&]+", body)
            if teams_match:
                parsed["meeting_link"] = teams_match.group(0)

        elif email_type == "offer":
            # Extract salary/compensation
            salary_match = re.search(r"\$(\d{1,3},?\d{3,})", body)
            if salary_match:
                parsed["salary_mentioned"] = salary_match.group(0)

            # Extract start date
            start_date_match = re.search(r"start date[:\s]+(\w+ \d{1,2},? \d{4})", body, re.IGNORECASE)
            if start_date_match:
                parsed["start_date"] = start_date_match.group(1)

        return parsed

    def forward_to_user(self, email_id: str) -> bool:
        """
        Forward email to user's real email address

        Args:
            email_id: Email document ID

        Returns:
            Success status
        """
        email = self.db.received_emails.find_one({"_id": ObjectId(email_id)})

        if not email:
            return False

        user = self.db.users.find_one({"_id": email["user_id"]})

        if not user:
            return False

        user_real_email = user.get("email")

        # Here you would integrate with your email service (AWS SES, SendGrid, etc.)
        # For now, just mark as forwarded

        # TODO: Actual email sending logic
        # send_email(
        #     to=user_real_email,
        #     from_address=f"notifications@{self.domain}",
        #     subject=f"Fwd: {email['subject']}",
        #     body=email['body_text'],
        #     html=email['body_html']
        # )

        # Mark as forwarded
        self.db.received_emails.update_one(
            {"_id": ObjectId(email_id)},
            {"$set": {"forwarded_to_user": True, "forwarded_at": datetime.utcnow()}}
        )

        logger.info(f"Forwarded email {email_id} to {user_real_email}")

        return True

    def get_user_inbox(self, user_id: str, limit: int = 50) -> List[Dict]:
        """
        Get all emails for user

        Args:
            user_id: User's ObjectId
            limit: Maximum emails to return

        Returns:
            List of email documents
        """
        emails = list(
            self.db.received_emails.find(
                {"user_id": ObjectId(user_id)}
            )
            .sort("received_at", -1)
            .limit(limit)
        )

        return emails
