"""
Initialize Database Indexes
Creates unique indexes to prevent duplicate jobs
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB


async def create_indexes():
    """Create database indexes for jobs collection"""
    try:
        db = MongoDB.get_async_db()

        print("=" * 60)
        print("Creating Database Indexes")
        print("=" * 60)
        print()

        # Create unique index on jobs collection
        # This prevents duplicate jobs from same source
        print("Creating unique index on jobs collection...")

        # Index on source + external_id (prevents duplicates from same source)
        await db.jobs.create_index(
            [("source", 1), ("external_id", 1)],
            unique=True,
            name="unique_source_external_id"
        )
        print("✅ Created unique index: source + external_id")

        # Index on title + company + location (prevents similar jobs)
        await db.jobs.create_index(
            [("title", 1), ("company", 1), ("location", 1)],
            name="job_dedup_index"
        )
        print("✅ Created index: title + company + location")

        # Index on is_active for faster queries
        await db.jobs.create_index(
            [("is_active", 1)],
            name="active_jobs_index"
        )
        print("✅ Created index: is_active")

        # Index on created_at for sorting
        await db.jobs.create_index(
            [("created_at", -1)],
            name="created_at_desc_index"
        )
        print("✅ Created index: created_at (desc)")

        # Create indexes on application_queue collection
        print("\nCreating indexes on application_queue collection...")

        # Unique index to prevent duplicate queue items
        await db.application_queue.create_index(
            [("user_id", 1), ("job_id", 1)],
            unique=True,
            name="unique_user_job"
        )
        print("✅ Created unique index: user_id + job_id")

        # Index on status for filtering
        await db.application_queue.create_index(
            [("status", 1)],
            name="queue_status_index"
        )
        print("✅ Created index: status")

        # Index on user_id for user-specific queries
        await db.application_queue.create_index(
            [("user_id", 1)],
            name="queue_user_index"
        )
        print("✅ Created index: user_id")

        print("\n" + "=" * 60)
        print("✅ All indexes created successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error creating indexes: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(create_indexes())
