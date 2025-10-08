"""
Test Email Forwarding Service
Creates test emails to show on user dashboard
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from bson import ObjectId

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.email_forwarding_service import EmailForwardingService


async def test_email_forwarding():
    """Test email forwarding with sample emails"""
    try:
        db = MongoDB.get_async_db()
        forwarding_service = EmailForwardingService(db)

        print("=" * 80)
        print("📧 EMAIL FORWARDING SERVICE TEST")
        print("=" * 80)
        print()

        # Get test user
        user = await db.users.find_one({"email": "test@example.com"})
        if not user:
            print("❌ Test user not found")
            return

        user_id = str(user["_id"])
        print(f"👤 Test User: {user.get('email')}")
        print(f"   User ID: {user_id}")
        print()

        # Generate forwarding email for user
        forwarding_email = forwarding_service.generate_user_forwarding_email(user_id, user)
        user_real_email = user.get("email")

        # Create forwarding record if not exists
        existing_record = await db.forwarding_emails.find_one({"user_id": ObjectId(user_id)})
        if not existing_record:
            forwarding_record = {
                "user_id": ObjectId(user_id),
                "forwarding_address": forwarding_email,
                "user_real_email": user_real_email,
                "applications_using": [],
                "emails_received_count": 0,
                "last_email_at": None,
                "status": "active",
                "created_at": datetime.utcnow()
            }
            await db.forwarding_emails.insert_one(forwarding_record)

        print(f"📨 Forwarding Email: {forwarding_email}")
        print(f"📮 User Real Email: {user_real_email}")
        print()

        # Get user's latest application
        application = await db.applications.find_one(
            {"user_id": ObjectId(user_id)},
            sort=[("created_at", -1)]
        )

        if not application:
            print("❌ No applications found for user")
            return

        job_title = application.get("job_title", "Software Engineer")
        company = application.get("company", "Tech Company")

        print(f"💼 Latest Application: {job_title} at {company}")
        print()

        # Test 1: Interview Email
        print("=" * 80)
        print("TEST 1: Interview Invitation Email")
        print("=" * 80)

        interview_email = {
            "from": f"recruiter@{company.lower().replace(' ', '')}.com",
            "to": forwarding_email,
            "subject": f"Interview Invitation - {job_title} Position",
            "body": f"""
Dear {user.get('profile', {}).get('first_name', 'Candidate')},

Thank you for applying to the {job_title} position at {company}!

We were impressed with your background and would like to schedule an interview with you.

Interview Details:
- Date: January 20, 2025 at 2:00 PM EST
- Duration: 45 minutes
- Format: Video call via Zoom
- Meeting Link: https://zoom.us/j/123456789

Please confirm your availability by replying to this email.

We look forward to speaking with you!

Best regards,
Hiring Team
{company}
            """,
            "html": "",
            "attachments": []
        }

        # Manually save email (since service uses sync db)
        to_email = interview_email["to"]
        from_email = interview_email["from"]
        subject = interview_email["subject"]
        body_text = interview_email["body"]

        # Detect email type
        email_type = forwarding_service._detect_email_type(subject, body_text)
        parsed_data = forwarding_service._parse_email_content(subject, body_text, email_type)

        # Save email
        email_doc = {
            "application_id": application["_id"],
            "user_id": ObjectId(user_id),
            "from": from_email,
            "to": to_email,
            "subject": subject,
            "body_text": body_text,
            "body_html": "",
            "email_type": email_type,
            "parsed_data": parsed_data,
            "attachments": [],
            "forwarded_to_user": False,
            "received_at": datetime.utcnow()
        }

        result = await db.received_emails.insert_one(email_doc)
        email_doc["_id"] = result.inserted_id
        saved_interview = email_doc

        # Update application status
        await db.applications.update_one(
            {"_id": application["_id"]},
            {
                "$set": {
                    "status": "interview",
                    "company_response_received": True,
                    "company_response_date": datetime.utcnow(),
                    "company_response_type": email_type
                }
            }
        )
        print(f"✅ Interview email saved - ID: {saved_interview['_id']}")
        print(f"   Type detected: {saved_interview['email_type']}")
        print(f"   Parsed data: {saved_interview.get('parsed_data', {})}")
        print()

        # Test 2: Rejection Email
        print("=" * 80)
        print("TEST 2: Rejection Email")
        print("=" * 80)

        # Get another application
        another_app = await db.applications.find_one(
            {"user_id": ObjectId(user_id), "_id": {"$ne": application["_id"]}},
            sort=[("created_at", -1)]
        )

        if another_app:
            rejection_email = {
                "from": "hiring@anothercompany.com",
                "to": forwarding_email,
                "subject": "Re: Your Application",
                "body": f"""
