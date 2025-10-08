"""
Stripe Configuration Verification Script
Verifies that all Stripe products, prices, and coupons are correctly configured
"""

import stripe
import os
from dotenv import load_dotenv
from typing import Dict, List

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')


def check_stripe_connection():
    """Verify Stripe API connection"""
    try:
        stripe.Account.retrieve()
        print("✅ Stripe API connection successful")
        print(f"   Mode: {'TEST' if 'test' in stripe.api_key else 'LIVE'}")
        return True
    except stripe.error.AuthenticationError:
        print("❌ Stripe API key is invalid")
        return False
    except Exception as e:
        print(f"❌ Error connecting to Stripe: {str(e)}")
        return False


def verify_products():
    """Verify all subscription products exist"""
    print("\n🔍 Verifying Products...")
    print("=" * 60)

    expected_products = ["starter", "pro", "pro-plus"]
    found_products = {}

    try:
        products = stripe.Product.list(limit=100)

        for product in products.data:
            plan_id = product.metadata.get('plan_id', '')
            if plan_id in expected_products:
                found_products[plan_id] = product
                print(f"✅ Found: {product.name}")
                print(f"   Product ID: {product.id}")
                print(f"   Plan ID: {plan_id}")

        # Check for missing products
        missing = set(expected_products) - set(found_products.keys())
        if missing:
            print(f"\n⚠️  Missing products: {', '.join(missing)}")
            return found_products, False

        print(f"\n✅ All {len(expected_products)} products found")
        return found_products, True

    except Exception as e:
        print(f"❌ Error verifying products: {str(e)}")
        return {}, False


def verify_prices(products: Dict):
    """Verify all prices for products"""
    print("\n🔍 Verifying Prices...")
    print("=" * 60)

    all_prices_found = True
    price_mapping = {}

    for plan_id, product in products.items():
        try:
            prices = stripe.Price.list(product=product.id, limit=10)

            monthly_price = None
            yearly_price = None

            for price in prices.data:
                if price.recurring.interval == "month":
                    monthly_price = price
                elif price.recurring.interval == "year":
                    yearly_price = price

            if monthly_price and yearly_price:
                print(f"\n✅ {plan_id.upper()}")
                print(f"   Monthly: ${monthly_price.unit_amount/100}/month (ID: {monthly_price.id})")
                print(f"   Yearly:  ${yearly_price.unit_amount/100}/year (ID: {yearly_price.id})")

                # Calculate savings
                yearly_equivalent = (monthly_price.unit_amount * 12)
                savings = (yearly_equivalent - yearly_price.unit_amount) / 100
                print(f"   Yearly Savings: ${savings:.2f}/year")

                price_mapping[f"{plan_id}_monthly"] = monthly_price.id
                price_mapping[f"{plan_id}_yearly"] = yearly_price.id
            else:
                print(f"\n⚠️  {plan_id.upper()}: Missing prices")
                if not monthly_price:
                    print("   Missing monthly price")
                if not yearly_price:
                    print("   Missing yearly price")
                all_prices_found = False

        except Exception as e:
            print(f"❌ Error verifying prices for {plan_id}: {str(e)}")
            all_prices_found = False

    if all_prices_found:
        print(f"\n✅ All prices configured correctly")

    return price_mapping, all_prices_found


def verify_coupons():
    """Verify all coupons exist"""
    print("\n🔍 Verifying Coupons...")
    print("=" * 60)

    expected_coupons = ["SAVE30", "EARLYBIRD", "WELCOME10", "FIRSTMONTH50", "LOYALTY15"]
    found_coupons = {}

    try:
        coupons = stripe.Coupon.list(limit=100)

        for coupon in coupons.data:
            if coupon.id in expected_coupons:
                found_coupons[coupon.id] = coupon
                print(f"\n✅ {coupon.id}")
                print(f"   Discount: {coupon.percent_off}% off")
                print(f"   Duration: {coupon.duration}")
                if coupon.max_redemptions:
                    print(f"   Max Redemptions: {coupon.max_redemptions}")
                    if coupon.times_redeemed:
                        print(f"   Times Redeemed: {coupon.times_redeemed}")
                print(f"   Valid: {coupon.valid}")

        # Check for missing coupons
        missing = set(expected_coupons) - set(found_coupons.keys())
        if missing:
            print(f"\n⚠️  Missing coupons: {', '.join(missing)}")
            return found_coupons, False

        print(f"\n✅ All {len(expected_coupons)} coupons found")
        return found_coupons, True

    except Exception as e:
        print(f"❌ Error verifying coupons: {str(e)}")
        return {}, False


def verify_addons():
    """Verify add-on products"""
    print("\n🔍 Verifying Add-ons...")
    print("=" * 60)

    try:
        products = stripe.Product.list(limit=100)
        addons = []

        for product in products.data:
            if product.metadata.get('type') == 'addon':
                addons.append(product)

                # Get price
                prices = stripe.Price.list(product=product.id, limit=1)
                price = prices.data[0] if prices.data else None

                print(f"\n✅ {product.name}")
                print(f"   Product ID: {product.id}")
                if price:
                    print(f"   Price: ${price.unit_amount/100}")
                    print(f"   Price ID: {price.id}")

        if addons:
            print(f"\n✅ Found {len(addons)} add-on products")
        else:
            print("\n⚠️  No add-on products found")

        return len(addons) > 0

    except Exception as e:
        print(f"❌ Error verifying add-ons: {str(e)}")
        return False


def generate_env_config(price_mapping: Dict):
    """Generate environment configuration"""
    print("\n📝 Generated Configuration for .env")
    print("=" * 60)

    print("\n# Add these to your backend .env file:")
    for key, value in price_mapping.items():
        env_key = f"STRIPE_PRICE_{key.upper()}"
        print(f"{env_key}={value}")

    print("\n# Or update price_mapping in subscriptions.py:")
    print("price_mapping = {")
    for key, value in price_mapping.items():
        print(f'    "{key}": "{value}",')
    print("}")


def run_verification():
    """Run all verification checks"""
    print("\n" + "=" * 60)
    print("🎯 STRIPE CONFIGURATION VERIFICATION")
    print("=" * 60)

    # Check connection
    if not check_stripe_connection():
        print("\n❌ Verification failed: Cannot connect to Stripe")
        return False

    # Verify products
    products, products_ok = verify_products()

    # Verify prices
    price_mapping, prices_ok = verify_prices(products)

    # Verify coupons
    coupons, coupons_ok = verify_coupons()

    # Verify add-ons
    addons_ok = verify_addons()

    # Generate config
    if price_mapping:
        generate_env_config(price_mapping)

    # Final summary
    print("\n\n" + "=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 60)

    checks = [
        ("Products", products_ok),
        ("Prices", prices_ok),
        ("Coupons", coupons_ok),
        ("Add-ons", addons_ok)
    ]

    for check_name, status in checks:
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {check_name}: {'PASS' if status else 'FAIL'}")

    all_passed = all(status for _, status in checks)

    if all_passed:
        print("\n✨ All checks passed! Your Stripe configuration is ready.")
    else:
        print("\n⚠️  Some checks failed. Run setup_stripe_products.py to fix.")

    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    try:
        if not stripe.api_key:
            print("❌ Error: STRIPE_SECRET_KEY not found in environment variables")
            print("   Please add it to your .env file")
            exit(1)

        success = run_verification()
        exit(0 if success else 1)

    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        exit(1)
