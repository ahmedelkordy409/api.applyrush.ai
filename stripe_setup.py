"""
Stripe Product and Subscription Setup for ApplyRush.AI
Creates products, prices, add-ons, coupons, and manages subscriptions
"""

import stripe
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any

load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


class StripeSubscriptionManager:
    """Manages all Stripe subscription operations"""

    def __init__(self):
        self.products = {}
        self.prices = {}
        self.addons = {}
        self.coupons = {}

    # ==================== PRODUCT CREATION ====================

    def create_subscription_products(self):
        """Create all subscription plan products"""

        # Free Plan (for tracking, no payment required)
        free_product = stripe.Product.create(
            name="Free Plan",
            description="20 job applications per day with basic features",
            metadata={
                "plan_type": "free",
                "daily_applications": "20",
                "ai_model": "basic",
                "support": "email"
            }
        )
        self.products["free"] = free_product

        # Basic Plan
        basic_product = stripe.Product.create(
            name="Basic Plan",
            description="40 job applications per day with advanced features",
            metadata={
                "plan_type": "basic",
                "daily_applications": "40",
                "ai_model": "gpt-4-mini",
                "support": "email",
                "analytics": "basic"
            }
        )
        self.products["basic"] = basic_product

        # Premium Plan (Recommended)
        premium_product = stripe.Product.create(
            name="Premium Plan",
            description="60 job applications per day with AI-powered matching and priority support",
            metadata={
                "plan_type": "premium",
                "daily_applications": "60",
                "ai_model": "gpt-4.1-mini",
                "support": "priority",
                "analytics": "advanced",
                "resume_customization": "true",
                "recommended": "true"
            }
        )
        self.products["premium"] = premium_product

        # Enterprise Plan
        enterprise_product = stripe.Product.create(
            name="Enterprise Plan",
            description="Unlimited applications with dedicated AI agent and 24/7 support",
            metadata={
                "plan_type": "enterprise",
                "daily_applications": "unlimited",
                "ai_model": "premium",
                "support": "24/7",
                "analytics": "enterprise",
                "api_access": "true"
            }
        )
        self.products["enterprise"] = enterprise_product

        print("✅ Created subscription products")
        return self.products

    def create_subscription_prices(self):
        """Create pricing for all plans (monthly and yearly)"""

        # Basic Plan Prices
        self.prices["basic_monthly"] = stripe.Price.create(
            product=self.products["basic"].id,
            unit_amount=2000,  # $20.00
            currency="usd",
            recurring={"interval": "month"},
            metadata={"billing_cycle": "monthly"}
        )

        self.prices["basic_yearly"] = stripe.Price.create(
            product=self.products["basic"].id,
            unit_amount=20000,  # $200.00 (save $40/year)
            currency="usd",
            recurring={"interval": "year"},
            metadata={"billing_cycle": "yearly", "savings": "40"}
        )

        # Premium Plan Prices
        self.prices["premium_monthly"] = stripe.Price.create(
            product=self.products["premium"].id,
            unit_amount=5000,  # $50.00
            currency="usd",
            recurring={"interval": "month"},
            metadata={"billing_cycle": "monthly"}
        )

        self.prices["premium_yearly"] = stripe.Price.create(
            product=self.products["premium"].id,
            unit_amount=50000,  # $500.00 (save $100/year)
            currency="usd",
            recurring={"interval": "year"},
            metadata={"billing_cycle": "yearly", "savings": "100"}
        )

        # Enterprise Plan Prices
        self.prices["enterprise_monthly"] = stripe.Price.create(
            product=self.products["enterprise"].id,
            unit_amount=9900,  # $99.00
            currency="usd",
            recurring={"interval": "month"},
            metadata={"billing_cycle": "monthly"}
        )

        self.prices["enterprise_yearly"] = stripe.Price.create(
            product=self.products["enterprise"].id,
            unit_amount=99000,  # $990.00 (save $198/year)
            currency="usd",
            recurring={"interval": "year"},
            metadata={"billing_cycle": "yearly", "savings": "198"}
        )

        print("✅ Created subscription prices")
        return self.prices

    # ==================== ADD-ON CREATION ====================

    def create_addon_products(self):
        """Create one-time add-on products"""

        # Resume Customization Add-on
        resume_addon = stripe.Product.create(
            name="AI Resume Customization",
            description="Auto-customize your resume with ATS keywords for each job (+44% more interviews)",
            type="service",
            metadata={
                "addon_type": "resume_customization",
                "benefit": "+44% interview invitations",
                "one_time": "true"
            }
        )
        self.addons["resume_customization"] = resume_addon

        self.prices["resume_addon"] = stripe.Price.create(
            product=resume_addon.id,
            unit_amount=1200,  # $12.00
            currency="usd",
            metadata={"addon_type": "one_time"}
        )

        # Cover Letter Add-on
        cover_letter_addon = stripe.Product.create(
            name="AI Cover Letter Generation",
            description="Generate custom cover letters for every application with AI",
            type="service",
            metadata={
                "addon_type": "cover_letter",
                "benefit": "personalized cover letters",
                "one_time": "true"
            }
        )
        self.addons["cover_letter"] = cover_letter_addon

        self.prices["cover_letter_addon"] = stripe.Price.create(
            product=cover_letter_addon.id,
            unit_amount=1200,  # $12.00
            currency="usd",
            metadata={"addon_type": "one_time"}
        )

        # Priority Access Add-on
        priority_addon = stripe.Product.create(
            name="Priority Job Access",
            description="Get notified about new jobs within the first hour (+36% response rate)",
            type="service",
            metadata={
                "addon_type": "priority_access",
                "benefit": "+36% higher response rate",
                "one_time": "true"
            }
        )
        self.addons["priority_access"] = priority_addon

        self.prices["priority_addon"] = stripe.Price.create(
            product=priority_addon.id,
            unit_amount=1200,  # $12.00
            currency="usd",
            metadata={"addon_type": "one_time"}
        )

        print("✅ Created add-on products")
        return self.addons

    # ==================== COUPON CREATION ====================

    def create_coupons(self):
        """Create promotional coupons"""

        # First month 50% off
        self.coupons["first_month_50"] = stripe.Coupon.create(
            percent_off=50,
            duration="once",
            name="50% Off First Month",
            metadata={"campaign": "first_signup"}
        )

        # Yearly plan discount
        self.coupons["yearly_discount"] = stripe.Coupon.create(
            amount_off=5000,  # $50 off
            duration="once",
            currency="usd",
            name="$50 Off Yearly Plan",
            metadata={"campaign": "yearly_promotion"}
        )

        # Limited time premium upgrade
        self.coupons["premium_limited"] = stripe.Coupon.create(
            percent_off=49,
            duration="once",
            name="Limited Time: $49 Off Premium",
            metadata={"campaign": "premium_upgrade", "original_price": "99"}
        )

        # Bundle discount (3 add-ons)
        self.coupons["addon_bundle"] = stripe.Coupon.create(
            percent_off=25,
            duration="once",
            name="25% Off Add-on Bundle",
            metadata={"campaign": "addon_bundle", "min_addons": "3"}
        )

        print("✅ Created promotional coupons")
        return self.coupons

    # ==================== SUBSCRIPTION MANAGEMENT ====================

    def create_checkout_session(
        self,
        customer_email: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
        trial_days: Optional[int] = None,
        coupon_id: Optional[str] = None
    ):
        """Create Stripe Checkout session for subscription"""

        session_params = {
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            "mode": "subscription",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "customer_email": customer_email,
            "metadata": metadata or {},
            "subscription_data": {
                "metadata": metadata or {}
            }
        }

        # Add trial period if specified
        if trial_days:
            session_params["subscription_data"]["trial_period_days"] = trial_days

        # Add coupon if specified
        if coupon_id:
            session_params["discounts"] = [{"coupon": coupon_id}]

        session = stripe.checkout.Session.create(**session_params)

        return session

    def create_addon_checkout(
        self,
        customer_email: str,
        addon_price_ids: List[str],
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None
    ):
        """Create checkout session for one-time add-on purchases"""

        line_items = [
            {"price": price_id, "quantity": 1}
            for price_id in addon_price_ids
        ]

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",  # One-time payment
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email,
            metadata=metadata or {}
        )

        return session

    def update_subscription(
        self,
        subscription_id: str,
        new_price_id: str,
        prorate: bool = True
    ):
        """Update existing subscription to new plan"""

        subscription = stripe.Subscription.retrieve(subscription_id)

        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False,
            proration_behavior="create_prorations" if prorate else "none",
            items=[{
                "id": subscription["items"]["data"][0].id,
                "price": new_price_id,
            }]
        )

        return subscription

    def cancel_subscription(
        self,
        subscription_id: str,
        immediately: bool = False
    ):
        """Cancel subscription (immediately or at period end)"""

        if immediately:
            subscription = stripe.Subscription.delete(subscription_id)
        else:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )

        return subscription

    def get_customer_subscriptions(self, customer_id: str):
        """Get all subscriptions for a customer"""

        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="all"
        )

        return subscriptions

    def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ):
        """Create a Stripe customer"""

        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {}
        )

        return customer

    # ==================== WEBHOOK HANDLERS ====================

    def handle_checkout_completed(self, session):
        """Handle successful checkout completion"""

        customer_email = session.get("customer_email")
        subscription_id = session.get("subscription")
        metadata = session.get("metadata", {})

        # TODO: Update database
        # db.activate_subscription(metadata["user_id"], subscription_id)

        return {
            "customer_email": customer_email,
            "subscription_id": subscription_id,
            "metadata": metadata
        }

    def handle_subscription_updated(self, subscription):
        """Handle subscription updates (upgrades, downgrades)"""

        customer_id = subscription.get("customer")
        status = subscription.get("status")

        # TODO: Update database
        # db.update_subscription_status(customer_id, status)

        return {
            "customer_id": customer_id,
            "status": status
        }

    def handle_subscription_deleted(self, subscription):
        """Handle subscription cancellation"""

        customer_id = subscription.get("customer")

        # TODO: Update database
        # db.deactivate_subscription(customer_id)

        return {
            "customer_id": customer_id,
            "cancelled": True
        }

    def handle_invoice_paid(self, invoice):
        """Handle successful payment"""

        customer_id = invoice.get("customer")
        amount_paid = invoice.get("amount_paid")

        # TODO: Update database
        # db.record_payment(customer_id, amount_paid)

        return {
            "customer_id": customer_id,
            "amount_paid": amount_paid
        }

    def handle_invoice_payment_failed(self, invoice):
        """Handle failed payment"""

        customer_id = invoice.get("customer")

        # TODO: Update database and notify user
        # db.mark_payment_failed(customer_id)
        # notification_service.send_payment_failed_email(customer_id)

        return {
            "customer_id": customer_id,
            "payment_failed": True
        }


