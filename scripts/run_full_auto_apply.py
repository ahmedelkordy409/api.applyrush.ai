"""
Run Full Auto-Apply Process
1. Find matches for active users
2. Process auto-apply queue
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.background_jobs import background_job_service


async def run_auto_apply():
    db = MongoDB.get_async_db()
    
    print("\n" + "=" * 80)
    print("🎯 RUNNING FULL AUTO-APPLY PROCESS")
    print("=" * 80 + "\n")
    
    # Get user
    user = await db.users.find_one({"email": "kobew70224@ampdial.com"})
    user_id = user["_id"]
    
    # Clear old queue items first
    print("🧹 Cleaning up old auto_applied queue items...")
    result = await db.application_queue.delete_many({
        "user_id": user_id,
        "status": "auto_applied"
    })
    print(f"   Removed {result.deleted_count} old queue items\n")
    
    # Count current applications
    before_count = await db.applications.count_documents({"user_id": user_id})
    print(f"📊 Applications before: {before_count}\n")
    
    # Step 1: Find matches
    print("🔍 Step 1: Finding job matches...")
    await background_job_service.find_matches_for_active_users()
    print()
    
    # Check queue
    queue_count = await db.application_queue.count_documents({
        "user_id": user_id,
        "status": {"$in": ["pending", "approved"]}
    })
    print(f"📋 Queue items pending/approved: {queue_count}\n")
    
    if queue_count == 0:
        print("⚠️  No new matches found. Checking why...\n")
        
        # Check user preferences
        prefs = user.get("preferences", {})
        print("User Preferences:")
        print(f"  search_active: {prefs.get('search_active')}")
        print(f"  match_threshold: {prefs.get('match_threshold')}")
        print(f"  approval_mode: {prefs.get('approval_mode')}")
        print()
        
        # Check jobs count
        jobs_count = await db.jobs.count_documents({"is_active": True})
        print(f"Active jobs in database: {jobs_count}\n")
        
        return
    
    # Step 2: Approve items if needed
    approval_mode = user.get("preferences", {}).get("approval_mode", "approval")
    print(f"Approval Mode: {approval_mode}")
    
    if approval_mode == "approval":
        print("✅ Approving queue items manually...")
        from datetime import datetime
        result = await db.application_queue.update_many(
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
        print(f"   Approved {result.modified_count} items\n")
    
    # Step 3: Process auto-apply
    print("🚀 Step 2: Processing auto-apply queue...")
    await background_job_service.process_auto_apply_queue()
    print()
    
    # Check results
    after_count = await db.applications.count_documents({"user_id": user_id})
    new_apps = after_count - before_count
    
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80 + "\n")
    print(f"Applications before: {before_count}")
    print(f"Applications after:  {after_count}")
    print(f"New applications:    {new_apps}\n")
    
    # Show new applications
    if new_apps > 0:
        apps = await db.applications.find({
            "user_id": user_id,
            "source": "auto_apply"
        }).sort("applied_at", -1).to_list(length=10)
        
        print(f"✅ Auto-Applied Jobs ({len(apps)}):\n")
        for app in apps:
            print(f"  • {app.get('job_title', 'Unknown')} at {app.get('company', 'Unknown')}")
            print(f"    Match Score: {app.get('match_score', 0)}%")
            print(f"    Method: {app.get('application_method')}")
            print(f"    Status: {app.get('status')}")
            print()
    
    print("=" * 80)
    print("✅ AUTO-APPLY COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_auto_apply())
