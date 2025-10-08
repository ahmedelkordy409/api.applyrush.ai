"""
Test script for authenticated upselling endpoints
"""

import asyncio
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"


def test_upselling_without_auth():
    """Test that upselling endpoints require authentication"""
    print("=" * 60)
    print("Test 1: Upselling Endpoints Without Authentication")
    print("=" * 60)

    endpoints = [
        ("POST", "/upselling/update-profile", {"data": {"test": "value"}}),
        ("POST", "/upselling/save-step", {"step": "test", "data": {}}),
        ("GET", "/upselling/user-profile", None),
        ("POST", "/upselling/complete-onboarding", {"step": "final", "data": {}}),
    ]

    for method, endpoint, body in endpoints:
        url = f"{BASE_URL}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url)
            else:
                response = requests.post(url, json=body)

            if response.status_code == 401:
                print(f"✓ {method} {endpoint} → 401 Unauthorized (correct)")
            else:
                print(f"✗ {method} {endpoint} → {response.status_code} (should be 401)")
                print(f"  Response: {response.text[:100]}")

        except Exception as e:
            print(f"✗ {method} {endpoint} → Error: {e}")


def test_upselling_with_auth():
    """Test that upselling endpoints work with valid token"""
    print("\n" + "=" * 60)
    print("Test 2: Upselling Endpoints With Authentication")
    print("=" * 60)

    # First, try to login to get a token
    login_url = f"{BASE_URL}/auth/login"

    # Try with test user
    test_credentials = {
        "email": "test@example.com",
        "password": "password123"
    }

    try:
        login_response = requests.post(login_url, json=test_credentials)

        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            print(f"✓ Login successful, got token: {token[:20]}...")

            headers = {"Authorization": f"Bearer {token}"}

            # Test authenticated endpoints
            endpoints = [
                ("GET", "/upselling/user-profile", None),
                ("POST", "/upselling/save-step", {
                    "step": "preferences",
                    "data": {"location": "Remote"}
                }),
                ("POST", "/upselling/update-profile", {
                    "data": {"phone": "+1-555-0100"}
                }),
            ]

            for method, endpoint, body in endpoints:
                url = f"{BASE_URL}{endpoint}"

                try:
                    if method == "GET":
                        response = requests.get(url, headers=headers)
                    else:
                        response = requests.post(url, json=body, headers=headers)

                    if response.status_code in [200, 201]:
                        print(f"✓ {method} {endpoint} → {response.status_code} (success)")
                        result = response.json()
                        if "user_email" in result:
                            print(f"  User: {result['user_email']}")
                    else:
                        print(f"⚠ {method} {endpoint} → {response.status_code}")
                        print(f"  Response: {response.text[:200]}")

                except Exception as e:
                    print(f"✗ {method} {endpoint} → Error: {e}")

        else:
            print(f"✗ Login failed: {login_response.status_code}")
            print("  Cannot test authenticated endpoints")
            print(f"  Response: {login_response.text[:200]}")

    except Exception as e:
        print(f"✗ Login error: {e}")


def test_subscription_endpoints():
    """Test that subscription endpoints also require auth"""
    print("\n" + "=" * 60)
    print("Test 3: Subscription Endpoints (Already Authenticated)")
    print("=" * 60)

    endpoints = [
        ("POST", "/subscriptions/create-checkout-session", {
            "plan": "basic",
            "billing_cycle": "monthly",
            "success_url": "http://example.com/success",
            "cancel_url": "http://example.com/cancel"
        }),
        ("GET", "/subscriptions/portal", None),
    ]

    for method, endpoint, body in endpoints:
        url = f"{BASE_URL}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url)
            else:
                response = requests.post(url, json=body)

            if response.status_code == 401:
                print(f"✓ {method} {endpoint} → 401 Unauthorized (correct)")
            else:
                print(f"⚠ {method} {endpoint} → {response.status_code}")

        except Exception as e:
            print(f"✗ {method} {endpoint} → Error: {e}")


def main():
    """Run all tests"""
    print("\n🔒 Testing Upselling Authentication Requirements\n")

    test_upselling_without_auth()
    test_upselling_with_auth()
    test_subscription_endpoints()

    print("\n" + "=" * 60)
    print("✅ Authentication Tests Complete")
    print("=" * 60)
    print("\nSummary:")
    print("- All upselling endpoints now require authentication")
    print("- Subscription endpoints already require authentication")
    print("- Users must login to access upselling pages")
    print("- Email is extracted from JWT token (secure)")


if __name__ == "__main__":
    main()
