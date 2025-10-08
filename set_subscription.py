"""Quick script to set subscription_plan for a user"""
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "jobhire")

async def set_subscription():
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[MONGODB_DATABASE]

    result = await db.users.update_one(
        {"email": "paid@example.com"},
        {
            "$set": {
                "subscription_plan": "starter",
                "subscription_status": "active",
                "billing_cycle": "monthly"
            }
        }
    )

    print(f"✓ Updated {result.modified_count} user(s)")

    # Verify
    user = await db.users.find_one({"email": "paid@example.com"})
    print(f"✓ User subscription_plan: {user.get('subscription_plan')}")

    client.close()

if __name__ == "__main__":
    asyncio.run(set_subscription())
