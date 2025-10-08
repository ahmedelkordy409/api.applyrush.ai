"""
Check Queue Status
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from bson import ObjectId


async def check_queue():
    db = MongoDB.get_async_db()
    
    # Get test user
    user = await db.users.find_one({"email": "kobew70224@ampdial.com"})
    if not user:
        print("❌ User not found")
        return
    
    user_id = user["_id"]
    
    # Check all queue items
    all_queue = await db.application_queue.find({"user_id": user_id}).to_list(length=None)
    
    print(f"\n📋 Total Queue Items: {len(all_queue)}\n")
    
    if all_queue:
        for item in all_queue:
            job = item.get("job", {})
            print(f"Job: {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
            print(f"  Status: {item.get('status')}")
            print(f"  Match Score: {item.get('match_score', 0)}")
            print(f"  Created: {item.get('created_at')}")
            if item.get('application_id'):
                print(f"  Application ID: {item.get('application_id')}")
            print()
    
    # Check applications
    apps = await db.applications.find({"user_id": user_id}).to_list(length=None)
    print(f"📝 Total Applications: {len(apps)}\n")
    
    if apps:
        status_counts = {}
        for app in apps:
            status = app.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("Application Status:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")


if __name__ == "__main__":
    asyncio.run(check_queue())
