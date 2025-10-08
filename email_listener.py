"""
SMTP Email Listener Server
Listens for incoming emails and processes them for job application responses
"""

import asyncio
import email
from email.message import EmailMessage
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP as SMTPServer
from datetime import datetime
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.services.email_forwarding_service import EmailForwardingService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JobApplicationEmailHandler:
    """Handler for incoming job application response emails"""

    def __init__(self, db):
        self.db = db
        self.forwarding_service = EmailForwardingService(db)

    async def handle_DATA(self, server, session, envelope):
        """
        Handle incoming email message

        Args:
            server: SMTP server instance
            session: Current session
            envelope: Email envelope with sender, recipients, and content
        """
        try:
            logger.info(f"📧 Received email from: {envelope.mail_from}")
            logger.info(f"📬 To: {envelope.rcpt_tos}")

            # Parse email message
            message = email.message_from_bytes(envelope.content)

            # Extract email details
            from_email = envelope.mail_from
            to_emails = envelope.rcpt_tos
            subject = message.get('Subject', 'No Subject')

            # Get email body
            body = self._extract_email_body(message)

            logger.info(f"📝 Subject: {subject}")
            logger.info(f"📄 Body preview: {body[:200]}...")

            # Process each recipient (forwarding address)
            for to_email in to_emails:
                await self._process_email_for_user(
                    from_email=from_email,
                    to_email=to_email,
                    subject=subject,
                    body=body,
                    raw_message=envelope.content
                )

            return '250 Message accepted for delivery'

        except Exception as e:
            logger.error(f"❌ Error handling email: {e}")
            return '550 Error processing message'

    def _extract_email_body(self, message: EmailMessage) -> str:
        """Extract email body text from message"""
        body = ""

        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        body = part.get_payload(decode=True).decode()
                        break
                    except:
                        pass
                elif content_type == 'text/html' and not body:
                    try:
                        body = part.get_payload(decode=True).decode()
                    except:
                        pass
        else:
            try:
                body = message.get_payload(decode=True).decode()
            except:
                body = str(message.get_payload())

        return body

    async def _process_email_for_user(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        raw_message: bytes
    ):
        """Process incoming email for a specific user"""
        try:
            # Find user by forwarding email
            user = self.forwarding_service.find_user_by_forwarding_email(to_email)

            if not user:
                logger.warning(f"⚠️  No user found for forwarding email: {to_email}")
                return

            user_id = str(user["_id"])
            logger.info(f"✅ Found user: {user.get('email')} for forwarding email: {to_email}")

            # Detect email type (job response, interview invite, rejection, etc.)
            email_type = self._detect_email_type(subject, body)
            logger.info(f"📊 Email type: {email_type}")

            # Save email to database
            email_doc = {
                "user_id": user["_id"],
                "from_email": from_email,
                "to_email": to_email,
                "subject": subject,
                "body": body,
                "raw_message": raw_message.decode('utf-8', errors='ignore'),
                "email_type": email_type,
                "status": "unread",
                "received_at": datetime.utcnow(),
                "processed": False
            }

            result = await self.db.received_emails.insert_one(email_doc)
            logger.info(f"💾 Saved email to database: {result.inserted_id}")

            # Update forwarding email record
            await self.db.forwarding_emails.update_one(
                {"forwarding_address": to_email},
                {
                    "$inc": {"emails_received_count": 1},
                    "$set": {"last_email_at": datetime.utcnow()}
                }
            )

            # Process based on email type
            if email_type == "interview_invite":
                await self._handle_interview_invite(user_id, email_doc)
            elif email_type == "offer":
                await self._handle_job_offer(user_id, email_doc)
            elif email_type == "rejection":
                await self._handle_rejection(user_id, email_doc)
            else:
                await self._handle_general_response(user_id, email_doc)

            logger.info(f"✨ Successfully processed email for user {user_id}")

        except Exception as e:
            logger.error(f"❌ Error processing email for user: {e}")

    def _detect_email_type(self, subject: str, body: str) -> str:
        """Detect the type of job application email"""
        subject_lower = subject.lower()
        body_lower = body.lower()

        # Interview invite
        interview_keywords = ['interview', 'schedule', 'meeting', 'call', 'zoom', 'teams']
        if any(keyword in subject_lower or keyword in body_lower for keyword in interview_keywords):
            return "interview_invite"

        # Job offer
        offer_keywords = ['offer', 'congratulations', 'we are pleased', 'selected', 'hired']
        if any(keyword in subject_lower or keyword in body_lower for keyword in offer_keywords):
            return "offer"

        # Rejection
        rejection_keywords = ['unfortunately', 'not selected', 'regret', 'other candidates', 'rejected']
        if any(keyword in subject_lower or keyword in body_lower for keyword in rejection_keywords):
            return "rejection"

        # General response
        return "general_response"

    async def _handle_interview_invite(self, user_id: str, email_doc: dict):
        """Handle interview invitation email"""
        logger.info(f"📅 Interview invite detected for user {user_id}")

        # Find related application
        application = await self.db.applications.find_one({
            "user_id": user_id,
            "status": {"$in": ["applied", "reviewing"]}
        })

        if application:
            # Update application status
            await self.db.applications.update_one(
                {"_id": application["_id"]},
                {
                    "$set": {
                        "status": "interview",
                        "interview_scheduled_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ Updated application status to 'interview'")

    async def _handle_job_offer(self, user_id: str, email_doc: dict):
        """Handle job offer email"""
        logger.info(f"🎉 Job offer detected for user {user_id}")

        # Find related application
        application = await self.db.applications.find_one({
            "user_id": user_id,
            "status": {"$in": ["applied", "reviewing", "interview"]}
        })

        if application:
            await self.db.applications.update_one(
                {"_id": application["_id"]},
                {
                    "$set": {
                        "status": "offer",
                        "offer_received_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ Updated application status to 'offer'")

    async def _handle_rejection(self, user_id: str, email_doc: dict):
        """Handle rejection email"""
        logger.info(f"😔 Rejection detected for user {user_id}")

        application = await self.db.applications.find_one({
            "user_id": user_id,
            "status": {"$in": ["applied", "reviewing", "interview"]}
        })

        if application:
            await self.db.applications.update_one(
                {"_id": application["_id"]},
                {
                    "$set": {
                        "status": "rejected",
                        "response_received_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ Updated application status to 'rejected'")

    async def _handle_general_response(self, user_id: str, email_doc: dict):
        """Handle general response email"""
        logger.info(f"📨 General response for user {user_id}")

        application = await self.db.applications.find_one({
            "user_id": user_id,
            "status": "applied"
        })

        if application:
            await self.db.applications.update_one(
                {"_id": application["_id"]},
                {
                    "$set": {
                        "status": "reviewing",
                        "response_received_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )


class CustomSMTPHandler:
    """Custom SMTP handler to integrate with JobApplicationEmailHandler"""

    def __init__(self, db):
        self.email_handler = JobApplicationEmailHandler(db)

    async def handle_DATA(self, server, session, envelope):
        return await self.email_handler.handle_DATA(server, session, envelope)


async def start_email_listener():
    """Start the SMTP email listener server"""

    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE]

    # Create handler
    handler = CustomSMTPHandler(db)

    # SMTP server configuration
    smtp_host = getattr(settings, 'SMTP_LISTEN_HOST', '0.0.0.0')
    smtp_port = getattr(settings, 'SMTP_LISTEN_PORT', 8025)

    # Create and start controller
    controller = Controller(
        handler,
        hostname=smtp_host,
        port=smtp_port
    )

    controller.start()

    logger.info(f"🚀 SMTP Email Listener started on {smtp_host}:{smtp_port}")
    logger.info(f"📬 Listening for incoming job application responses...")
    logger.info(f"📊 Connected to MongoDB: {settings.MONGODB_DATABASE}")

    try:
        # Keep server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Stopping SMTP server...")
        controller.stop()
        client.close()


if __name__ == "__main__":
    try:
        asyncio.run(start_email_listener())
    except KeyboardInterrupt:
        logger.info("👋 Email listener stopped")
