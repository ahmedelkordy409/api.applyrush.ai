"""
Test to verify all endpoints are in Swagger documentation
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def test_swagger_endpoints():
    """Verify all expected endpoints are in Swagger"""
    print("=" * 60)
    print("Testing Swagger Documentation")
    print("=" * 60)

    # Get OpenAPI spec
    response = requests.get(f"{BASE_URL}/openapi.json")

    if response.status_code != 200:
        print(f"✗ Failed to get OpenAPI spec: {response.status_code}")
        return

    openapi = response.json()
    paths = openapi.get("paths", {})

    print(f"\n✅ Total Endpoints: {len(paths)}")

    # Expected endpoints by category
    expected_categories = {
        "Authentication": [
            "/api/v1/auth/login",
            "/api/v1/auth/signup",
            "/api/v1/auth/refresh",
            "/api/v1/auth/me",
        ],
        "Upselling": [
            "/api/v1/upselling/save-step",
            "/api/v1/upselling/update-profile",
            "/api/v1/upselling/user-profile",
            "/api/v1/upselling/complete-onboarding",
        ],
        "Resumes": [
            "/api/v1/resumes/upload",
            "/api/v1/resumes/upload-guest",
            "/api/v1/resumes/",
            "/api/v1/resumes/{resume_id}",
        ],
        "Subscriptions": [
            "/api/v1/subscriptions/create-checkout-session",
            "/api/v1/subscriptions/portal",
            "/api/v1/subscriptions/webhook",
        ],
        "Auto-Apply": [
            "/api/v1/auto-apply/queue/start",
            "/api/v1/auto-apply/queue/stop",
            "/api/v1/auto-apply/queue/status",
        ],
    }

    # Check each category
    total_found = 0
    total_expected = 0

    for category, endpoints in expected_categories.items():
        found = sum(1 for ep in endpoints if ep in paths)
        total = len(endpoints)
        total_found += found
        total_expected += total

        status = "✓" if found == total else "✗"
        print(f"\n{status} {category}: {found}/{total} endpoints")

        # Show missing endpoints
        for endpoint in endpoints:
            if endpoint not in paths:
                print(f"  ✗ Missing: {endpoint}")

    print(f"\n{'='*60}")
    print(f"Summary: {total_found}/{total_expected} expected endpoints found")
    print(f"Total endpoints in system: {len(paths)}")

    # Show new endpoints we've added today
    print(f"\n{'='*60}")
    print("New Endpoints Added Today:")
    print(f"{'='*60}")

    new_endpoints = [
        "/api/v1/upselling/save-step",
        "/api/v1/upselling/update-profile",
        "/api/v1/upselling/user-profile",
        "/api/v1/upselling/complete-onboarding",
    ]

    for endpoint in new_endpoints:
        if endpoint in paths:
            methods = list(paths[endpoint].keys())
            print(f"✓ {endpoint} [{', '.join(m.upper() for m in methods)}]")
        else:
            print(f"✗ {endpoint} [MISSING]")

    return len(paths)


def test_swagger_ui_accessible():
    """Test that Swagger UI is accessible"""
    print(f"\n{'='*60}")
    print("Testing Swagger UI Accessibility")
    print(f"{'='*60}")

    endpoints_to_test = [
        ("/docs", "Swagger UI"),
        ("/redoc", "ReDoc"),
        ("/openapi.json", "OpenAPI Spec"),
    ]

    for endpoint, name in endpoints_to_test:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"✓ {name} accessible at {endpoint}")
            else:
                print(f"✗ {name} returned {response.status_code}")
        except Exception as e:
            print(f"✗ {name} error: {e}")


def main():
    """Run all tests"""
    print("\n🔍 Swagger Documentation Verification\n")

    try:
        endpoint_count = test_swagger_endpoints()
        test_swagger_ui_accessible()

        print(f"\n{'='*60}")
        print("✅ All Tests Complete!")
        print(f"{'='*60}")
        print(f"\nSwagger UI: http://localhost:8000/docs")
        print(f"ReDoc: http://localhost:8000/redoc")
        print(f"OpenAPI JSON: http://localhost:8000/openapi.json")
        print(f"\nTotal Endpoints Documented: {endpoint_count}")

    except Exception as e:
        print(f"\n❌ Test Error: {e}")


if __name__ == "__main__":
    main()
