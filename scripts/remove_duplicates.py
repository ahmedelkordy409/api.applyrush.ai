"""
Remove Duplicate Applications
Clean up existing duplicates before creating unique index
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_new import MongoDB


async def remove_duplicates():
    """Remove duplicate applications"""
    db = MongoDB.get_async_db()

    print("=" * 80)
    print("🔍 FINDING AND REMOVING DUPLICATE APPLICATIONS")
    print("=" * 80)
    print()

    # Get all applications
    apps = await db.applications.find({}).to_list(length=None)

    # Find duplicates
    seen = {}
    duplicates = []

    for app in apps:
        key = (str(app.get("user_id")), str(app.get("job_id")))
        if key in seen:
            duplicates.append(app["_id"])
            print(f"Duplicate: user={key[0][:8]}..., job={key[1][:8]}...")
        else:
            seen[key] = app["_id"]

    print()
    print(f"Total applications: {len(apps)}")
    print(f"Unique applications: {len(seen)}")
    print(f"Duplicates found: {len(duplicates)}")
    print()

    if duplicates:
        print(f"Removing {len(duplicates)} duplicate applications...")
        result = await db.applications.delete_many({"_id": {"$in": duplicates}})
        print(f"✅ Removed {result.deleted_count} duplicates")
    else:
        print("✅ No duplicates found!")

    # Final count
    final_count = await db.applications.count_documents({})
    print()
    print(f"Final application count: {final_count}")
    print()
    print("=" * 80)
    print("✅ DUPLICATE CLEANUP COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    print("\n🔍 Removing duplicate applications...\n")
    asyncio.run(remove_duplicates())
