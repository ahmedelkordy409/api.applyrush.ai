#!/usr/bin/env python3
"""
Check all applications in database
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "jobhire")

client = MongoClient(MONGODB_URL)
db = client[MONGODB_DATABASE]

print("=" * 60)
print("ALL APPLICATIONS CHECK")
print("=" * 60)

# Get all applications
total_apps = db.applications.count_documents({})
print(f"\n📊 Total Applications in Database: {total_apps}")

if total_apps > 0:
    # Group by user
    pipeline = [
        {
            "$group": {
                "_id": "$user_id",
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"count": -1}}
    ]

    results = list(db.applications.aggregate(pipeline))
    print(f"\n📊 Applications by User:")
    for result in results[:10]:  # Show top 10 users
        user_id = result["_id"]
        count = result["count"]

        # Get user email
        user = db.users.find_one({"_id": user_id}) if user_id else None
        email = user.get("email", "Unknown") if user else "Unknown"

        print(f"   - {email} ({user_id}): {count} applications")

        # Show status breakdown for this user
        statuses = db.applications.aggregate([
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ])

        for status in statuses:
            print(f"       • {status['_id']}: {status['count']}")

    # Show sample application
    print(f"\n📄 Sample Application:")
    sample = db.applications.find_one()
    print(f"   User ID: {sample.get('user_id', 'N/A')}")
    print(f"   Status: {sample.get('status', 'N/A')}")
    print(f"   Created: {sample.get('created_at', 'N/A')}")
    if 'job' in sample:
        print(f"   Job: {sample['job'].get('title', 'N/A')} at {sample['job'].get('company', 'N/A')}")

else:
    print("\n⚠️  No applications found in database!")
    print("\nYou need to:")
    print("1. Login to the dashboard")
    print("2. Click 'Find Matches' button")
    print("3. Or wait for the background job to run")

print("\n" + "=" * 60)

client.close()