Dear {user.get('profile', {}).get('first_name', 'Candidate')},

Thank you for your interest in the position at our company.

Unfortunately, we have decided to move forward with other candidates whose qualifications more closely match our current needs.

We appreciate the time you invested in the application process and wish you the best in your job search.

Best regards,
Hiring Team
                """,
                "html": "",
                "attachments": []
            }

            saved_rejection = forwarding_service.save_received_email(rejection_email)
            print(f"✅ Rejection email saved - ID: {saved_rejection['_id']}")
            print(f"   Type detected: {saved_rejection['email_type']}")
            print()

        # Test 3: Job Offer Email
        print("=" * 80)
        print("TEST 3: Job Offer Email")
        print("=" * 80)

        offer_email = {
            "from": f"offers@{company.lower().replace(' ', '')}.com",
            "to": forwarding_email,
            "subject": f"Job Offer - {job_title}",
            "body": f"""
Dear {user.get('profile', {}).get('first_name', 'Candidate')},

Congratulations! We are pleased to offer you the position of {job_title} at {company}.

Offer Details:
- Position: {job_title}
- Salary: $150,000 per year
- Start Date: February 1, 2025
- Benefits: Health insurance, 401k, unlimited PTO

Please review the attached offer letter and let us know your decision within 5 business days.

We're excited to have you join our team!

Best regards,
HR Team
{company}
            """,
            "html": "",
            "attachments": []
        }

        saved_offer = forwarding_service.save_received_email(offer_email)
        print(f"✅ Offer email saved - ID: {saved_offer['_id']}")
        print(f"   Type detected: {saved_offer['email_type']}")
        print(f"   Parsed data: {saved_offer.get('parsed_data', {})}")
        print()

        # Test 4: Info Request Email
        print("=" * 80)
        print("TEST 4: Information Request Email")
        print("=" * 80)

        info_email = {
            "from": "hr@techstartup.com",
            "to": forwarding_email,
            "subject": "Additional Information Required",
            "body": f"""
Dear {user.get('profile', {}).get('first_name', 'Candidate')},

Thank you for your application to our company.

We would like to request some additional information to complete your application:

1. Professional references (3)
2. Portfolio or work samples
3. Salary expectations

Please provide these details at your earliest convenience.

Thank you,
HR Team
            """,
            "html": "",
            "attachments": []
        }

        saved_info = forwarding_service.save_received_email(info_email)
        print(f"✅ Info request email saved - ID: {saved_info['_id']}")
        print(f"   Type detected: {saved_info['email_type']}")
        print()

        # Summary
        print("=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)

        # Get user's inbox
        inbox = forwarding_service.get_user_inbox(user_id)
        print(f"📬 Total emails in inbox: {len(inbox)}")
        print()

        # Count by type
        email_types = {}
        for email in inbox:
            email_type = email.get("email_type", "general")
            email_types[email_type] = email_types.get(email_type, 0) + 1

        print("📊 Emails by type:")
        for email_type, count in email_types.items():
            print(f"   • {email_type}: {count}")
        print()

        # Check application updates
        updated_app = await db.applications.find_one({"_id": application["_id"]})
        print(f"📝 Application Status Updates:")
        print(f"   • Status: {updated_app.get('status', 'pending')}")
        print(f"   • Company Response: {updated_app.get('company_response_received', False)}")
        print(f"   • Response Type: {updated_app.get('company_response_type', 'none')}")
        print()

        print("=" * 80)
        print("✅ EMAIL FORWARDING TEST COMPLETE!")
        print("=" * 80)
        print()
        print("💡 Next Steps:")
        print("   1. Check the dashboard for received emails")
        print("   2. Verify application status updates")
        print("   3. Test email forwarding to user's real email")
        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n📧 Testing Email Forwarding Service...\n")
    asyncio.run(test_email_forwarding())
