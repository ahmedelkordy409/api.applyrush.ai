"""
Test Find Matches API
Tests the find_matches endpoint directly
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.job_matcher_service import job_matcher_service
from bson import ObjectId
from datetime import datetime, timedelta


async def test_find_matches_api():
    """Test the find_matches logic directly"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 60)
        print("🔍 Testing Find Matches API Logic")
        print("=" * 60)
        print()

        # Get active user
        user = await db.users.find_one({
            "preferences.search_active": True
        })

        if not user:
            print("❌ No active user found!")
            return

        user_id = str(user["_id"])
        print(f"👤 User: {user.get('email', 'unknown')}")
        print(f"🆔 User ID: {user_id}")
        print()

        # Get user preferences
        preferences = user.get("preferences", {})
        match_threshold = preferences.get("match_threshold", "good-fit")

        # Convert match threshold to score
        threshold_map = {
            "open": 60,
            "good-fit": 70,
            "top": 85
        }
        min_score = threshold_map.get(match_threshold, 70)

        print(f"📊 Match threshold: {match_threshold} (min score: {min_score})")
        print()

        # Get active jobs
        jobs = await db.jobs.find({"is_active": True}).limit(100).to_list(length=100)
        print(f"📋 Found {len(jobs)} active jobs")
        print()

        # Match jobs
        matched_count = 0
        skipped_existing = 0
        filtered_out = 0
        low_score_count = 0

        print("🎯 Matching jobs...")
        print("-" * 60)

        for job in jobs:
            job_id = str(job["_id"])

            # Check if job already exists
            existing_application = await db.applications.find_one({
                "user_id": user_id,
                "job_id": job_id
            })

            if existing_application:
                skipped_existing += 1
                continue

            # Check filters
            passes_filters, filter_reason = job_matcher_service.passes_user_filters(user, job)
            if not passes_filters:
                filtered_out += 1
                continue

            # Calculate match score
            match_result = await job_matcher_service.calculate_match_score(user, job)
            match_score = match_result["score"]
            match_reasons = match_result["reasons"]

            if match_score >= min_score:
                # Prepare job data
                job_data = {
                    "id": job_id,
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "location": job.get("location", ""),
                    "salary_min": job.get("salary_min"),
                    "salary_max": job.get("salary_max"),
                    "salary_currency": job.get("salary_currency", "USD"),
                    "description": job.get("description", ""),
                    "requirements": job.get("requirements", []),
                    "benefits": job.get("benefits", []),
                    "job_type": job.get("job_type", "Full-time"),
                    "remote": job.get("remote", False),
                    "date_posted": job.get("date_posted"),
                    "apply_url": job.get("apply_url", ""),
                    "source": job.get("source", "")
                }

                # Create application entry
                application = {
                    "user_id": user_id,
                    "job_id": job_id,
                    "job": job_data,
                    "status": "matched",
                    "match_score": match_score,
                    "match_reasons": match_reasons,
                    "match_breakdown": match_result.get("breakdown", {}),
                    "source": "auto_match",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }

                # Insert into applications
                await db.applications.insert_one(application)
                matched_count += 1

                print(f"✅ {matched_count}. {job.get('title', 'Unknown')} - Score: {match_score}")

                if matched_count >= 10:
                    print(f"\n🎯 Reached limit of 10 matches")
                    break
            else:
                low_score_count += 1

        print()
        print("=" * 60)
        print("📊 Matching Summary:")
        print(f"   ✅ Matched: {matched_count}")
        print(f"   🔄 Already exists: {skipped_existing}")
        print(f"   🚫 Filtered out: {filtered_out}")
        print(f"   📉 Low score: {low_score_count}")
        print(f"   📋 Total checked: {len(jobs)}")
        print("=" * 60)

        # Check applications collection
        total_apps = await db.applications.count_documents({"user_id": user_id})
        matched_apps = await db.applications.count_documents({
            "user_id": user_id,
            "status": "matched"
        })

        print()
        print("📬 Applications Collection:")
        print(f"   Total: {total_apps}")
        print(f"   Matched: {matched_apps}")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_find_matches_api())
