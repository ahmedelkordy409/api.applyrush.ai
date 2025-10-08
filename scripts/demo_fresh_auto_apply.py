"""
Fresh Demo - Clear previous test data and run auto-apply
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.background_jobs import background_job_service


async def fresh_demo():
    db = MongoDB.get_async_db()
    
    print("\n" + "=" * 80)
    print("🎯 FRESH AUTO-APPLY DEMO")
    print("=" * 80 + "\n")
    
    user = await db.users.find_one({"email": "kobew70224@ampdial.com"})
    user_id = user["_id"]
    
    # Clear all previous applications and queue for fresh demo
    print("🧹 Clearing previous test data...")
    
    apps_deleted = await db.applications.delete_many({"user_id": user_id})
    queue_deleted = await db.application_queue.delete_many({"user_id": user_id})
    
    print(f"   Deleted {apps_deleted.deleted_count} applications")
    print(f"   Deleted {queue_deleted.deleted_count} queue items\n")
    
    # Set threshold to good-fit
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {
            "preferences.match_threshold": "good-fit",
            "preferences.approval_mode": "instant"  # Auto-approve for demo
        }}
    )
    
    print("⚙️  Settings:")
    print("   Match Threshold: good-fit (70%+)")
    print("   Approval Mode: instant (auto-apply immediately)\n")
    
    # Run matching
    print("🔍 Step 1: Finding job matches...")
    await background_job_service.find_matches_for_active_users()
    print()
    
    # Check queue
    queue_items = await db.application_queue.find({
        "user_id": user_id
    }).to_list(length=None)
    
    print(f"📋 Found {len(queue_items)} matches in queue\n")
    
    if queue_items:
        print("Matched Jobs:")
        for item in queue_items:
            job = item.get("job", {})
            print(f"  • {job.get('title', 'Unknown')[:60]}")
            print(f"    Company: {job.get('company', 'Unknown')}")
            print(f"    Score: {item.get('match_score')}%")
            print(f"    Status: {item.get('status')}")
        print()
        
        # Run auto-apply
        print("🚀 Step 2: Processing auto-apply...")
        await background_job_service.process_auto_apply_queue()
        print()
        
        # Check results
        apps = await db.applications.find({"user_id": user_id}).to_list(length=None)
        
        print("=" * 80)
        print("📊 RESULTS")
        print("=" * 80 + "\n")
        print(f"✅ Total Applications Created: {len(apps)}\n")
        
        if apps:
            print("Auto-Applied Jobs:\n")
            for app in apps:
                print(f"  • {app.get('job_title', 'Unknown')}")
                print(f"    Company: {app.get('company', 'Unknown')}")
                print(f"    Match Score: {app.get('match_score', 0)}% ⭐")
                print(f"    Status: {app.get('status')}")
                print(f"    Method: {app.get('application_method')}")
                
                # Show match reasons
                reasons = app.get('match_reasons', [])
                if reasons:
                    print(f"    Why it matched:")
                    for reason in reasons[:2]:
                        print(f"      • {reason}")
                print()
    else:
        print("❌ No matches found")
    
    print("=" * 80)
    print("✅ DEMO COMPLETE!")
    print("=" * 80)
    print("\n💡 How Auto-Apply Works Automatically:\n")
    print("   1. APScheduler runs every 30 minutes:")
    print("      → Finds job matches for all active users")
    print("      → Adds matching jobs to queue\n")
    print("   2. APScheduler runs every 5 minutes:")
    print("      → Processes approved queue items")
    print("      → Sends applications via email or saves to DB\n")
    print("   3. User controls via settings:")
    print("      → Match Threshold: open (60%+), good-fit (70%+), top (85%+)")
    print("      → Approval Mode: instant, delayed (24h), approval (manual)\n")
    print("   No user action needed - completely automatic! 🚀\n")


if __name__ == "__main__":
    asyncio.run(fresh_demo())
