#!/usr/bin/env python3
"""
MongoDB Setup Script for ApplyRush.AI
Initializes collections, indexes, and schema validation
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from datetime import datetime

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = "applyrush_ai"

def setup_mongodb():
    """Initialize MongoDB with all collections, indexes, and validation"""

    print("🔗 Connecting to MongoDB...")
    client = MongoClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    print(f"📦 Database: {DATABASE_NAME}")
    print(f"🌐 URL: {MONGODB_URL}")
    print()

    # Drop existing collections for clean setup (optional - comment out for production)
    # print("⚠️  Dropping existing collections...")
    # for collection in db.list_collection_names():
    #     db.drop_collection(collection)

    print("✨ Creating collections with validation...")

    # 1. USERS COLLECTION
    try:
        db.create_collection("users", validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["email", "created_at"],
                "properties": {
                    "email": {
                        "bsonType": "string",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                    },
                    "subscription_status": {
                        "enum": ["free", "starter", "pro", "pro_plus", "canceled"]
                    },
                    "is_active": {"bsonType": "bool"}
                }
            }
        })
        print("  ✅ users")
    except Exception as e:
        print(f"  ⚠️  users (already exists)")

    # 2. RESUMES COLLECTION
    try:
        db.create_collection("resumes", validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "original_filename", "created_at"],
                "properties": {
                    "user_id": {"bsonType": "objectId"},
                    "is_current": {"bsonType": "bool"},
                    "status": {"enum": ["active", "deleted", "processing"]}
                }
            }
        })
        print("  ✅ resumes")
    except:
        print(f"  ⚠️  resumes (already exists)")

    # 3. JOBS COLLECTION
    try:
        db.create_collection("jobs", validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["title", "company_name", "source", "created_at"],
                "properties": {
                    "status": {"enum": ["active", "expired", "filled", "removed"]}
                }
            }
        })
        print("  ✅ jobs")
    except:
        print(f"  ⚠️  jobs (already exists)")

    # 4. JOB MATCHES COLLECTION
    try:
        db.create_collection("job_matches")
        print("  ✅ job_matches")
    except:
        print(f"  ⚠️  job_matches (already exists)")

    # 5. APPLICATIONS COLLECTION
    try:
        db.create_collection("applications", validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "job_id", "created_at"],
                "properties": {
                    "status": {
                        "enum": ["pending", "submitted", "confirmed", "interview", "rejected", "offer", "hired", "withdrawn"]
                    }
                }
            }
        })
        print("  ✅ applications")
    except:
        print(f"  ⚠️  applications (already exists)")

    # 6. AUTO APPLY APPLICATIONS COLLECTION
    try:
        db.create_collection("auto_apply_applications")
        print("  ✅ auto_apply_applications")
    except:
        print(f"  ⚠️  auto_apply_applications (already exists)")

    # 7. FORWARDING EMAILS COLLECTION
    try:
        db.create_collection("forwarding_emails")
        print("  ✅ forwarding_emails")
    except:
        print(f"  ⚠️  forwarding_emails (already exists)")

    # 8. COVER LETTERS COLLECTION
    try:
        db.create_collection("cover_letters")
        print("  ✅ cover_letters")
    except:
        print(f"  ⚠️  cover_letters (already exists)")

    # 9. INTERVIEW SESSIONS COLLECTION
    try:
        db.create_collection("interview_sessions")
        print("  ✅ interview_sessions")
    except:
        print(f"  ⚠️  interview_sessions (already exists)")

    # 10. SUBSCRIPTIONS COLLECTION
    try:
        db.create_collection("subscriptions")
        print("  ✅ subscriptions")
    except:
        print(f"  ⚠️  subscriptions (already exists)")

    # 11. ACTIVITY LOGS COLLECTION
    try:
        db.create_collection("activity_logs")
        print("  ✅ activity_logs")
    except:
        print(f"  ⚠️  activity_logs (already exists)")

    print()
    print("📊 Creating indexes...")

    # USERS INDEXES
    db.users.create_index([("email", ASCENDING)], unique=True, name="email_unique")
    db.users.create_index([("provider_id", ASCENDING)], name="provider_id")
    db.users.create_index([("stripe_customer_id", ASCENDING)], name="stripe_customer")
    db.users.create_index([("subscription_status", ASCENDING)], name="subscription_status")
    db.users.create_index([("created_at", DESCENDING)], name="created_at")
    print("  ✅ users indexes (5)")

    # RESUMES INDEXES
    db.resumes.create_index([("user_id", ASCENDING)], name="user_id")
    db.resumes.create_index([("user_id", ASCENDING), ("is_current", ASCENDING)], name="user_current")
    db.resumes.create_index([("status", ASCENDING)], name="status")
    db.resumes.create_index([("created_at", DESCENDING)], name="created_at")
    print("  ✅ resumes indexes (4)")

    # JOBS INDEXES
    db.jobs.create_index([("external_id", ASCENDING)], name="external_id")
    db.jobs.create_index([("source", ASCENDING)], name="source")
    db.jobs.create_index([("company_name", ASCENDING)], name="company_name")
    db.jobs.create_index([("location", ASCENDING)], name="location")
    db.jobs.create_index([("ats_type", ASCENDING)], name="ats_type")
    db.jobs.create_index([("status", ASCENDING)], name="status")
    db.jobs.create_index([("posted_date", DESCENDING)], name="posted_date")
    db.jobs.create_index([("title", TEXT), ("description", TEXT), ("company_name", TEXT)], name="text_search")
    print("  ✅ jobs indexes (8)")

    # JOB MATCHES INDEXES
    db.job_matches.create_index([("user_id", ASCENDING)], name="user_id")
    db.job_matches.create_index([("job_id", ASCENDING)], name="job_id")
    db.job_matches.create_index([("user_id", ASCENDING), ("job_id", ASCENDING)], unique=True, name="user_job_unique")
    db.job_matches.create_index([("match_score", DESCENDING)], name="match_score")
    db.job_matches.create_index([("status", ASCENDING)], name="status")
    print("  ✅ job_matches indexes (5)")

    # APPLICATIONS INDEXES
    db.applications.create_index([("user_id", ASCENDING)], name="user_id")
    db.applications.create_index([("job_id", ASCENDING)], name="job_id")
    db.applications.create_index([("user_id", ASCENDING), ("status", ASCENDING)], name="user_status")
    db.applications.create_index([("status", ASCENDING)], name="status")
    db.applications.create_index([("applied_at", DESCENDING)], name="applied_at")
    db.applications.create_index([("auto_applied", ASCENDING)], name="auto_applied")
    db.applications.create_index([("forwarding_email", ASCENDING)], unique=True, sparse=True, name="forwarding_email_unique")
    print("  ✅ applications indexes (7)")

    # AUTO APPLY APPLICATIONS INDEXES
    db.auto_apply_applications.create_index([("user_id", ASCENDING)], name="user_id")
    db.auto_apply_applications.create_index([("job_id", ASCENDING)], name="job_id")
    db.auto_apply_applications.create_index([("application_id", ASCENDING)], name="application_id")
    db.auto_apply_applications.create_index([("status", ASCENDING)], name="status")
    db.auto_apply_applications.create_index([("submitted_at", DESCENDING)], name="submitted_at")
    db.auto_apply_applications.create_index([("forwarding_email", ASCENDING)], name="forwarding_email")
    print("  ✅ auto_apply_applications indexes (6)")

    # FORWARDING EMAILS INDEXES
    db.forwarding_emails.create_index([("forwarding_address", ASCENDING)], unique=True, name="forwarding_address_unique")
    db.forwarding_emails.create_index([("user_id", ASCENDING)], name="user_id")
    db.forwarding_emails.create_index([("application_id", ASCENDING)], name="application_id")
    db.forwarding_emails.create_index([("status", ASCENDING)], name="status")
    db.forwarding_emails.create_index([("expires_at", ASCENDING)], name="expires_at")
    print("  ✅ forwarding_emails indexes (5)")

    # COVER LETTERS INDEXES
    db.cover_letters.create_index([("user_id", ASCENDING)], name="user_id")
    db.cover_letters.create_index([("job_id", ASCENDING)], name="job_id")
    db.cover_letters.create_index([("application_id", ASCENDING)], name="application_id")
    print("  ✅ cover_letters indexes (3)")

    # INTERVIEW SESSIONS INDEXES
    db.interview_sessions.create_index([("user_id", ASCENDING)], name="user_id")
    db.interview_sessions.create_index([("job_id", ASCENDING)], name="job_id")
    db.interview_sessions.create_index([("status", ASCENDING)], name="status")
    db.interview_sessions.create_index([("created_at", DESCENDING)], name="created_at")
    print("  ✅ interview_sessions indexes (4)")

    # SUBSCRIPTIONS INDEXES
    db.subscriptions.create_index([("user_id", ASCENDING)], unique=True, name="user_id_unique")
    db.subscriptions.create_index([("stripe_subscription_id", ASCENDING)], unique=True, sparse=True, name="stripe_sub_unique")
    db.subscriptions.create_index([("status", ASCENDING)], name="status")
    print("  ✅ subscriptions indexes (3)")

    # ACTIVITY LOGS INDEXES
    db.activity_logs.create_index([("user_id", ASCENDING)], name="user_id")
    db.activity_logs.create_index([("action", ASCENDING)], name="action")
    db.activity_logs.create_index([("created_at", DESCENDING)], name="created_at")
    db.activity_logs.create_index([("entity_type", ASCENDING), ("entity_id", ASCENDING)], name="entity")
    # TTL index - auto-delete logs older than 90 days
    db.activity_logs.create_index([("created_at", ASCENDING)], expireAfterSeconds=7776000, name="ttl_90days")
    print("  ✅ activity_logs indexes (5)")

    print()
    print("📈 Database Statistics:")
    print(f"  Collections: {len(db.list_collection_names())}")

    for collection_name in sorted(db.list_collection_names()):
        count = db[collection_name].count_documents({})
        indexes = len(list(db[collection_name].list_indexes()))
        print(f"  - {collection_name}: {count} documents, {indexes} indexes")

    print()
    print("✅ MongoDB setup complete!")
    print()
    print("Next steps:")
    print("1. Update backend to use MongoDB connection")
    print("2. Migrate any existing PostgreSQL data")
    print("3. Test all API endpoints")

    client.close()

if __name__ == "__main__":
    try:
        setup_mongodb()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
