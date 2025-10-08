"""
Enable Instant Auto-Apply
Sets user preferences to automatically apply to matched jobs
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB
from bson import ObjectId


async def enable_instant_apply():
    """Enable instant auto-apply for active users"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 60)
        print("⚡ Enabling Instant Auto-Apply")
        print("=" * 60)
        print()

        # Get active user
        user = await db.users.find_one({
            "preferences.search_active": True
        })

        if not user:
            print("❌ No active user found!")
            return

        user_id = user["_id"]
        user_email = user.get("email", "unknown")

        print(f"👤 User: {user_email}")
        print()

        # Update user preferences to instant auto-apply
        await db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "preferences.approval_mode": "instant",
                    "preferences.auto_apply_delay": 0,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        print("✅ Updated user preferences:")
        print("   Approval Mode: instant (auto-apply immediately)")
        print("   Auto Apply Delay: 0 hours")
        print()

        # Update existing queue items to set auto_apply_after to now
        result = await db.application_queue.update_many(
            {
                "user_id": user_id,
                "status": "approved",
                "auto_apply_after": {"$exists": False}
            },
            {
                "$set": {
                    "auto_apply_after": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        print(f"✅ Updated {result.modified_count} queue items")
        print("   Set auto_apply_after to NOW")
        print()

        # Check queue status
        total_queue = await db.application_queue.count_documents({"user_id": user_id})
        approved = await db.application_queue.count_documents({
            "user_id": user_id,
            "status": "approved"
        })
        ready_to_apply = await db.application_queue.count_documents({
            "user_id": user_id,
            "status": "approved",
            "auto_apply_after": {"$lte": datetime.utcnow()}
        })

        print("📊 Queue Status:")
        print(f"   Total items: {total_queue}")
        print(f"   Approved: {approved}")
        print(f"   Ready to auto-apply: {ready_to_apply}")
        print()

        print("=" * 60)
        print("✅ Instant auto-apply enabled!")
        print("=" * 60)
        print()
        print("💡 New matches will now be automatically applied")
        print("💡 Existing approved jobs are ready for auto-apply")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(enable_instant_apply())
