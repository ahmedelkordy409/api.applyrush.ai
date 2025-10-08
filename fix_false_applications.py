"""
Fix applications that were incorrectly marked as 'applied' without actual submission
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from datetime import datetime

async def fix_false_applications():
    """Mark applications as failed if they were browser automation without actual submission"""

    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE]

    # Find applications marked as applied via browser automation today
    # These are likely false positives from the previous buggy logic
    result = await db.applications.update_many(
        {
            "status": "applied",
            "application_method": "auto_apply_browser",
            "applied_at": {"$exists": True}
        },
        {
            "$set": {
                "status": "failed",
                "notes": "Browser automation failed - no form fields filled, CAPTCHA blocked, or no resume available",
                "updated_at": datetime.utcnow()
            }
        }
    )

    print(f"✅ Updated {result.modified_count} applications from 'applied' to 'failed'")

    # Also mark corresponding queue items as failed
    queue_result = await db.auto_apply_queue.update_many(
        {
            "status": "completed",
            "created_at": {"$gte": datetime(2025, 10, 6)}  # Today's date
        },
        {
            "$set": {
                "status": "failed",
                "updated_at": datetime.utcnow()
            }
        }
    )

    print(f"✅ Updated {queue_result.modified_count} queue items from 'completed' to 'failed'")

    client.close()

if __name__ == "__main__":
    asyncio.run(fix_false_applications())
