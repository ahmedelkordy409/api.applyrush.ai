# ApplyRush.AI Upselling Setup Guide

Quick setup guide to get the complete upselling flow working with Stripe integration.

## ✅ What We Built

### 8-Page Upselling Flow
1. **Pricing** → Select subscription plan (Free, Basic, Premium, Enterprise)
2. **Resume Customization** → AI-powered ATS optimization add-on
3. **Cover Letter** → AI cover letter generation add-on ($12)
4. **Premium Upgrade** → Upgrade to premium features
5. **Priority Access** → Early access to new jobs add-on
6. **Create Password** → Set permanent password after signup
7. **Upload Resume** → Upload and AI analyze resume
8. **Companies to Exclude** → Block unwanted companies

### Complete Backend APIs
- ✅ All 8 pages have dedicated API endpoints
- ✅ Stripe checkout session creation
- ✅ Subscription management
- ✅ Add-on purchases (one-time payments)
- ✅ Webhook handling
- ✅ Feature access control
- ✅ Usage tracking

### Authentication & Authorization
- ✅ NextAuth.js integration
- ✅ JWT-based sessions
- ✅ Middleware route protection
- ✅ Subscription-based feature access

---

## 🚀 Quick Start

### Step 1: Stripe Setup

```bash
cd /home/ahmed-elkordy/researchs/applyrush.ai/jobhire-ai-backend

# Install Stripe if not already installed
pip install stripe

# Create all Stripe products, prices, and coupons
python stripe_setup.py setup
```

**Output will show:**
```
✅ Created subscription products
Created 4 subscription products
✅ Created subscription prices
Created 6 prices
✅ Created add-ons
Created 3 add-ons
✅ Created promotional coupons
Created 4 coupons

📋 PRODUCT SUMMARY:
Subscription Plans:
  - Free Plan (free): prod_xxx
  - Basic Plan (basic): prod_xxx
  - Premium Plan (premium): prod_xxx
  - Enterprise Plan (enterprise): prod_xxx

Prices:
  - basic_monthly: $20.00/month (price_xxx)
  - basic_yearly: $200.00/year (price_xxx)
  ...
```

### Step 2: Update Environment Variables

Copy the Price IDs from the output and update your `.env`:

```bash
# Add to .env file
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Subscription Price IDs (from stripe_setup.py output)
STRIPE_BASIC_MONTHLY=price_xxx
STRIPE_BASIC_YEARLY=price_xxx
STRIPE_PREMIUM_MONTHLY=price_xxx
STRIPE_PREMIUM_YEARLY=price_xxx
STRIPE_ENTERPRISE_MONTHLY=price_xxx
STRIPE_ENTERPRISE_YEARLY=price_xxx

# Add-on Price IDs
STRIPE_COVER_LETTER_PRICE=price_xxx
STRIPE_RESUME_ADDON_PRICE=price_xxx
STRIPE_PRIORITY_ADDON_PRICE=price_xxx
```

### Step 3: Start Backend

```bash
python run_simple.py
```

Server will run at: `http://localhost:8000`
API Docs: `http://localhost:8000/docs`

### Step 4: Setup Stripe Webhooks (for production)

1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://yourdomain.com/api/webhooks/stripe`
3. Select these events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy the webhook signing secret to `.env` as `STRIPE_WEBHOOK_SECRET`

**For local testing:**
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe  # macOS
# or download from: https://stripe.com/docs/stripe-cli

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/webhooks/stripe

# Test webhook
stripe trigger checkout.session.completed
```

---

## 📋 Complete Flow Test

### 1. Start Both Servers

Terminal 1 (Backend):
```bash
cd /home/ahmed-elkordy/researchs/applyrush.ai/jobhire-ai-backend
python run_simple.py
```

Terminal 2 (Frontend):
```bash
cd /home/ahmed-elkordy/researchs/applyrush.ai/app.applyrush.ai
npm run dev
```

### 2. Test Onboarding → Upselling Flow

1. Go to `http://localhost:3000/onboarding`
2. Complete onboarding form (creates guest session)
3. Enter email → creates account with temp password
4. **Auto-login** → redirects to `http://localhost:3000/upselling/pricing`

### 3. Test Upselling Pages (In Order)

**Page 1: Pricing** (`/upselling/pricing`)
- User sees 4 plans: Free, Basic, Premium, Enterprise
- Select "Premium" + "Monthly"
- Click "Get Started" → API creates Stripe checkout
- Redirects to Stripe checkout page
- Enter test card: `4242 4242 4242 4242`
- Complete payment → redirects back with `?success=true`
- Next page: `/upselling/resume-customization`

