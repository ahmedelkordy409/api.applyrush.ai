"""
Create Database Indexes for Duplicate Prevention
Ensures no duplicate applications can be created
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB


async def create_indexes():
    """Create indexes to prevent duplicate applications"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 80)
        print("🔒 CREATING DUPLICATE PREVENTION INDEXES")
        print("=" * 80)
        print()

        # Index 1: Prevent duplicate applications (user_id + job_id must be unique)
        print("Creating unique index on applications collection...")
        await db.applications.create_index(
            [("user_id", 1), ("job_id", 1)],
            unique=True,
            name="unique_user_job_application"
        )
        print("✅ Created unique index: user_id + job_id on applications")
        print()

        # Index 2: Prevent duplicate queue items
        print("Creating unique index on application_queue collection...")
        await db.application_queue.create_index(
            [("user_id", 1), ("job_id", 1)],
            unique=True,
            name="unique_user_job_queue"
        )
        print("✅ Created unique index: user_id + job_id on application_queue")
        print()

        # Index 3: Fast lookup for existing applications
        print("Creating index for fast duplicate checking...")
        await db.applications.create_index(
            [("user_id", 1), ("job_id", 1), ("status", 1)],
            name="user_job_status_lookup"
        )
        print("✅ Created index: user_id + job_id + status for fast lookups")
        print()

        # Index 4: Job hash for deduplication (if using job hashes)
        print("Creating index on job_hash for deduplication...")
        await db.jobs.create_index(
            [("job_hash", 1)],
            unique=True,
            sparse=True,  # Allow null values
            name="unique_job_hash"
        )
        print("✅ Created unique index: job_hash on jobs collection")
        print()

        # List all indexes
        print("=" * 80)
        print("📊 CURRENT INDEXES")
        print("=" * 80)
        print()

        collections = ["applications", "application_queue", "jobs"]
        for collection_name in collections:
            collection = db[collection_name]
            indexes = await collection.list_indexes().to_list(length=None)
            print(f"\n{collection_name}:")
            for idx in indexes:
                print(f"  • {idx['name']}: {idx.get('key', {})}")
                if idx.get('unique'):
                    print(f"    → UNIQUE index - prevents duplicates")

        print()
        print("=" * 80)
        print("✅ DUPLICATE PREVENTION INDEXES CREATED!")
        print("=" * 80)
        print()
        print("💡 How Duplicate Prevention Works:")
        print("   1. Unique index on (user_id, job_id) in applications")
        print("      → Database will reject duplicate applications")
        print()
        print("   2. Unique index on (user_id, job_id) in queue")
        print("      → Prevents same job from being queued twice")
        print()
        print("   3. Code checks before applying:")
        print("      → Check queue for duplicates")
        print("      → Check applications for duplicates")
        print()
        print("   4. Job hash prevents duplicate jobs")
        print("      → Same job from different sources = same job_hash")
        print()
        print("🔒 RESULT: Zero duplicate applications possible!")
        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🔒 Creating duplicate prevention indexes...\n")
    asyncio.run(create_indexes())
