"""
Demo Auto-Apply Process
Temporarily lower threshold to get matches and demonstrate the system
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.background_jobs import background_job_service


async def demo_auto_apply():
    db = MongoDB.get_async_db()
    
    print("\n" + "=" * 80)
    print("🎯 AUTO-APPLY DEMO")
    print("=" * 80 + "\n")
    
    user = await db.users.find_one({"email": "kobew70224@ampdial.com"})
    user_id = user["_id"]
    
    # Save original threshold
    original_threshold = user.get("preferences", {}).get("match_threshold", "top")
    print(f"Original threshold: {original_threshold} (85%+)")
    print(f"Temporarily changing to 'good-fit' (70%+) for demo...\n")
    
    # Update to good-fit temporarily
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"preferences.match_threshold": "good-fit"}}
    )
    
    # Count before
    before_apps = await db.applications.count_documents({"user_id": user_id})
    print(f"📊 Applications before: {before_apps}\n")
    
    # Run matching
    print("🔍 Finding job matches with 70%+ threshold...")
    await background_job_service.find_matches_for_active_users()
    print()
    
    # Check queue
    queue_items = await db.application_queue.find({
        "user_id": user_id,
        "status": "pending"
    }).to_list(length=None)
    
    print(f"📋 Found {len(queue_items)} matches:\n")
    
    if queue_items:
        for item in queue_items:
            job = item.get("job", {})
            print(f"  • {job.get('title', 'Unknown')[:60]}")
            print(f"    Company: {job.get('company', 'Unknown')}")
            print(f"    Match Score: {item.get('match_score')}%")
            print(f"    Location: {job.get('location', 'Unknown')}")
            print()
        
        # Approve all
        print("✅ Approving all matches...")
        await db.application_queue.update_many(
            {
                "user_id": user_id,
                "status": "pending"
            },
            {
                "$set": {
                    "status": "approved",
                    "auto_apply_after": datetime.utcnow()
                }
            }
        )
        print()
        
        # Run auto-apply
        print("🚀 Processing auto-apply...")
        await background_job_service.process_auto_apply_queue()
        print()
        
        # Check results
        after_apps = await db.applications.count_documents({"user_id": user_id})
        new_apps = after_apps - before_apps
        
        print("=" * 80)
        print("📊 RESULTS")
        print("=" * 80 + "\n")
        print(f"Applications before: {before_apps}")
        print(f"Applications after:  {after_apps}")
        print(f"New applications:    {new_apps}\n")
        
        # Show new applications with match scores
        auto_apps = await db.applications.find({
            "user_id": user_id,
            "source": "auto_apply"
        }).sort("applied_at", -1).limit(10).to_list(length=10)
        
        if auto_apps:
            print(f"✅ Auto-Applied Jobs ({len(auto_apps)}):\n")
            for app in auto_apps:
                print(f"  • {app.get('job_title', 'Unknown')}")
                print(f"    Company: {app.get('company', 'Unknown')}")
                print(f"    Match Score: {app.get('match_score', 0)}%")
                print(f"    Method: {app.get('application_method', 'unknown')}")
                print(f"    Status: {app.get('status')}")
                
                # Show match reasons
                reasons = app.get('match_reasons', [])
                if reasons:
                    print(f"    Why it matched:")
                    for reason in reasons[:2]:
                        print(f"      • {reason}")
                print()
    else:
        print("❌ No matches found even with 70%+ threshold")
        print("   This might mean all matching jobs have been applied to already")
    
    # Restore original threshold
    print(f"Restoring original threshold: {original_threshold}\n")
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"preferences.match_threshold": original_threshold}}
    )
    
    print("=" * 80)
    print("✅ DEMO COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_auto_apply())
