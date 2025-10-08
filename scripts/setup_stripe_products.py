"""
Stripe Product, Price, and Coupon Setup Script
Creates all necessary Stripe products, pricing, and coupon codes
"""

import stripe
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def create_products_and_prices():
    """Create Stripe products and prices"""

    print("🚀 Creating Stripe Products and Prices...")
    print("=" * 60)

    # Define products and their prices
    products_config = [
        {
            "name": "Starter Plan",
            "description": "40 applications/day with GPT-4 Mini AI and basic analytics",
            "plan_id": "starter",
            "monthly_price": 2000,  # $20.00 in cents
            "yearly_price": 20000,  # $200.00 in cents (save $40/year)
            "features": [
                "40 applications per day",
                "GPT-4 Mini AI model",
                "Basic analytics",
                "Email support"
            ]
        },
        {
            "name": "Pro Plan",
            "description": "60 applications/day with GPT-4.1 Mini AI, priority support, and advanced analytics",
            "plan_id": "pro",
            "monthly_price": 5000,  # $50.00 in cents
            "yearly_price": 50000,  # $500.00 in cents (save $100/year)
            "features": [
                "60 applications per day",
                "GPT-4.1 Mini AI model",
                "Advanced analytics",
                "Priority support",
                "Resume customization included"
            ]
        },
        {
            "name": "Pro+ Plan",
            "description": "Unlimited applications with premium AI models, 24/7 support, and all features",
            "plan_id": "pro-plus",
            "monthly_price": 9900,  # $99.00 in cents
            "yearly_price": 99000,  # $990.00 in cents (save $198/year)
            "features": [
                "Unlimited applications",
                "Premium AI models",
                "24/7 priority support",
                "API access",
                "All features included"
            ]
        }
    ]

    created_products = {}

    for config in products_config:
        try:
            # Create product
            product = stripe.Product.create(
                name=config["name"],
                description=config["description"],
                metadata={
                    "plan_id": config["plan_id"],
                    "features": ", ".join(config["features"])
                }
            )

            print(f"\n✅ Created Product: {config['name']}")
            print(f"   Product ID: {product.id}")

            # Create monthly price
            monthly_price = stripe.Price.create(
                product=product.id,
                unit_amount=config["monthly_price"],
                currency="usd",
                recurring={"interval": "month"},
                metadata={
                    "plan_id": config["plan_id"],
                    "billing_cycle": "monthly"
                }
            )

            print(f"   Monthly Price ID: {monthly_price.id} (${config['monthly_price']/100}/month)")

            # Create yearly price
            yearly_price = stripe.Price.create(
                product=product.id,
                unit_amount=config["yearly_price"],
                currency="usd",
                recurring={"interval": "year"},
                metadata={
                    "plan_id": config["plan_id"],
                    "billing_cycle": "yearly"
                }
            )

            savings = (config["monthly_price"] * 12 - config["yearly_price"]) / 100
            print(f"   Yearly Price ID: {yearly_price.id} (${config['yearly_price']/100}/year, save ${savings}/year)")

            created_products[config["plan_id"]] = {
                "product_id": product.id,
                "monthly_price_id": monthly_price.id,
                "yearly_price_id": yearly_price.id
            }

        except stripe.error.StripeError as e:
            print(f"❌ Error creating {config['name']}: {str(e)}")

    return created_products


def create_coupons():
    """Create Stripe coupons"""

    print("\n\n💳 Creating Stripe Coupons...")
    print("=" * 60)

    coupons_config = [
        {
            "id": "SAVE30",
            "percent_off": 30,
            "duration": "once",
            "name": "Save 30% Off",
            "max_redemptions": None,
        },
        {
            "id": "EARLYBIRD",
            "percent_off": 20,
            "duration": "once",
            "name": "Early Bird 20% Discount",
            "max_redemptions": 100,
        },
        {
            "id": "WELCOME10",
            "percent_off": 10,
            "duration": "once",
            "name": "Welcome 10% Discount",
            "max_redemptions": None,
        },
        {
            "id": "FIRSTMONTH50",
            "percent_off": 50,
            "duration": "once",
            "name": "50% Off First Month",
            "max_redemptions": 50,
        },
        {
            "id": "LOYALTY15",
            "percent_off": 15,
            "duration": "repeating",
            "duration_in_months": 3,
            "name": "Loyalty 15% for 3 Months",
            "max_redemptions": None,
        }
    ]

    created_coupons = []

    for config in coupons_config:
        try:
            coupon_params = {
                "id": config["id"],
                "percent_off": config["percent_off"],
                "duration": config["duration"],
                "name": config["name"],
            }

            if config.get("max_redemptions"):
                coupon_params["max_redemptions"] = config["max_redemptions"]

            if config["duration"] == "repeating":
                coupon_params["duration_in_months"] = config.get("duration_in_months", 3)

            coupon = stripe.Coupon.create(**coupon_params)

            print(f"\n✅ Created Coupon: {config['name']}")
            print(f"   Coupon Code: {config['id']}")
            print(f"   Discount: {config['percent_off']}% off")
            print(f"   Duration: {config['duration']}")
            if config.get("max_redemptions"):
                print(f"   Max Redemptions: {config['max_redemptions']}")

            created_coupons.append(config["id"])

        except stripe.error.StripeError as e:
            if "already exists" in str(e):
                print(f"⚠️  Coupon {config['id']} already exists, skipping...")
            else:
                print(f"❌ Error creating coupon {config['id']}: {str(e)}")

    return created_coupons


