"""
Script to create Stripe products and prices for ApplyRush.AI subscription plans
"""
import stripe
import os
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Define your plans
plans = {
    "starter": {
        "name": "Starter Plan",
        "description": "Perfect for getting started with job applications",
        "monthly_price": 2900,  # $29.00 in cents
        "yearly_price": 29000,  # $290.00 in cents ($24.17/month)
    },
    "pro": {
        "name": "Pro Plan",
        "description": "Unlimited applications and premium features",
        "monthly_price": 4900,  # $49.00 in cents
        "yearly_price": 49000,  # $490.00 in cents ($40.83/month)
    },
    "pro-plus": {
        "name": "Pro Plus Plan",
        "description": "Everything in Pro + priority support and dedicated account manager",
        "monthly_price": 9900,  # $99.00 in cents
        "yearly_price": 99000,  # $990.00 in cents ($82.50/month)
    }
}

print("=" * 60)
print("Creating Stripe Products and Prices")
print("=" * 60)
print()

env_lines = []

for plan_id, plan_data in plans.items():
    print(f"Creating {plan_data['name']}...")

    # Create product
    product = stripe.Product.create(
        name=plan_data['name'],
        description=plan_data['description'],
        metadata={
            "plan_id": plan_id
        }
    )

    print(f"  ✓ Product created: {product.id}")

    # Create monthly price
    monthly_price = stripe.Price.create(
        product=product.id,
        unit_amount=plan_data['monthly_price'],
        currency='usd',
        recurring={
            'interval': 'month',
            'interval_count': 1,
        },
        metadata={
            "plan_id": plan_id,
            "billing_cycle": "monthly"
        }
    )

    print(f"  ✓ Monthly price created: {monthly_price.id} (${plan_data['monthly_price']/100:.2f}/mo)")

    # Create yearly price
    yearly_price = stripe.Price.create(
        product=product.id,
        unit_amount=plan_data['yearly_price'],
        currency='usd',
        recurring={
            'interval': 'year',
            'interval_count': 1,
        },
        metadata={
            "plan_id": plan_id,
            "billing_cycle": "yearly"
        }
    )

    print(f"  ✓ Yearly price created: {yearly_price.id} (${plan_data['yearly_price']/100:.2f}/yr)")
    print()

    # Store for .env
    env_key_monthly = f"STRIPE_{plan_id.upper().replace('-', '_')}_MONTHLY_PRICE_ID"
    env_key_yearly = f"STRIPE_{plan_id.upper().replace('-', '_')}_YEARLY_PRICE_ID"

    env_lines.append(f"{env_key_monthly}={monthly_price.id}")
    env_lines.append(f"{env_key_yearly}={yearly_price.id}")

print("=" * 60)
print("✓ All products and prices created successfully!")
print("=" * 60)
print()
print("Add these to your .env file:")
print()
for line in env_lines:
    print(line)
print()
print("=" * 60)
