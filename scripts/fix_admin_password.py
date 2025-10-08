"""
Fix admin user password hash
"""

import asyncio
from datetime import datetime
from app.core.database_new import MongoDB, connect_to_mongo
from app.core.security import hash_password

async def fix_admin_password():
    print("\n🔧 Fixing Admin Password...")
    print("="*60)

    await connect_to_mongo()

    db = MongoDB.get_async_db()
    users_collection = db["users"]

    # Admin credentials
    admin_email = "admin@applyrush.ai"
    admin_password = "admin123"

    # Find admin
    admin_user = await users_collection.find_one({"email": admin_email})

    if not admin_user:
        print(f"❌ Admin user not found: {admin_email}")
        return

    print(f"✅ Found admin user: {admin_email}")
    print(f"   Current role: {admin_user.get('role')}")
    print(f"   Has password_hash: {'password_hash' in admin_user}")
    print(f"   Has hashed_password: {'hashed_password' in admin_user}")

    # Hash the password correctly
    correct_hash = hash_password(admin_password)

    print(f"\n🔑 Updating password hash...")

    # Update with correct hash
    result = await users_collection.update_one(
        {"email": admin_email},
        {
            "$set": {
                "hashed_password": correct_hash,
                "updated_at": datetime.utcnow()
            },
            "$unset": {
                "password_hash": ""  # Remove old field if it exists
            }
        }
    )

    if result.modified_count > 0:
        print(f"✅ Password hash updated successfully!")
    else:
        print(f"⚠️  No changes made (hash might already be correct)")

    print(f"\n📧 Email: {admin_email}")
    print(f"🔑 Password: {admin_password}")
    print(f"\n🔗 Test login: http://localhost:3000/admin/login")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(fix_admin_password())
