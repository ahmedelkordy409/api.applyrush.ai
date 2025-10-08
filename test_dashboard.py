#!/usr/bin/env python3
"""
Test dashboard endpoints with real user token
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Test user credentials
TEST_EMAIL = "kobew70224@ampdial.com"
TEST_PASSWORD = "password123"  # Adjust if different
BASE_URL = "http://localhost:8000/api/v1"

print("=" * 60)
print("DASHBOARD ENDPOINTS TEST")
print("=" * 60)

# 1. Login to get token
print("\n🔐 Step 1: Logging in...")
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
)

if login_response.status_code != 200:
    print(f"❌ Login failed: {login_response.status_code}")
    print(f"Response: {login_response.text}")
    exit(1)

token = login_response.json().get("access_token")
user_id = login_response.json().get("user", {}).get("id")
print(f"✅ Login successful! User ID: {user_id}")

# Headers with auth token
headers = {"Authorization": f"Bearer {token}"}

# 2. Test dashboard summary
print("\n📊 Step 2: Testing /dashboard/summary...")
summary_response = requests.get(f"{BASE_URL}/dashboard/summary", headers=headers)

if summary_response.status_code == 200:
    data = summary_response.json()
    print(f"✅ Summary endpoint working!")
    print(f"   Preview (matched): {data['summary']['preview']}")
    print(f"   Queue (pending): {data['summary']['queue']}")
    print(f"   Completed (applied): {data['summary']['completed']}")
    print(f"   Cached: {data.get('cached', False)}")
else:
    print(f"❌ Summary failed: {summary_response.status_code}")
    print(f"Response: {summary_response.text}")

# 3. Test increase items
print("\n⭐ Step 3: Testing /dashboard/increase-items...")
items_response = requests.get(f"{BASE_URL}/dashboard/increase-items", headers=headers)

if items_response.status_code == 200:
    data = items_response.json()
    print(f"✅ Increase items endpoint working!")
    print(f"   Total gain: {data.get('total_gain', 0)}%")
    print(f"   Completion: {data.get('completion_percentage', 0)}%")
    for item in data.get('items', []):
        status = "✓" if item.get('completed') else "○"
        print(f"   {status} {item['label']} (+{item['gain']}%)")
else:
    print(f"❌ Increase items failed: {items_response.status_code}")
    print(f"Response: {items_response.text}")

# 4. Test getting started text
print("\n📝 Step 4: Testing /dashboard/getting-started...")
text_response = requests.get(f"{BASE_URL}/dashboard/getting-started", headers=headers)

if text_response.status_code == 200:
    data = text_response.json()
    print(f"✅ Getting started endpoint working!")
    print(f"   Text: {data.get('text', '')[:100]}...")
    print(f"   Total apps: {data.get('stats', {}).get('total_applications', 0)}")
    print(f"   New matches: {data.get('stats', {}).get('new_matches', 0)}")
else:
    print(f"❌ Getting started failed: {text_response.status_code}")
    print(f"Response: {text_response.text}")

# 5. Test application stats
print(f"\n📈 Step 5: Testing /dashboard/stats?userId={user_id}...")
stats_response = requests.get(
    f"{BASE_URL}/dashboard/stats",
    headers=headers,
    params={"userId": user_id}
)

if stats_response.status_code == 200:
    data = stats_response.json()
    print(f"✅ Stats endpoint working!")
    print(f"   Total applications: {data['stats']['totalApplications']}")
    print(f"   This week: {data['stats']['thisWeek']}")
    print(f"   This month: {data['stats']['thisMonth']}")
    print(f"   Response rate: {data['stats']['responseRate']}%")
    print(f"   Avg response time: {data['stats']['averageResponseTime']} days")
else:
    print(f"❌ Stats failed: {stats_response.status_code}")
    print(f"Response: {stats_response.text}")

# 6. Test cache functionality
print("\n🔄 Step 6: Testing cache (second request should be cached)...")
summary_response_2 = requests.get(f"{BASE_URL}/dashboard/summary", headers=headers)

if summary_response_2.status_code == 200:
    data = summary_response_2.json()
    if data.get('cached'):
        print(f"✅ Caching is working! Second request was cached.")
    else:
        print(f"⚠️  Second request was not cached (might be normal within TTL)")
else:
    print(f"❌ Second summary request failed: {summary_response_2.status_code}")

# 7. Test health check
print("\n❤️  Step 7: Testing /dashboard/health...")
health_response = requests.get(f"{BASE_URL}/dashboard/health")

if health_response.status_code == 200:
    data = health_response.json()
    print(f"✅ Health check passed!")
    print(f"   Status: {data['status']}")
    print(f"   Cache entries: {data['cache_entries']}")
else:
    print(f"❌ Health check failed: {health_response.status_code}")

print("\n" + "=" * 60)
print("✅ ALL TESTS COMPLETED")
print("=" * 60)
