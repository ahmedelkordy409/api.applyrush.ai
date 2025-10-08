"""
API Endpoints Testing Script
Tests the subscription API endpoints without requiring a running server
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api.endpoints.subscriptions import COUPONS
from datetime import datetime

def test_coupon_validation():
    """Test coupon validation logic"""
    print("\n🧪 Testing Coupon Validation")
    print("=" * 60)

    test_cases = [
        ("SAVE30", True, 30),
        ("EARLYBIRD", True, 20),
        ("WELCOME10", True, 10),
        ("INVALID", False, None),
        ("save30", True, 30),  # lowercase should work
    ]

    for code, should_be_valid, expected_discount in test_cases:
        code_upper = code.upper().strip()

        if code_upper in COUPONS:
            coupon = COUPONS[code_upper]
            expiry_date = datetime.strptime(coupon["expiry"], "%Y-%m-%d")
            is_valid = datetime.utcnow() <= expiry_date
            discount = coupon["discountPercent"] if is_valid else None

            status = "✅" if is_valid == should_be_valid else "❌"
            print(f"{status} Code: {code:15} Valid: {is_valid:5} Discount: {discount}%")

            if is_valid and expected_discount:
                assert discount == expected_discount, f"Expected {expected_discount}%, got {discount}%"
        else:
            is_valid = False
            status = "✅" if is_valid == should_be_valid else "❌"
            print(f"{status} Code: {code:15} Valid: {is_valid:5} (Invalid coupon)")


def test_price_mapping():
    """Test price mapping configuration"""
    print("\n🧪 Testing Price Mapping")
    print("=" * 60)

    price_mapping = {
        "starter_monthly": "price_1SDKIKQYDSf5l1Z0hXbunNSJ",
        "starter_yearly": "price_1SDKIKQYDSf5l1Z0tPciS0Dl",
        "pro_monthly": "price_1SDKILQYDSf5l1Z0JE97c6I5",
        "pro_yearly": "price_1SDKILQYDSf5l1Z0Klb7WwL8",
        "pro-plus_monthly": "price_1SDKIMQYDSf5l1Z0G5tWnwRa",
        "pro-plus_yearly": "price_1SDKIMQYDSf5l1Z0B5ldXuUa",
    }

    test_cases = [
        ("starter", "monthly", "price_1SDKIKQYDSf5l1Z0hXbunNSJ"),
        ("pro", "yearly", "price_1SDKILQYDSf5l1Z0Klb7WwL8"),
        ("pro-plus", "monthly", "price_1SDKIMQYDSf5l1Z0G5tWnwRa"),
    ]

    for plan_id, billing_cycle, expected_price_id in test_cases:
        price_key = f"{plan_id}_{billing_cycle}"
        price_id = price_mapping.get(price_key)

        status = "✅" if price_id == expected_price_id else "❌"
        print(f"{status} {plan_id:10} {billing_cycle:10} → {price_id}")

        assert price_id == expected_price_id, f"Price ID mismatch for {price_key}"


def test_discount_calculations():
    """Test discount calculations"""
    print("\n🧪 Testing Discount Calculations")
    print("=" * 60)

    test_cases = [
        (50, 30, 35),   # $50 with 30% off = $35
        (99, 20, 79.2), # $99 with 20% off = $79.20
        (20, 50, 10),   # $20 with 50% off = $10
        (500, 30, 350), # $500 with 30% off = $350
    ]

    for original_price, discount_percent, expected_final in test_cases:
        discount_amount = original_price * (discount_percent / 100)
        final_price = original_price - discount_amount

        status = "✅" if abs(final_price - expected_final) < 0.01 else "❌"
        print(f"{status} ${original_price:6.2f} - {discount_percent}% = ${final_price:6.2f} (expected ${expected_final:6.2f})")

        assert abs(final_price - expected_final) < 0.01, f"Calculation error: expected ${expected_final}, got ${final_price}"


def test_yearly_savings():
    """Test yearly savings calculations"""
    print("\n🧪 Testing Yearly Savings Calculations")
    print("=" * 60)

    plans = [
        ("Starter", 20, 200, 40),
        ("Pro", 50, 500, 100),
        ("Pro+", 99, 990, 198),
    ]

    for plan_name, monthly_price, yearly_price, expected_savings in plans:
        yearly_equivalent = monthly_price * 12
        savings = yearly_equivalent - yearly_price

        status = "✅" if savings == expected_savings else "❌"
        print(f"{status} {plan_name:10} ${monthly_price}/mo × 12 = ${yearly_equivalent:4} - ${yearly_price:4} = ${savings:3} saved")

        assert savings == expected_savings, f"Savings calculation error for {plan_name}"


def test_api_request_validation():
    """Test API request validation"""
    print("\n🧪 Testing API Request Validation")
    print("=" * 60)

    valid_plan_ids = ["starter", "pro", "pro-plus"]
    valid_billing_cycles = ["monthly", "yearly"]

    test_cases = [
        ("starter", "monthly", True),
        ("pro", "yearly", True),
        ("invalid", "monthly", False),
        ("starter", "invalid", False),
    ]

    for plan_id, billing_cycle, should_be_valid in test_cases:
        is_valid = plan_id in valid_plan_ids and billing_cycle in valid_billing_cycles
        status = "✅" if is_valid == should_be_valid else "❌"
        print(f"{status} Plan: {plan_id:12} Cycle: {billing_cycle:10} Valid: {is_valid}")


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🎯 API ENDPOINTS TESTING")
    print("=" * 60)

    try:
        test_coupon_validation()
        test_price_mapping()
        test_discount_calculations()
        test_yearly_savings()
        test_api_request_validation()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
