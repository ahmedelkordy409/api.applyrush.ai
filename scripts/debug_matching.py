"""
Debug Job Matching
Find out why no matches are being found
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.job_matcher_service import job_matcher_service


async def debug_matching():
    db = MongoDB.get_async_db()
    
    print("\n" + "=" * 80)
    print("🔍 DEBUGGING JOB MATCHING")
    print("=" * 80 + "\n")
    
    user = await db.users.find_one({"email": "kobew70224@ampdial.com"})
    user_id = str(user["_id"])
    
    # User preferences
    prefs = user.get("preferences", {})
    print("User Preferences:")
    print(f"  search_active: {prefs.get('search_active')}")
    print(f"  match_threshold: {prefs.get('match_threshold')} (85%+ required)")
    print(f"  approval_mode: {prefs.get('approval_mode')}")
    print()
    
    # Get latest 10 jobs
    jobs = await db.jobs.find({"is_active": True}).sort("created_at", -1).limit(10).to_list(length=10)
    
    print(f"Testing matching on {len(jobs)} latest jobs:\n")
    
    matches_found = 0
    
    for i, job in enumerate(jobs, 1):
        job_id = str(job["_id"])
        
        # Check if already applied
        existing_app = await db.applications.find_one({
            "user_id": user["_id"],
            "job_id": job_id
        })
        
        # Calculate match score
        match_result = await job_matcher_service.calculate_match_score(user, job)
        score = match_result["score"]
        
        print(f"{i}. {job.get('title', 'Unknown')[:50]} at {job.get('company', 'Unknown')[:30]}")
        print(f"   Score: {score}% {'✅ MATCH!' if score >= 85 else '❌ Too low'}")
        
        if existing_app:
            print(f"   ⚠️  Already applied")
        
        if score >= 85 and not existing_app:
            matches_found += 1
            print(f"   Match Reasons:")
            for reason in match_result.get("reasons", [])[:3]:
                print(f"     • {reason}")
        
        print()
    
    print("=" * 80)
    print(f"📊 Matches Found (85%+, not applied): {matches_found}")
    print("=" * 80)
    
    if matches_found == 0:
        print("\n💡 Suggestions:")
        print("  • Lower match_threshold to 'good-fit' (70%+) in settings")
        print("  • Or check if all matching jobs have already been applied to")
        print("  • Or wait for more jobs to be collected")


if __name__ == "__main__":
    asyncio.run(debug_matching())
