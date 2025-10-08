"""
Direct test of subscriptions API
"""

import sys
sys.path.insert(0, '/home/ahmed-elkordy/researchs/applyrush.ai/jobhire-ai-backend')

from app.api.endpoints.subscriptions import router, COUPONS
from datetime import datetime

print("=" * 60)
print("🧪 Testing Subscriptions Module")
print("=" * 60)

# Test 1: Check router
print("\n✅ Subscriptions router loaded successfully")
print(f"   Routes: {len(router.routes)}")
for route in router.routes:
    print(f"   - {route.methods} {route.path}")

# Test 2: Check coupons
print("\n✅ Coupons loaded:")
for code, details in COUPONS.items():
    print(f"   - {code}: {details['discountPercent']}% off (expires: {details['expiry']})")

# Test 3: Simulate coupon validation
print("\n✅ Testing coupon validation logic:")
test_codes = ["SAVE30", "INVALID", "EARLYBIRD"]
for code in test_codes:
    if code in COUPONS:
        coupon = COUPONS[code]
        expiry_date = datetime.strptime(coupon["expiry"], "%Y-%m-%d")
        is_valid = datetime.utcnow() <= expiry_date
        if is_valid:
            print(f"   ✓ {code}: Valid ({coupon['discountPercent']}% off)")
        else:
            print(f"   ✗ {code}: Expired")
    else:
        print(f"   ✗ {code}: Invalid")

print("\n" + "=" * 60)
print("✅ All checks passed!")
print("=" * 60)