# ==================== SETUP FUNCTIONS ====================

def setup_all_products():
    """Run complete Stripe setup"""

    manager = StripeSubscriptionManager()

    print("🚀 Starting Stripe product setup...")
    print("=" * 50)

    # Create products
    products = manager.create_subscription_products()
    print(f"Created {len(products)} subscription products")

    # Create prices
    prices = manager.create_subscription_prices()
    print(f"Created {len(prices)} prices")

    # Create add-ons
    addons = manager.create_addon_products()
    print(f"Created {len(addons)} add-ons")

    # Create coupons
    coupons = manager.create_coupons()
    print(f"Created {len(coupons)} coupons")

    print("=" * 50)
    print("✅ Stripe setup complete!")

    # Print summary
    print("\n📊 PRODUCT SUMMARY:")
    print("\nSubscription Plans:")
    for key, product in products.items():
        print(f"  - {product.name} ({key}): {product.id}")

    print("\nAdd-ons:")
    for key, addon in addons.items():
        print(f"  - {addon.name}: {addon.id}")

    print("\nPrices:")
    for key, price in prices.items():
        amount = price.unit_amount / 100
        interval = price.get("recurring", {}).get("interval", "one-time")
        print(f"  - {key}: ${amount:.2f}/{interval} ({price.id})")

    print("\nCoupons:")
    for key, coupon in coupons.items():
        discount = f"{coupon.percent_off}%" if coupon.percent_off else f"${coupon.amount_off/100}"
        print(f"  - {coupon.name}: {discount} off ({coupon.id})")

    return {
        "products": products,
        "prices": prices,
        "addons": addons,
        "coupons": coupons
    }


def get_product_ids():
    """Get all product and price IDs (for reference)"""

    products = stripe.Product.list(limit=100)
    prices = stripe.Price.list(limit=100)

    print("📋 EXISTING PRODUCTS:")
    for product in products.data:
        print(f"  {product.name}: {product.id}")

    print("\n💰 EXISTING PRICES:")
    for price in prices.data:
        amount = price.unit_amount / 100 if price.unit_amount else 0
        print(f"  {price.id}: ${amount:.2f}")

    return products, prices


# ==================== MAIN ====================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "setup":
            setup_all_products()
        elif command == "list":
            get_product_ids()
        else:
            print("Usage: python stripe_setup.py [setup|list]")
    else:
        print("=" * 50)
        print("Stripe Setup Script")
        print("=" * 50)
        print("\nCommands:")
        print("  python stripe_setup.py setup  - Create all products, prices, and coupons")
        print("  python stripe_setup.py list   - List existing products and prices")
        print("\n" + "=" * 50)