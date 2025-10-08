"""
Create an admin user for the admin dashboard
"""

import asyncio
from datetime import datetime
from app.core.database_new import MongoDB, connect_to_mongo
from app.core.security import hash_password

async def create_admin():
    print("\n🔐 Creating Admin User...")
    print("="*60)

    await connect_to_mongo()

    db = MongoDB.get_async_db()
    users_collection = db["users"]

    # Admin credentials
    admin_email = "admin@applyrush.ai"
    admin_password = "admin123"  # Change this after first login!

    # Check if admin already exists
    existing_admin = await users_collection.find_one({"email": admin_email})

    if existing_admin:
        print(f"✅ Admin user already exists: {admin_email}")
        print(f"   Role: {existing_admin.get('role')}")
        return

    # Create admin user
    admin_user = {
        "email": admin_email,
        "hashed_password": hash_password(admin_password),
        "full_name": "Admin User",
        "role": "super_admin",
        "is_active": True,
        "email_verified": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "subscription_tier": "enterprise",
        "subscription_status": "active",
    }

    result = await users_collection.insert_one(admin_user)

    print(f"✅ Admin user created successfully!")
    print(f"\n📧 Email: {admin_email}")
    print(f"🔑 Password: {admin_password}")
    print(f"🆔 User ID: {result.inserted_id}")
    print(f"\n⚠️  IMPORTANT: Change the password after first login!")
    print(f"\n🔗 Admin Login: http://localhost:3000/admin/login")
    print(f"🔗 API Endpoint: http://localhost:8000/api/v1/admin/auth/login")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(create_admin())