**Page 2: Resume Customization** (`/upselling/resume-customization`)
- Shows AI customization benefits (+44% interviews)
- Click "Get Extra Feature — $12" OR "Skip"
- Next page: `/upselling/cover-letter`

**Page 3: Cover Letter** (`/upselling/cover-letter`)
- Shows AI cover letter generation
- Click "Add Premium Feature — $12" → Stripe checkout
- OR click "Skip"
- Next page: `/upselling/premium-upgrade`

**Page 4: Premium Upgrade** (`/upselling/premium-upgrade`)
- Shows premium features (GPT-4.1, 60 jobs/day, support)
- Click "Upgrade — $50" OR "Stick with Basic"
- Next page: `/upselling/priority-access`

**Page 5: Priority Access** (`/upselling/priority-access`)
- Shows priority job access (+36% response rate)
- Click "Get Extra Feature" OR "Skip"
- Next page: `/upselling/create-password`

**Page 6: Create Password** (`/upselling/create-password`)
- User creates permanent password
- Password requirements: 8+ chars, uppercase, lowercase, number, special char
- Enter password → API validates and creates
- Next page: `/upselling/upload-resume`

**Page 7: Upload Resume** (`/upselling/upload-resume`)
- Drag & drop resume (PDF, DOC, DOCX, TXT max 10MB)
- Enter first name, last name, phone
- Click "Continue" → API uploads and analyzes
- Returns ATS score and suggestions
- Next page: `/upselling/companies-to-exclude`

**Page 8: Companies to Exclude** (`/upselling/companies-to-exclude`)
- Type company names and press Enter
- Select categories (Consulting, Big Tech, Banks, etc.)
- Click "Start job search" → redirects to `/dashboard`

---

## 🔐 Authentication & Feature Access

### Check User Subscription

```typescript
// Frontend: Check if user has access to a feature
const checkFeatureAccess = async (userId: string, feature: string) => {
  const response = await fetch(`http://localhost:8000/api/user/${userId}/subscription`);
  const data = await response.json();
  return data.features[feature] === true;
};

// Usage
if (!await checkFeatureAccess(userId, 'resume_customization')) {
  // Redirect to upselling page or show upgrade prompt
  router.push('/upselling/resume-customization');
}
```

### Enforce Application Limits

```typescript
// Check daily application limit
const checkApplicationLimit = async (userId: string) => {
  const response = await fetch(`http://localhost:8000/api/user/${userId}/subscription`);
  const data = await response.json();

  const limit = data.features.daily_application_limit;
  const usage = data.usage.applications_today;

  if (usage >= limit) {
    // Show upgrade prompt
    return false;
  }
  return true;
};
```

---

## 🧪 Testing with Stripe Test Cards

Use these test card numbers in Stripe checkout:

### Successful Payments
- **Success**: `4242 4242 4242 4242`
- **Success (Visa Debit)**: `4000 0566 5566 5556`

### Failed Payments
- **Declined**: `4000 0000 0000 0002`
- **Insufficient Funds**: `4000 0000 0000 9995`
- **Expired Card**: `4000 0000 0000 0069`

### 3D Secure
- **Required**: `4000 0025 0000 3155`
- **Not Supported**: `4000 0000 0000 3220`

**For all cards:**
- Expiry: Any future date (e.g., `12/34`)
- CVC: Any 3 digits (e.g., `123`)
- ZIP: Any 5 digits (e.g., `12345`)

---

## 📊 API Testing

### Test Pricing Checkout

```bash
curl -X POST http://localhost:8000/api/upselling/pricing/create-checkout \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_123",
    "email": "test@example.com",
    "plan_type": "premium",
    "billing_cycle": "monthly",
    "success_url": "http://localhost:3000/upselling/resume-customization?success=true",
    "cancel_url": "http://localhost:3000/upselling/pricing"
  }'
```

### Test Cover Letter Addon

```bash
curl -X POST http://localhost:8000/api/upselling/cover-letter/create-checkout \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_123",
    "email": "test@example.com",
    "success_url": "http://localhost:3000/upselling/premium-upgrade?success=true",
    "cancel_url": "http://localhost:3000/upselling/cover-letter"
  }'
```

### Test Subscription Status

```bash
curl http://localhost:8000/api/user/test_user_123/subscription
```

---

## 📂 File Structure

```
jobhire-ai-backend/
├── run_simple.py                 # Main FastAPI app with upselling endpoints
├── stripe_setup.py               # Stripe product creation script
├── upselling_endpoints.py        # Detailed endpoint implementations
├── UPSELLING_API_DOCS.md         # Complete API documentation
└── UPSELLING_SETUP_GUIDE.md      # This file

