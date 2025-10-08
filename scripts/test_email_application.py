"""
Test Email Application System
Tests the complete flow of:
1. Creating unique forwarding email for user
2. Sending actual job application via email
3. Tracking the application
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.job_application_email_service import send_job_application_email
from app.services.email_forwarding_service import EmailForwardingService
from bson import ObjectId


async def test_email_application_system():
    """Test the complete email application flow"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 80)
        print("🧪 TESTING EMAIL APPLICATION SYSTEM")
        print("=" * 80)
        print()

        # Step 1: Get active user
        print("📋 Step 1: Getting active user...")
        user = await db.users.find_one({
            "preferences.search_active": True
        })

        if not user:
            print("❌ No active user found!")
            return

        user_id = str(user["_id"])
        user_email = user.get("email", "unknown")
        print(f"   ✅ Found user: {user_email}")
        print(f"   🆔 User ID: {user_id}")
        print()

        # Step 2: Create/Get forwarding email
        print("📋 Step 2: Creating unique forwarding email for user...")
        forwarding_service = EmailForwardingService(MongoDB.get_db())

        forwarding_email_doc = forwarding_service.create_user_forwarding_email(user_id)
        forwarding_email = forwarding_email_doc['forwarding_address']

        print(f"   ✅ Forwarding Email: {forwarding_email}")
        print(f"   📧 Real Email: {forwarding_email_doc['user_real_email']}")
        print(f"   📊 Status: {forwarding_email_doc['status']}")
        print()

        # Step 3: Get a test job with email application
        print("📋 Step 3: Finding a job with email application method...")

        # First, try to find a job with apply_email field
        test_job = await db.jobs.find_one({
            "is_active": True,
            "$or": [
                {"apply_email": {"$exists": True, "$ne": ""}},
                {"application_email": {"$exists": True, "$ne": ""}},
                {"contact_email": {"$exists": True, "$ne": ""}}
            ]
        })

        if not test_job:
            # If no job with email, create a test job entry
            print("   ⚠️  No jobs with email found, creating test job...")
            test_job = await db.jobs.find_one({"is_active": True})

            if test_job:
                # Add a test email to the job
                test_job['apply_email'] = "hiring@example.com"  # Replace with actual test email
                job_id = str(test_job["_id"])

                await db.jobs.update_one(
                    {"_id": test_job["_id"]},
                    {"$set": {"apply_email": "hiring@example.com"}}
                )
                print(f"   ✅ Added test email to job: {test_job.get('title')}")
            else:
                print("   ❌ No jobs found in database!")
                return
        else:
            job_id = str(test_job["_id"])

        print(f"   📄 Job: {test_job.get('title', 'Unknown')}")
        print(f"   🏢 Company: {test_job.get('company', 'Unknown')}")
        apply_email = (test_job.get('apply_email') or
                      test_job.get('application_email') or
                      test_job.get('contact_email'))
        print(f"   📧 Apply Email: {apply_email}")
        print()

        # Step 4: Get user's resume
        print("📋 Step 4: Getting user's resume...")
        resume = await db.resumes.find_one({
            "user_id": user_id,
            "is_primary": True
        })

        resume_path = None
        if resume:
            resume_path = resume.get("file_path")
            print(f"   ✅ Resume found: {resume_path}")
        else:
            print(f"   ⚠️  No resume found - will send without attachment")
        print()

        # Step 5: Test sending job application email
        print("📋 Step 5: Sending job application email...")
        print(f"   🔄 This will send an actual email to: {apply_email}")
        print(f"   📧 Reply-To will be set to: {forwarding_email}")
        print()

        # Prepare job data with proper structure
        job_data = {
            "id": job_id,
            "title": test_job.get("title", "Software Engineer"),
            "company": test_job.get("company", "Tech Company"),
            "apply_email": apply_email,
            "location": test_job.get("location", "Remote"),
            "description": test_job.get("description", "")
        }

        # Create a test cover letter
        cover_letter = """Dear Hiring Manager,

I am writing to express my interest in this position. With my background in software development and passion for technology, I believe I would be a great fit for your team.

I have experience working with modern technologies and have a proven track record of delivering high-quality solutions.

I look forward to the opportunity to discuss how I can contribute to your organization.

Best regards"""

        # Send the email
        result = await send_job_application_email(
            db=db,
            user_id=user_id,
            job_data=job_data,
            resume_path=resume_path,
            cover_letter=cover_letter
        )

        print("📋 Step 6: Email Sending Result")
        print(f"   ✅ Success: {result.get('success')}")

        if result.get('success'):
            print(f"   📧 Sent to: {result.get('recipient')}")
            print(f"   🔄 Reply-to: {result.get('forwarding_email')}")
            print(f"   📅 Sent at: {result.get('sent_at')}")
            print(f"   💌 Method: {result.get('method')}")
        else:
            print(f"   ❌ Error: {result.get('error')}")
        print()

        # Step 7: Verify database records
        print("📋 Step 7: Verifying database records...")

        # Check sent_emails collection
        sent_email_record = await db.sent_emails.find_one({
            "user_id": ObjectId(user_id),
            "job_id": job_id
        })

        if sent_email_record:
            print(f"   ✅ Sent email record created")
            print(f"   📧 To: {sent_email_record.get('sent_to')}")
            print(f"   🔄 Forwarding: {sent_email_record.get('reply_to_forwarding')}")
        else:
            print(f"   ⚠️  No sent email record found")
        print()

        # Check forwarding_emails collection
        forwarding_email_record = await db.forwarding_emails.find_one({
            "user_id": ObjectId(user_id)
        })

        if forwarding_email_record:
            print(f"   ✅ Forwarding email record exists")
            print(f"   📧 Address: {forwarding_email_record.get('forwarding_address')}")
            print(f"   📊 Applications using: {len(forwarding_email_record.get('applications_using', []))}")
        print()

        print("=" * 80)
        print("✅ EMAIL APPLICATION SYSTEM TEST COMPLETE!")
        print("=" * 80)
        print()
        print("📝 Summary:")
        print(f"   • Unique forwarding email created: {forwarding_email}")
        print(f"   • Application email sent to: {apply_email}")
        print(f"   • Replies will be forwarded to: {user_email}")
        print(f"   • Email sent successfully: {result.get('success')}")
        print()
        print("💡 Next Steps:")
        print("   1. Check if email was received at the job application email")
        print("   2. When company replies, it will go to the forwarding email")
        print("   3. System will parse and forward replies to user's real email")
        print("   4. Application status will be updated automatically")
        print()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_email_application_system())
