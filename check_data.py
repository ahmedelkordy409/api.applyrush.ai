#!/usr/bin/env python3
"""
Quick script to check MongoDB data
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
print("DATABASE CHECK")
print("=" * 60)

# Check users
user_count = db.users.count_documents({})
print(f"\n📊 Total Users: {user_count}")

if user_count > 0:
    # Get first user
    user = db.users.find_one()
    user_id = str(user["_id"])
    print(f"   Sample User ID: {user_id}")
    print(f"   Email: {user.get('email', 'N/A')}")

    # Check applications for this user
    print(f"\n📊 Applications for user {user_id}:")

    # Count by status
    statuses = ["matching", "matched", "pending", "approved", "applied", "completed", "rejected"]
    for status in statuses:
        count = db.applications.count_documents({"user_id": user_id, "status": status})
        if count > 0:
            print(f"   - {status}: {count}")

    # Total applications
    total_apps = db.applications.count_documents({"user_id": user_id})
    print(f"   - TOTAL: {total_apps}")

    # Show a sample application if exists
    if total_apps > 0:
        sample_app = db.applications.find_one({"user_id": user_id})
        print(f"\n📄 Sample Application:")
        print(f"   Status: {sample_app.get('status', 'N/A')}")
        print(f"   Job ID: {sample_app.get('job_id', 'N/A')}")
        if 'job' in sample_app:
            print(f"   Job Title: {sample_app['job'].get('title', 'N/A')}")
            print(f"   Company: {sample_app['job'].get('company', 'N/A')}")

# Check jobs
job_count = db.jobs.count_documents({})
print(f"\n📊 Total Jobs: {job_count}")

print("\n" + "=" * 60)

client.close()
