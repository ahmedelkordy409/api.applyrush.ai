"""
Trigger Auto-Apply for Matched Jobs
Approves pending queue items and triggers auto-apply process
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from app.services.background_jobs import background_job_service


async def trigger_auto_apply():
    """Approve queue items and trigger auto-apply"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 80)
        print("🎯 TRIGGERING AUTO-APPLY FOR MATCHED JOBS")
        print("=" * 80)
        print()

        # Get test user
        user = await db.users.find_one({"email": "kobew70224@ampdial.com"})
        if not user:
            print("❌ User not found")
            return

        user_id = user["_id"]
        print(f"👤 User: {user.get('email')}")
        print()

        # Get pending queue items
        pending_items = await db.application_queue.find({
            "user_id": user_id,
            "status": {"$in": ["pending", "approved"]}
        }).to_list(length=None)

        print(f"📋 Found {len(pending_items)} items in queue")
        print()

        if not pending_items:
            print("⚠️  No pending items to process")
            return

        # Show queue items
        print("Queue Items:")
        for item in pending_items:
            job = item.get("job", {})
            print(f"  • {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
            print(f"    Status: {item.get('status')}, Score: {item.get('match_score', 0)}")
        print()

        # Approve all pending items
        print("✅ Approving all pending items...")
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
        print(f"   Approved {result.modified_count} items")
        print()

        # Trigger auto-apply
        print("🚀 Running auto-apply process...")
        await background_job_service.process_auto_apply_queue()
        print()

        # Check results
        print("=" * 80)
        print("📊 RESULTS")
        print("=" * 80)
        print()

        # Get updated queue status
        queue_status = {}
        queue_items = await db.application_queue.find({"user_id": user_id}).to_list(length=None)
        for item in queue_items:
            status = item.get("status")
            queue_status[status] = queue_status.get(status, 0) + 1

        print("Queue Status:")
        for status, count in queue_status.items():
            print(f"  {status}: {count}")
        print()

        # Get applications created
        applications = await db.applications.find({
            "user_id": user_id,
            "source": "auto_apply"
        }).sort("applied_at", -1).to_list(length=10)

        print(f"✅ Auto-Applied Applications: {len(applications)}")
        print()

        if applications:
            print("Recently Applied:")
            for app in applications[:5]:
                print(f"  • {app.get('job_title', 'Unknown')} at {app.get('company', 'Unknown')}")
                print(f"    Match Score: {app.get('match_score', 0)}%")
                print(f"    Method: {app.get('application_method', 'unknown')}")
                print(f"    Applied: {app.get('applied_at', 'unknown')}")
                print()

        # Total applications count
        total_apps = await db.applications.count_documents({"user_id": user_id})
        print(f"📈 Total Applications: {total_apps}")
        print()

        print("=" * 80)
        print("✅ AUTO-APPLY COMPLETE!")
        print("=" * 80)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🎯 Triggering auto-apply...\n")
    asyncio.run(trigger_auto_apply())
