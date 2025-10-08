"""
Fill User Profile Script
Populates user onboarding data with realistic information for testing
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from bson import ObjectId


async def fill_user_profile():
    """Fill user profile with realistic data"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 60)
        print("📝 Filling User Profile with Realistic Data")
        print("=" * 60)
        print()

        # Get active user
        active_users = await db.users.find({
            "preferences.search_active": True
        }).to_list(length=None)

        if not active_users:
            print("❌ No active users found!")
            return

        user = active_users[0]
        user_id = user["_id"]
        user_email = user.get("email", "unknown")

        print(f"👤 Updating user: {user_email}")
        print(f"🆔 User ID: {user_id}")
        print()

        # Prepare comprehensive onboarding data
        onboarding_data = {
            # Job preferences
            "job_titles": [
                "Software Engineer",
                "Full Stack Developer",
                "Backend Developer",
                "Python Developer"
            ],

            # Experience
            "years_of_experience": 5,
            "education_level": "Bachelor's Degree",

            # Salary expectations
            "salary_min": 80000,
            "salary_max": 150000,
            "salary_currency": "USD",

            # Location preferences
            "preferred_locations": [
                "United States",
                "Remote",
                "San Francisco",
                "New York",
                "Austin"
            ],
            "relocation_willing": True,
            "work_location_preference": "remote",  # remote, onsite, hybrid, flexible

            # Work types
            "work_types": [
                "full-time",
                "contract"
            ],

            # Industries
            "industries": [
                "technology",
                "software",
                "fintech",
                "saas",
                "startup"
            ],

            # Skills
            "skills": [
                "Python",
                "JavaScript",
                "React",
                "Node.js",
                "FastAPI",
                "MongoDB",
                "PostgreSQL",
                "Docker",
                "Kubernetes",
                "AWS",
                "Git",
                "REST API",
                "GraphQL",
                "TypeScript",
                "CI/CD"
            ],

            # Additional preferences
            "excluded_companies": [],
            "visa_sponsorship_needed": False,
            "work_authorization": "authorized",  # authorized, need_sponsorship

            # Completion tracking
            "completed": True,
            "completed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Update preferences
        preferences_update = {
            "search_active": True,
            "match_threshold": "good-fit",  # Changed from "top" to "good-fit" (70+ score)
            "approval_mode": "approval",
            "auto_apply_delay": 24,
            "ai_features": {
                "cover_letters": True,
                "resume_optimization": True,
                "interview_prep": True
            }
        }

        # Update user in database
        result = await db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "onboarding_data": onboarding_data,
                    "preferences": preferences_update,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count > 0:
            print("✅ User profile updated successfully!")
            print()
            print("📋 Updated Data:")
            print(f"  Job Titles: {', '.join(onboarding_data['job_titles'][:3])}...")
            print(f"  Experience: {onboarding_data['years_of_experience']} years")
            print(f"  Salary Range: ${onboarding_data['salary_min']:,} - ${onboarding_data['salary_max']:,}")
            print(f"  Locations: {', '.join(onboarding_data['preferred_locations'][:3])}...")
            print(f"  Skills: {len(onboarding_data['skills'])} skills")
            print(f"  Match Threshold: {preferences_update['match_threshold']}")
            print()
            print("=" * 60)
            print("✅ Ready for job matching!")
            print("=" * 60)
        else:
            print("⚠️  No changes made to user profile")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(fill_user_profile())