def create_addons():
    """Create add-on products (one-time purchases or add-ons to subscriptions)"""

    print("\n\n🎁 Creating Add-on Products...")
    print("=" * 60)

    addons_config = [
        {
            "name": "Resume Review Service",
            "description": "Professional resume review by career experts",
            "price": 4900,  # $49.00
            "type": "one_time"
        },
        {
            "name": "Interview Coaching Session",
            "description": "1-hour one-on-one interview coaching",
            "price": 9900,  # $99.00
            "type": "one_time"
        },
        {
            "name": "LinkedIn Profile Optimization",
            "description": "Professional LinkedIn profile optimization",
            "price": 7900,  # $79.00
            "type": "one_time"
        },
        {
            "name": "Extra Applications Bundle",
            "description": "Additional 100 applications credit",
            "price": 1900,  # $19.00
            "type": "recurring"
        }
    ]

    created_addons = {}

    for config in addons_config:
        try:
            # Create addon product
            product = stripe.Product.create(
                name=config["name"],
                description=config["description"],
                metadata={"type": "addon"}
            )

            print(f"\n✅ Created Add-on: {config['name']}")
            print(f"   Product ID: {product.id}")

            # Create price
            price_params = {
                "product": product.id,
                "unit_amount": config["price"],
                "currency": "usd",
            }

            if config["type"] == "recurring":
                price_params["recurring"] = {"interval": "month"}

            price = stripe.Price.create(**price_params)

            print(f"   Price ID: {price.id} (${config['price']/100})")

            created_addons[config["name"]] = {
                "product_id": product.id,
                "price_id": price.id
            }

        except stripe.error.StripeError as e:
            print(f"❌ Error creating addon {config['name']}: {str(e)}")

    return created_addons


def print_configuration_summary(products, coupons, addons):
    """Print a summary of all created resources"""

    print("\n\n" + "=" * 60)
    print("📋 CONFIGURATION SUMMARY")
    print("=" * 60)

    print("\n🎯 Subscription Products:")
    for plan_id, details in products.items():
        print(f"\n{plan_id.upper()}:")
        print(f"  Product ID: {details['product_id']}")
        print(f"  Monthly Price ID: {details['monthly_price_id']}")
        print(f"  Yearly Price ID: {details['yearly_price_id']}")

    print("\n💳 Coupons:")
    for coupon_code in coupons:
        print(f"  - {coupon_code}")

    print("\n🎁 Add-ons:")
    for addon_name, details in addons.items():
        print(f"\n{addon_name}:")
        print(f"  Product ID: {details['product_id']}")
        print(f"  Price ID: {details['price_id']}")

    print("\n" + "=" * 60)
    print("✨ Setup Complete! Update your .env file with these IDs")
    print("=" * 60)


if __name__ == "__main__":
    try:
        print("\n🎯 ApplyRush.AI - Stripe Setup Script")
        print("=" * 60)

        # Check if Stripe key is configured
        if not stripe.api_key:
            print("❌ Error: STRIPE_SECRET_KEY not found in environment variables")
            print("   Please add it to your .env file")
            exit(1)

        print(f"✅ Stripe API Key loaded")
        print(f"   Mode: {'TEST' if 'test' in stripe.api_key else 'LIVE'}")

        # Create products and prices
        products = create_products_and_prices()

        # Create coupons
        coupons = create_coupons()

        # Create add-ons
        addons = create_addons()

        # Print summary
        print_configuration_summary(products, coupons, addons)

    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        exit(1)
