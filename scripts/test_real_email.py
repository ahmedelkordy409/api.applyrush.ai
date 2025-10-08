"""
Test Real Email Sending with Local SMTP Server
Tests the complete email flow including sending job applications
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.job_application_email_service import JobApplicationEmailService


async def test_real_email_sending():
    """Test sending real emails via local SMTP server"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 80)
        print("📧 REAL EMAIL SENDING TEST")
        print("=" * 80)
        print()
        print("✅ Local SMTP Server: localhost:1025")
        print("✅ SMTP Server will print received emails to /tmp/smtp_debug.log")
        print()

        # Get user with applications
        user = await db.users.find_one({"email": "kobew70224@ampdial.com"})
        if not user:
            print("❌ User not found")
            return

        app = await db.applications.find_one({"user_id": user["_id"], "status": "matched"})
        if not app:
            print("❌ No matched applications found")
            return

        user_id = str(user["_id"])
        user_email = user.get("email", "test@example.com")
        first_name = user.get("profile", {}).get("first_name", "John")
        last_name = user.get("profile", {}).get("last_name", "Doe")

        print(f"👤 Test User:")
        print(f"   Name: {first_name} {last_name}")
        print(f"   Email: {user_email}")
        print(f"   User ID: {user_id}")
        print()

        # Get job details from application
        job_data = {
            "id": str(app.get("job_id", "test-job-123")),
            "title": app.get("job_title", "Senior Software Engineer"),
            "company": app.get("company", "TechCorp Inc."),
            "location": app.get("location", "Remote"),
            "apply_email": "hiring@techcorp.com",  # Test email
            "description": "We are looking for a talented software engineer...",
        }

        print(f"💼 Job Details:")
        print(f"   Title: {job_data['title']}")
        print(f"   Company: {job_data['company']}")
        print(f"   Application Email: {job_data['apply_email']}")
        print()

        # Create cover letter
        cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_data['title']} position at {job_data['company']}.

With my extensive background in software development and my passion for building scalable solutions, I believe I would be an excellent addition to your team.

I am particularly excited about this opportunity because of {job_data['company']}'s innovative approach to technology and your commitment to excellence.

I look forward to discussing how my skills and experience align with your needs.

Best regards,
{first_name} {last_name}"""

        # Initialize email service with LOCAL SMTP settings
        email_service = JobApplicationEmailService(db)

        # Override SMTP settings to use local server
        email_service.smtp_server = "localhost"
        email_service.smtp_port = 1025
        email_service.smtp_username = ""  # No auth for local server
        email_service.smtp_password = ""
        email_service.from_email = f"{first_name.lower()}.{last_name.lower()}@applyrush.ai"

        print("=" * 80)
        print("📤 SENDING APPLICATION EMAIL...")
        print("=" * 80)
        print()

        # Send application email
        result = await email_service.apply_via_email(
            user_id=user_id,
            job_data=job_data,
            resume_path=None,  # No resume for this test
            cover_letter=cover_letter
        )

        if result.get("success"):
            print("✅ APPLICATION EMAIL SENT SUCCESSFULLY!")
            print()
            print(f"📧 Email Details:")
            print(f"   Method: {result.get('method')}")
            print(f"   To: {result.get('recipient')}")
            print(f"   Reply-To: {result.get('forwarding_email')}")
            print(f"   Sent At: {result.get('sent_at')}")
            print()
        else:
            print(f"❌ FAILED TO SEND EMAIL: {result.get('error')}")
            print()

        # Check SMTP debug log
        print("=" * 80)
        print("📝 SMTP SERVER LOG (last 50 lines)")
        print("=" * 80)
        print()

        import subprocess
        try:
            log_output = subprocess.check_output(
                ["tail", "-n", "50", "/tmp/smtp_debug.log"],
                stderr=subprocess.STDOUT,
                text=True
            )
            print(log_output)
        except:
            print("⚠️  No SMTP log found yet")
        print()

        # Test 2: Simulate receiving company response
        print("=" * 80)
        print("📨 SIMULATING COMPANY RESPONSE EMAIL")
        print("=" * 80)
        print()

        # Create a response email
        response_email = {
            "application_id": app["_id"],
            "user_id": user["_id"],
            "from": "recruiter@techcorp.com",
            "to": user_email,
            "subject": f"Interview Request - {job_data['title']}",
            "body_text": f"""Dear {first_name},

Thank you for your application to the {job_data['title']} position at {job_data['company']}!

We were very impressed with your background and would like to schedule an interview.

Interview Details:
- Date: January 22, 2025 at 3:00 PM EST
- Duration: 1 hour
- Format: Video call via Zoom
- Meeting Link: https://zoom.us/j/987654321

Please reply to confirm your availability.

Best regards,
Sarah Johnson
Senior Technical Recruiter
{job_data['company']}
            """,
            "body_html": "",
            "email_type": "interview",
            "parsed_data": {
                "interview_date_text": "January 22, 2025",
                "meeting_link": "https://zoom.us/j/987654321"
            },
            "attachments": [],
            "forwarded_to_user": False,
            "received_at": datetime.utcnow()
        }

        # Save received email
        result = await db.received_emails.insert_one(response_email)
        print(f"✅ Company response email saved - ID: {result.inserted_id}")

        # Update application status
        await db.applications.update_one(
            {"_id": app["_id"]},
            {
                "$set": {
                    "status": "interview",
                    "company_response_received": True,
                    "company_response_date": datetime.utcnow(),
                    "company_response_type": "interview"
                }
            }
        )
        print(f"✅ Application status updated to 'interview'")
        print()

        # Summary
        print("=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        print()

        # Check sent emails
        sent_count = await db.sent_emails.count_documents({"user_id": user["_id"]})
        print(f"📤 Sent Emails: {sent_count}")

        # Check received emails
        received_count = await db.received_emails.count_documents({"user_id": user["_id"]})
        print(f"📥 Received Emails: {received_count}")

        # Check application status
        updated_app = await db.applications.find_one({"_id": app["_id"]})
        print(f"📝 Application Status: {updated_app.get('status')}")
        print(f"📧 Company Response: {updated_app.get('company_response_received', False)}")
        print()

        print("=" * 80)
        print("✅ REAL EMAIL TEST COMPLETE!")
        print("=" * 80)
        print()
        print("💡 Next Steps:")
        print("   1. Check /tmp/smtp_debug.log for full email content")
        print("   2. View sent emails in the dashboard")
        print("   3. View received emails/responses in the inbox")
        print("   4. The application status should show 'interview'")
        print()
        print("📍 Dashboard: http://localhost:3000")
        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n📧 Testing Real Email Sending with Local SMTP...\n")
    asyncio.run(test_real_email_sending())