app.applyrush.ai/
├── app/
│   ├── api/auth/[...nextauth]/route.ts  # NextAuth config
│   └── upselling/
│       ├── pricing/page.tsx
│       ├── resume-customization/page.tsx
│       ├── cover-letter/page.tsx
│       ├── premium-upgrade/page.tsx
│       ├── priority-access/page.tsx
│       ├── create-password/page.tsx
│       ├── upload-resume/page.tsx
│       └── companies-to-exclude/page.tsx
├── components/upselling/
│   └── header.tsx                # Shows authenticated user
├── lib/
│   ├── hooks/
│   │   ├── use-user-state.tsx    # User state management
│   │   └── use-upselling-user.ts # Upselling-specific hook
│   └── supabase/middleware.ts    # NextAuth JWT validation
└── .env.local                     # NextAuth & Stripe config
```

---

## ⚙️ Environment Variables Summary

### Backend (.env)
```bash
# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Price IDs (from stripe_setup.py)
STRIPE_BASIC_MONTHLY=price_...
STRIPE_BASIC_YEARLY=price_...
STRIPE_PREMIUM_MONTHLY=price_...
STRIPE_PREMIUM_YEARLY=price_...
STRIPE_ENTERPRISE_MONTHLY=price_...
STRIPE_ENTERPRISE_YEARLY=price_...
STRIPE_COVER_LETTER_PRICE=price_...
STRIPE_RESUME_ADDON_PRICE=price_...
STRIPE_PRIORITY_ADDON_PRICE=price_...

# Backend URL
BACKEND_URL=http://localhost:8000
```

### Frontend (.env.local)
```bash
# NextAuth
NEXTAUTH_SECRET=your_secret_here
NEXTAUTH_URL=http://localhost:3000

# Stripe (Public Key)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# Backend
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_PYTHON_API_URL=http://localhost:8000

# Auth Requirements
NEXT_PUBLIC_UPSELLING_REQUIRE_AUTH=true
NEXT_PUBLIC_DASHBOARD_REQUIRE_AUTH=true
```

---

## 🎯 Key Features Implemented

### ✅ Pricing & Subscriptions
- 4 subscription tiers (Free, Basic, Premium, Enterprise)
- Monthly and yearly billing
- 7-day free trial for Premium/Enterprise
- Automatic Stripe checkout creation
- Proration on upgrades/downgrades

### ✅ Add-ons (One-time Purchases)
- Resume Customization ($12)
- Cover Letter Generation ($12)
- Priority Access ($12)
- Supports multiple add-ons per user

### ✅ Authentication Flow
- Guest onboarding (no login required)
- Auto-create account after onboarding
- Temporary password generation
- User sets permanent password in upselling
- NextAuth JWT tokens
- Middleware-based route protection

### ✅ Feature Access Control
- Subscription-based feature unlocking
- Daily application limits by plan
- AI model selection by plan
- Support tier by plan
- Add-on based features

### ✅ Stripe Integration
- Checkout session creation
- Webhook event handling
- Subscription lifecycle management
- Payment failure handling
- Coupon/discount support

---

## 🚨 Common Issues & Solutions

### Issue: Stripe checkout fails with "Invalid price ID"
**Solution:** Run `python stripe_setup.py setup` and update `.env` with actual Price IDs

### Issue: Webhooks not working locally
**Solution:** Use Stripe CLI: `stripe listen --forward-to localhost:8000/api/webhooks/stripe`

### Issue: User not authenticated after onboarding
**Solution:** Check NextAuth configuration in `/app/api/auth/[...nextauth]/route.ts`

### Issue: Can't access upselling pages
**Solution:** Verify middleware is using NextAuth JWT tokens in `lib/supabase/middleware.ts`

---

## 📚 Additional Resources

- **Full API Documentation**: `UPSELLING_API_DOCS.md`
- **Stripe Documentation**: https://stripe.com/docs/api
- **NextAuth.js Docs**: https://next-auth.js.org/
- **FastAPI Docs**: https://fastapi.tiangolo.com/

---

## ✅ Checklist

- [ ] Run `python stripe_setup.py setup`
- [ ] Copy Price IDs to `.env`
- [ ] Update `STRIPE_SECRET_KEY` in `.env`
- [ ] Update `NEXTAUTH_SECRET` in frontend `.env.local`
- [ ] Start backend: `python run_simple.py`
- [ ] Start frontend: `npm run dev`
- [ ] Test complete onboarding flow
- [ ] Test all 8 upselling pages
- [ ] Test Stripe checkout with test card
- [ ] Verify webhook handling (use Stripe CLI)
- [ ] Test subscription API: `/api/user/{user_id}/subscription`
- [ ] Verify feature access control works
- [ ] Test application limits enforcement

---

**Setup Guide Version:** 1.0
**Last Updated:** September 30, 2025
**Status:** ✅ Ready for Testing