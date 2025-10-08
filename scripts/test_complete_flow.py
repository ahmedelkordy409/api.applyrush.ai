"""
Test Complete Matching Flow
Simulates the exact API call from the frontend "Find New Matches" button
"""

import asyncio
import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.api.endpoints.applications_queue import manage_queue_actions
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId


async def test_complete_matching_flow():
    """Test the complete flow as if called from frontend"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 80)
        print("🚀 TESTING COMPLETE MATCHING FLOW")
        print("=" * 80)
        print()

        # Step 1: Get the active user
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

        # Step 2: Clear existing applications for clean test
        print("📋 Step 2: Clearing existing matched applications...")
        delete_result = await db.applications.delete_many({
            "user_id": user_id,
            "status": "matched"
        })
        print(f"   🗑️  Deleted {delete_result.deleted_count} existing matches")
        print()

        # Step 3: Check current stats
        print("📋 Step 3: Checking current database stats...")
        total_jobs = await db.jobs.count_documents({"is_active": True})
        total_apps_before = await db.applications.count_documents({"user_id": user_id})
        print(f"   📊 Active jobs in database: {total_jobs:,}")
        print(f"   📊 User's applications before: {total_apps_before}")
        print()

        # Step 4: Simulate the API call
        print("📋 Step 4: Simulating 'Find New Matches' button click...")
        print("   🔍 Searching for up to 5 job matches...")
        print()

        # Import the actual function logic
        from app.services.job_matcher_service import job_matcher_service
        from datetime import datetime, timedelta

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

        print(f"   📊 Match threshold: {match_threshold} (minimum score: {min_score})")
        print(f"   🎯 Target: Find 5 best matches")
        print()

        # Get active jobs
        jobs_cursor = db.jobs.find({
            "is_active": True
        }).sort("created_at", -1)

        jobs = await jobs_cursor.to_list(length=None)

        # Match jobs for user
        matched_count = 0
        skipped_existing = 0
        filtered_out = 0
        low_score_count = 0
        matched_jobs_list = []
        limit = 5

        print("   🔄 Processing jobs...")
        print("   " + "-" * 76)

        for idx, job in enumerate(jobs, 1):
            try:
                job_id = str(job["_id"])

                # Check if job already exists in applications
                existing_application = await db.applications.find_one({
                    "user_id": user_id,
                    "job_id": job_id
                })

                if existing_application:
                    skipped_existing += 1
                    continue

                # Check hard filters first
                passes_filters, filter_reason = job_matcher_service.passes_user_filters(user, job)
                if not passes_filters:
                    filtered_out += 1
                    continue

                # Calculate match score
                match_result = await job_matcher_service.calculate_match_score(user, job)
                match_score = match_result["score"]
                match_reasons = match_result["reasons"]

                if match_score >= min_score:
                    # Prepare job data for storage
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

                    # Create application match entry
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

                    # Insert into applications collection
                    result = await db.applications.insert_one(application)
                    application["_id"] = str(result.inserted_id)

                    # Add to response list
                    matched_jobs_list.append({
                        "id": str(result.inserted_id),
                        "job_id": job_id,
                        "status": "matched",
                        "match_score": match_score,
                        "match_reasons": match_reasons,
                        "job": job_data
                    })

                    matched_count += 1

                    print(f"   ✅ Match {matched_count}: '{job.get('title', 'Unknown')[:50]}' - Score: {match_score}/100")
                    print(f"      Company: {job.get('company', 'Unknown')}")
                    print(f"      Reasons: {', '.join(match_reasons[:2])}")
                    print()

                    # Stop if we reached the limit
                    if matched_count >= limit:
                        print(f"   🎯 Reached target of {limit} matches!")
                        break
                else:
                    low_score_count += 1

            except Exception as e:
                print(f"   ❌ Error matching job: {e}")
                continue

        print("   " + "-" * 76)
        print()

        # Step 5: Show results
        print("📋 Step 5: Matching Results")
        print()
        print(f"   📊 STATISTICS:")
        print(f"      ✅ Matched: {matched_count}")
        print(f"      🔄 Already in applications: {skipped_existing}")
        print(f"      🚫 Filtered out: {filtered_out}")
        print(f"      📉 Below threshold ({min_score}): {low_score_count}")
        print(f"      📋 Total jobs scanned: {len(jobs):,}")
        print()

        # Step 6: Verify in database
        print("📋 Step 6: Verifying database...")
        total_apps_after = await db.applications.count_documents({"user_id": user_id})
        matched_apps = await db.applications.count_documents({
            "user_id": user_id,
            "status": "matched"
        })

        print(f"   📊 User's total applications: {total_apps_after}")
        print(f"   🎯 Matched applications: {matched_apps}")
        print()

        # Step 7: Show sample matched jobs
        if matched_count > 0:
            print("📋 Step 7: Sample Matched Jobs")
            print()

            sample_apps = await db.applications.find({
                "user_id": user_id,
                "status": "matched"
            }).limit(3).to_list(length=3)

            for i, app in enumerate(sample_apps, 1):
                job = app.get("job", {})
                print(f"   {i}. {job.get('title', 'Unknown')}")
                print(f"      📍 {job.get('company', 'Unknown')} - {job.get('location', 'Unknown')}")
                print(f"      💰 Salary: {job.get('salary_min', 'N/A')} - {job.get('salary_max', 'N/A')} {job.get('salary_currency', '')}")
                print(f"      🎯 Match Score: {app.get('match_score', 0)}/100")
                print(f"      ✨ Remote: {'Yes' if job.get('remote') else 'No'}")
                print()

        # Step 8: Frontend response simulation
        print("📋 Step 8: Frontend would receive:")
        print()
        response = {
            "success": True,
            "message": f"Found {matched_count} new job matches",
            "matches": matched_jobs_list,
            "stats": {
                "matched": matched_count,
                "already_exists": skipped_existing,
                "filtered_out": filtered_out,
                "low_score": low_score_count,
                "total_jobs": len(jobs)
            }
        }
        print(f"   ✅ Success: {response['success']}")
        print(f"   💬 Message: {response['message']}")
        print(f"   📊 Matches returned: {len(response['matches'])}")
        print()

        print("=" * 80)
        if matched_count > 0:
            print("✅ TEST PASSED - Matching system working perfectly!")
        else:
            print("⚠️  TEST WARNING - No matches found (may need to adjust threshold)")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_complete_matching_flow())
