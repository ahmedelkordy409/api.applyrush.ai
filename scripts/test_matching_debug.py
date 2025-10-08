"""
Test Matching Debug Script
Runs matching with detailed logging
"""

import asyncio
import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.job_matcher_service import job_matcher_service


async def test_matching():
    """Test matching with debug output"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 60)
        print("🔍 Testing Job Matching with Debug Output")
        print("=" * 60)
        print()

        # Get active users
        active_users = await db.users.find({
            "preferences.search_active": True
        }).to_list(length=None)

        print(f"👥 Found {len(active_users)} active users")

        if not active_users:
            print("❌ No active users found!")
            return

        user = active_users[0]
        user_id = str(user["_id"])
        print(f"\n📧 Testing with user: {user.get('email', 'unknown')}")
        print(f"🆔 User ID: {user_id}")

        # Print user preferences
        preferences = user.get("preferences", {})
        onboarding = user.get("onboarding_data", {})

        print(f"\n📋 User Preferences:")
        print(f"  Match Threshold: {preferences.get('match_threshold', 'N/A')}")
        print(f"  Search Active: {preferences.get('search_active', False)}")

        print(f"\n📋 Onboarding Data:")
        print(f"  Job Titles: {onboarding.get('job_titles', [])}")
        print(f"  Years Experience: {onboarding.get('years_of_experience', 'N/A')}")
        print(f"  Salary Range: ${onboarding.get('salary_min', 0):,} - ${onboarding.get('salary_max', 0):,}")
        print(f"  Locations: {onboarding.get('preferred_locations', [])}")
        print(f"  Work Types: {onboarding.get('work_types', [])}")
        print(f"  Industries: {onboarding.get('industries', [])}")
        print(f"  Skills: {onboarding.get('skills', [])}")

        # Get jobs
        jobs = await db.jobs.find({"is_active": True}).limit(10).to_list(length=10)
        print(f"\n📋 Testing with {len(jobs)} sample jobs")

        # Test matching
        print(f"\n🎯 Testing Match Scores:")
        print("-" * 60)

        match_count = 0
        for i, job in enumerate(jobs, 1):
            print(f"\n{i}. {job.get('title', 'Unknown')} - {job.get('company', 'Unknown')}")

            # Check filters
            passes_filters, filter_reason = job_matcher_service.passes_user_filters(user, job)
            if not passes_filters:
                print(f"   🚫 Filtered out: {filter_reason}")
                continue

            # Calculate score
            match_result = await job_matcher_service.calculate_match_score(user, job)
            score = match_result["score"]
            reasons = match_result["reasons"]
            breakdown = match_result.get("breakdown", {})

            print(f"   Score: {score}/100")
            print(f"   Breakdown: {breakdown}")
            print(f"   Reasons: {reasons[:3] if reasons else []}")

            if score >= 70:
                match_count += 1
                print(f"   ✅ MATCH!")

        print(f"\n" + "=" * 60)
        print(f"📊 Summary: {match_count} matches out of {len(jobs)} jobs tested")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_matching())
