"""
Simple Email Test - Create test emails for dashboard
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from bson import ObjectId

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB


async def create_test_emails():
    """Create test emails to display on dashboard"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 80)
        print("📧 CREATE TEST EMAILS FOR DASHBOARD")
        print("=" * 80)
        print()

        # Get user with applications
        app = await db.applications.find_one({})
        if not app:
            print("❌ No applications found in database")
            return

        user = await db.users.find_one({"_id": app.get("user_id")})
        if not user:
            print("❌ Test user not found")
            return

        user_id = user["_id"]
        user_email = user.get("email")
        first_name = user.get("profile", {}).get("first_name", "John")

        print(f"👤 User: {user_email}")
        print(f"   Name: {first_name}")
        print()

        # Get user's applications
        applications = await db.applications.find({"user_id": user_id}).to_list(length=3)

        if not applications:
            print("❌ No applications found")
            return

        print(f"📝 Found {len(applications)} applications")
        print()

        # Test Email 1: Interview Invitation
        print("Creating Test Email 1: Interview Invitation...")
        app1 = applications[0]
        email1 = {
            "application_id": app1["_id"],
            "user_id": user_id,
            "from": f"recruiter@{app1.get('company', 'company').lower().replace(' ', '')}.com",
            "to": user_email,
            "subject": f"Interview Invitation - {app1.get('job_title', 'Position')}",
            "body_text": f"""Dear {first_name},

Thank you for applying to the {app1.get('job_title')} position at {app1.get('company')}!

We were impressed with your background and would like to schedule an interview.

Interview Details:
- Date: January 20, 2025 at 2:00 PM EST
- Duration: 45 minutes
- Format: Video call via Zoom
- Meeting Link: https://zoom.us/j/123456789

Please confirm your availability.

Best regards,
Hiring Team
{app1.get('company')}
            """,
            "body_html": "",
            "email_type": "interview",
            "parsed_data": {
                "interview_date_text": "January 20, 2025",
                "meeting_link": "https://zoom.us/j/123456789"
            },
            "attachments": [],
            "forwarded_to_user": False,
            "received_at": datetime.utcnow()
        }

        result1 = await db.received_emails.insert_one(email1)
        print(f"✅ Email 1 saved - ID: {result1.inserted_id}")

        # Update application status
        await db.applications.update_one(
            {"_id": app1["_id"]},
            {
                "$set": {
                    "status": "interview",
                    "company_response_received": True,
                    "company_response_date": datetime.utcnow(),
                    "company_response_type": "interview"
                }
            }
        )
        print()

        # Test Email 2: Job Offer
        if len(applications) > 1:
            print("Creating Test Email 2: Job Offer...")
            app2 = applications[1]
            email2 = {
                "application_id": app2["_id"],
                "user_id": user_id,
                "from": f"offers@{app2.get('company', 'company').lower().replace(' ', '')}.com",
                "to": user_email,
                "subject": f"Job Offer - {app2.get('job_title', 'Position')}",
                "body_text": f"""Dear {first_name},

Congratulations! We are pleased to offer you the position of {app2.get('job_title')} at {app2.get('company')}.

Offer Details:
- Position: {app2.get('job_title')}
- Salary: $150,000 per year
- Start Date: February 1, 2025
- Benefits: Health insurance, 401k, unlimited PTO

Please review and respond within 5 business days.

Best regards,
HR Team
{app2.get('company')}
                """,
                "body_html": "",
                "email_type": "offer",
                "parsed_data": {
                    "salary_mentioned": "$150,000",
                    "start_date": "February 1, 2025"
                },
                "attachments": [],
                "forwarded_to_user": False,
                "received_at": datetime.utcnow()
            }

            result2 = await db.received_emails.insert_one(email2)
            print(f"✅ Email 2 saved - ID: {result2.inserted_id}")

            # Update application status
            await db.applications.update_one(
                {"_id": app2["_id"]},
                {
                    "$set": {
                        "status": "offer",
                        "company_response_received": True,
                        "company_response_date": datetime.utcnow(),
                        "company_response_type": "offer"
                    }
                }
            )
            print()

        # Test Email 3: Rejection
        if len(applications) > 2:
            print("Creating Test Email 3: Rejection...")
            app3 = applications[2]
            email3 = {
                "application_id": app3["_id"],
                "user_id": user_id,
                "from": f"hiring@{app3.get('company', 'company').lower().replace(' ', '')}.com",
                "to": user_email,
                "subject": "Re: Your Application",
                "body_text": f"""Dear {first_name},

Thank you for your interest in the {app3.get('job_title')} position.

Unfortunately, we have decided to move forward with other candidates whose qualifications more closely match our current needs.

We appreciate your time and wish you the best.

Best regards,
Hiring Team
                """,
                "body_html": "",
                "email_type": "rejection",
                "parsed_data": {},
                "attachments": [],
                "forwarded_to_user": False,
                "received_at": datetime.utcnow()
            }

            result3 = await db.received_emails.insert_one(email3)
            print(f"✅ Email 3 saved - ID: {result3.inserted_id}")

            # Update application status
            await db.applications.update_one(
                {"_id": app3["_id"]},
                {
                    "$set": {
                        "status": "rejected",
                        "company_response_received": True,
                        "company_response_date": datetime.utcnow(),
                        "company_response_type": "rejection"
                    }
                }
            )
            print()

        # Summary
        print("=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)

        # Count emails
        total_emails = await db.received_emails.count_documents({"user_id": user_id})
        print(f"📬 Total emails in inbox: {total_emails}")

        # Count by type
        interview_count = await db.received_emails.count_documents({"user_id": user_id, "email_type": "interview"})
        offer_count = await db.received_emails.count_documents({"user_id": user_id, "email_type": "offer"})
        rejection_count = await db.received_emails.count_documents({"user_id": user_id, "email_type": "rejection"})

        print(f"   • Interview: {interview_count}")
        print(f"   • Offer: {offer_count}")
        print(f"   • Rejection: {rejection_count}")
        print()

        # Check updated applications
        updated_apps = await db.applications.count_documents({"user_id": user_id, "company_response_received": True})
        print(f"📝 Applications with responses: {updated_apps}")
        print()

        print("=" * 80)
        print("✅ TEST EMAILS CREATED SUCCESSFULLY!")
        print("=" * 80)
        print()
        print("💡 Next Steps:")
        print("   1. Check the dashboard at http://localhost:3000")
        print("   2. Navigate to the 'Inbox' or 'Messages' section")
        print("   3. Verify emails are displayed correctly")
        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n📧 Creating test emails for dashboard...\n")
    asyncio.run(create_test_emails())
