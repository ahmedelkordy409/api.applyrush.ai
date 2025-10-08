#!/usr/bin/env python3
"""
Update Stripe Webhook Endpoint
This script updates or creates a webhook endpoint in your Stripe account
"""

import os
import stripe
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Your webhook URL (change this to your production URL when deploying)
WEBHOOK_URL = "http://localhost:8000/api/webhooks/stripe"
PRODUCTION_URL = "https://api.applyrush.ai/api/webhooks/stripe"  # Update with your actual domain

# Events to listen to
WEBHOOK_EVENTS = [
    "checkout.session.completed",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.trial_will_end",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
]


def list_existing_webhooks():
    """List all existing webhook endpoints"""
    print("\n📋 Listing existing webhook endpoints...")
    try:
        webhooks = stripe.WebhookEndpoint.list()

        if not webhooks.data:
            print("   No existing webhooks found.")
            return []

        for idx, webhook in enumerate(webhooks.data, 1):
            print(f"\n   Webhook #{idx}:")
            print(f"   ID: {webhook.id}")
            print(f"   URL: {webhook.url}")
            print(f"   Status: {webhook.status}")
            print(f"   Events: {len(webhook.enabled_events)} events")

        return webhooks.data
    except Exception as e:
        print(f"   ❌ Error listing webhooks: {str(e)}")
        return []


def create_webhook(url):
    """Create a new webhook endpoint"""
    print(f"\n🔨 Creating new webhook endpoint: {url}")
    try:
        webhook = stripe.WebhookEndpoint.create(
            url=url,
            enabled_events=WEBHOOK_EVENTS,
        )

        print(f"   ✅ Webhook created successfully!")
        print(f"   Webhook ID: {webhook.id}")
        print(f"   Webhook Secret: {webhook.secret}")
        print(f"\n   ⚠️  IMPORTANT: Add this to your .env file:")
        print(f"   STRIPE_WEBHOOK_SECRET={webhook.secret}")

        return webhook
    except Exception as e:
        print(f"   ❌ Error creating webhook: {str(e)}")
        return None


def update_webhook(webhook_id, url):
    """Update an existing webhook endpoint"""
    print(f"\n🔄 Updating webhook {webhook_id} with URL: {url}")
    try:
        webhook = stripe.WebhookEndpoint.modify(
            webhook_id,
            url=url,
            enabled_events=WEBHOOK_EVENTS,
        )

        print(f"   ✅ Webhook updated successfully!")
        print(f"   Webhook ID: {webhook.id}")
        print(f"   Webhook URL: {webhook.url}")

        return webhook
    except Exception as e:
        print(f"   ❌ Error updating webhook: {str(e)}")
        return None


def delete_webhook(webhook_id):
    """Delete a webhook endpoint"""
    print(f"\n🗑️  Deleting webhook {webhook_id}")
    try:
        stripe.WebhookEndpoint.delete(webhook_id)
        print(f"   ✅ Webhook deleted successfully!")
        return True
    except Exception as e:
        print(f"   ❌ Error deleting webhook: {str(e)}")
        return False


def main():
    print("=" * 70)
    print("🔧 Stripe Webhook Management")
    print("=" * 70)

    # List existing webhooks
    existing_webhooks = list_existing_webhooks()

    # Ask user what they want to do
    print("\n" + "=" * 70)
    print("What would you like to do?")
    print("1. Info about local development webhooks")
    print("2. Create new webhook for production")
    print("3. Update existing webhook")
    print("4. Delete existing webhook")
    print("5. Exit")
    print("=" * 70)

    choice = input("\nEnter your choice (1-5): ").strip()

    if choice == "1":
        # Info about local development webhooks
        print("\n" + "=" * 70)
        print("ℹ️  Local Development Webhooks")
        print("=" * 70)
        print("\n⚠️  Stripe doesn't allow localhost URLs via API.")
        print("   For local development, use the Stripe CLI:\n")
        print("   1. Your Stripe CLI listener is already running!")
        print("   2. It's forwarding to: http://localhost:8000/api/webhooks/stripe")
        print("   3. Your webhook secret has been added to .env")
        print("\n   To test webhooks locally:")
        print("   stripe trigger payment_intent.succeeded")
        print("\n   The webhook secret from CLI is already in your .env file:")
        print("   STRIPE_WEBHOOK_SECRET=whsec_5ee51efde5d06c5e24dff636c812ac365eb643be71e66f9be17aaeb334aca2e4")
        print("\n✅ You're all set for local webhook testing!")

    elif choice == "2":
        # Create production webhook
        prod_url = input(f"\nEnter production URL (default: {PRODUCTION_URL}): ").strip()
        if not prod_url:
            prod_url = PRODUCTION_URL

        webhook = create_webhook(prod_url)
        if webhook:
            print("\n✨ Production webhook is ready!")

    elif choice == "3":
        # Update existing webhook
        if not existing_webhooks:
            print("\n⚠️  No existing webhooks to update.")
            return

        webhook_id = input("\nEnter webhook ID to update: ").strip()
        new_url = input("Enter new URL: ").strip()

        if webhook_id and new_url:
            update_webhook(webhook_id, new_url)

    elif choice == "4":
        # Delete existing webhook
        if not existing_webhooks:
            print("\n⚠️  No existing webhooks to delete.")
            return

        webhook_id = input("\nEnter webhook ID to delete: ").strip()

        if webhook_id:
            confirm = input(f"Are you sure you want to delete {webhook_id}? (yes/no): ").strip().lower()
            if confirm == "yes":
                delete_webhook(webhook_id)

    elif choice == "5":
        print("\n👋 Goodbye!")
        return

    else:
        print("\n❌ Invalid choice. Please run the script again.")

    print("\n" + "=" * 70)
    print("✅ Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()
