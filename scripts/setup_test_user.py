"""
Setup Test User with Complete Profile and Applications
Creates realistic test data for kobew70224@ampdial.com
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from bson import ObjectId

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB


async def setup_test_user():
    """Setup complete test user with profile and applications"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 80)
        print("👤 SETTING UP TEST USER")
        print("=" * 80)
        print()

        user_email = "kobew70224@ampdial.com"

        # Get user
        user = await db.users.find_one({"email": user_email})
        if not user:
            print(f"❌ User {user_email} not found")
            return

        user_id = user["_id"]
        print(f"✅ User found: {user_email}")
        print(f"   User ID: {user_id}")
        print()

        # Update user profile
        print("📝 Updating user profile...")
        profile_update = {
            "profile": {
                "first_name": "Ahmed",
                "last_name": "Elkordy",
                "phone": "+1 (555) 123-4567",
                "location": "San Francisco, CA",
                "linkedin_url": "https://linkedin.com/in/ahmedelkordy",
                "github_url": "https://github.com/ahmedelkordy",
                "portfolio_url": "https://ahmedelkordy.dev",
                "bio": "Full-stack software engineer with 5+ years of experience building scalable web applications. Passionate about AI and automation.",
                "skills": ["Python", "JavaScript", "React", "Node.js", "FastAPI", "MongoDB", "AWS", "Docker"],
                "experience_years": 5,
                "education": "BS in Computer Science"
            },
            "preferences": {
                "desired_roles": ["Software Engineer", "Full Stack Developer", "Backend Engineer"],
                "desired_locations": ["Remote", "San Francisco, CA", "New York, NY"],
                "desired_salary_min": 120000,
                "desired_salary_max": 180000,
                "work_type": ["remote", "hybrid"],
                "job_type": ["full-time"],
                "auto_apply_enabled": True,
                "match_threshold": "good-fit"
            },
            "search_settings": {
                "job_titles": ["Software Engineer", "Full Stack Developer", "Backend Engineer", "Python Developer"],
                "locations": ["Remote", "San Francisco, CA", "United States"],
                "remote_only": False,
                "keywords": ["python", "fastapi", "react", "mongodb", "aws"],
                "exclude_keywords": ["senior manager", "director"],
                "min_salary": 120000,
                "employment_types": ["FULLTIME"]
            }
        }

        await db.users.update_one(
            {"_id": user_id},
            {"$set": profile_update}
        )
        print("✅ Profile updated")
        print()

        # Get some jobs from database
        print("🔍 Finding suitable jobs for user...")
        jobs = await db.jobs.find({"is_active": True}).limit(5).to_list(length=5)

        if not jobs:
            print("❌ No jobs found in database")
            return

        print(f"✅ Found {len(jobs)} jobs")
        print()

        # Create applications for the user
        print("📝 Creating test applications...")
        created_apps = 0

        for i, job in enumerate(jobs, 1):
            # Create different statuses for testing
            statuses = ["matched", "applied", "interview", "offer", "rejected"]
            status = statuses[i % len(statuses)]

            application = {
                "user_id": user_id,
                "job_id": job["_id"],
                "job": {
                    "id": str(job["_id"]),
                    "title": job.get("title", "Software Engineer"),
                    "company": job.get("company", "Tech Company"),
                    "location": job.get("location", "Remote"),
                    "description": job.get("description", ""),
                    "salary_min": job.get("salary_min"),
                    "salary_max": job.get("salary_max"),
                    "apply_url": job.get("apply_url", ""),
                    "remote": job.get("remote", False)
                },
                "job_title": job.get("title", "Software Engineer"),
                "company": job.get("company", "Tech Company"),
                "location": job.get("location", "Remote"),
                "status": status,
                "match_score": 85 - (i * 5),  # Decreasing scores
                "match_details": {
                    "title_match": 90,
                    "skills_match": 85,
                    "location_match": 95,
                    "salary_match": 80,
                    "overall_score": 85 - (i * 5)
                },
                "is_approved": status in ["applied", "interview", "offer"],
                "is_auto_applied": status in ["applied", "interview"],
                "applied_at": datetime.utcnow() if status != "matched" else None,
                "company_response_received": status in ["interview", "offer", "rejected"],
                "company_response_type": status if status in ["interview", "offer", "rejected"] else None,
                "company_response_date": datetime.utcnow() if status in ["interview", "offer", "rejected"] else None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await db.applications.insert_one(application)
            created_apps += 1
            print(f"   ✅ Application {i}: {job.get('title')} at {job.get('company')} - Status: {status}")

        print()
        print(f"✅ Created {created_apps} applications")
        print()

        # Summary
        print("=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print()
        print(f"👤 User: {user_email}")
        print(f"📝 Profile: Complete")
        print(f"📋 Applications: {created_apps}")
        print()

        # Count by status
        for status in ["matched", "applied", "interview", "offer", "rejected"]:
            count = await db.applications.count_documents({"user_id": user_id, "status": status})
            print(f"   • {status}: {count}")
        print()

        print("=" * 80)
        print("✅ TEST USER SETUP COMPLETE!")
        print("=" * 80)
        print()
        print("💡 You can now:")
        print("   1. Login as kobew70224@ampdial.com")
        print("   2. View applications on the dashboard")
        print("   3. Test auto-apply functionality")
        print("   4. Test email sending")
        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n👤 Setting up test user...\n")
    asyncio.run(setup_test_user())
