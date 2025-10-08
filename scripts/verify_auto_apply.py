"""
Verify Auto-Apply Results
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from bson import ObjectId


async def verify():
    db = MongoDB.get_async_db()
    
    user = await db.users.find_one({"email": "kobew70224@ampdial.com"})
    user_id = user["_id"]
    
    print("\n" + "=" * 80)
    print("🔍 VERIFYING AUTO-APPLY RESULTS")
    print("=" * 80 + "\n")
    
    # Get queue items with application IDs
    queue_items = await db.application_queue.find({
        "user_id": user_id,
        "status": "auto_applied",
        "application_id": {"$exists": True}
    }).to_list(length=None)
    
    print(f"📋 Queue Items Marked 'auto_applied': {len(queue_items)}\n")
    
    # Check if those applications exist
    for item in queue_items:
        app_id_str = item.get("application_id")
        job = item.get("job", {})
        
        print(f"Queue Item: {job.get('title', 'Unknown')}")
        print(f"  Application ID: {app_id_str}")
        
        # Try to find the application
        try:
            app = await db.applications.find_one({"_id": ObjectId(app_id_str)})
            if app:
                print(f"  ✅ Application EXISTS")
                print(f"     Status: {app.get('status')}")
                print(f"     Match Score: {app.get('match_score', 'N/A')}")
                print(f"     Source: {app.get('source')}")
                print(f"     Method: {app.get('application_method')}")
            else:
                print(f"  ❌ Application NOT FOUND")
        except Exception as e:
            print(f"  ❌ Error checking application: {e}")
        
        print()
    
    # Get all applications
    all_apps = await db.applications.find({"user_id": user_id}).to_list(length=None)
    
    print(f"\n📊 Total Applications: {len(all_apps)}\n")
    
    # Group by source
    by_source = {}
    by_status = {}
    
    for app in all_apps:
        source = app.get("source", "unknown")
        status = app.get("status", "unknown")
        by_source[source] = by_source.get(source, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
    
    print("By Source:")
    for source, count in by_source.items():
        print(f"  {source}: {count}")
    
    print("\nBy Status:")
    for status, count in by_status.items():
        print(f"  {status}: {count}")
    
    # Show auto-applied applications with match scores
    auto_apps = await db.applications.find({
        "user_id": user_id,
        "source": "auto_apply"
    }).to_list(length=None)
    
    if auto_apps:
        print(f"\n✅ Auto-Applied Applications ({len(auto_apps)}):\n")
        for app in auto_apps:
            print(f"  • {app.get('job_title', 'Unknown')} at {app.get('company', 'Unknown')}")
            print(f"    Match Score: {app.get('match_score', 'N/A')}%")
            print(f"    Status: {app.get('status')}")
            print(f"    Method: {app.get('application_method')}")
            print(f"    Applied: {app.get('applied_at')}")
            print()


if __name__ == "__main__":
    asyncio.run(verify())
