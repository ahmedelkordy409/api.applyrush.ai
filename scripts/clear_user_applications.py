"""
Clear all applications and queue items for a specific user
Use this to reset and test the application flow
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def clear_user_data(user_email: str):
    """Clear all application-related data for a user"""

    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE]

    try:
        # Find user by email
        user = await db.users.find_one({"email": user_email})

        if not user:
            logger.error(f"❌ User not found: {user_email}")
            return

        user_id = str(user["_id"])
        logger.info(f"🔍 Found user: {user_email} (ID: {user_id})")

        # Delete applications
        apps_result = await db.applications.delete_many({"user_id": user_id})
        logger.info(f"🗑️  Deleted {apps_result.deleted_count} applications")

        # Delete auto-apply queue items
        queue_result = await db.auto_apply_queue.delete_many({"user_id": user_id})
        logger.info(f"🗑️  Deleted {queue_result.deleted_count} queue items")

        # Optional: Reset user settings to defaults
        await db.user_settings.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "searchActive": True,
                    "matchThreshold": "good-fit",
                    "approvalMode": "approval"
                },
                "$unset": {
                    "search_paused_at": "",
                    "excludedCompanies": ""
                }
            },
            upsert=True
        )
        logger.info(f"⚙️  Reset user settings to defaults")

        # Optional: Clear user tasks progress
        await db.user_tasks.delete_one({"user_id": user_id})
        logger.info(f"📋 Cleared user tasks progress")

        logger.info(f"✅ Successfully cleared all data for {user_email}")
        logger.info(f"👤 User can now start fresh with the application flow")

    except Exception as e:
        logger.error(f"❌ Error clearing user data: {e}")

    finally:
        client.close()


async def main():
    """Main function"""

    # Default user email - you can change this
    user_email = "kobew70224@ampdial.com"

    if len(sys.argv) > 1:
        user_email = sys.argv[1]

    logger.info(f"🧹 Clearing all applications for: {user_email}")
    logger.info(f"{'='*60}")

    await clear_user_data(user_email)

    logger.info(f"{'='*60}")
    logger.info(f"✨ Done! User can now start testing fresh")


if __name__ == "__main__":
    asyncio.run(main())
