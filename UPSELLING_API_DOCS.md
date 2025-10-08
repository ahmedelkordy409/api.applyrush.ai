# ApplyRush.AI Upselling API Documentation

Complete API documentation for the 8-page upselling flow with Stripe integration.

## Table of Contents
1. [Setup](#setup)
2. [Pricing Page APIs](#1-pricing-page)
3. [Resume Customization APIs](#2-resume-customization)
4. [Cover Letter APIs](#3-cover-letter)
5. [Premium Upgrade APIs](#4-premium-upgrade)
6. [Priority Access APIs](#5-priority-access)
7. [Create Password APIs](#6-create-password)
8. [Upload Resume APIs](#7-upload-resume)
9. [Companies Exclusion APIs](#8-companies-to-exclude)
10. [Subscription Management](#subscription-management)
11. [Stripe Webhooks](#stripe-webhooks)

---

## Setup

### Environment Variables

Add these to your `.env` file:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Stripe Price IDs (get these after running stripe_setup.py)
STRIPE_BASIC_MONTHLY=price_...
STRIPE_BASIC_YEARLY=price_...
STRIPE_PREMIUM_MONTHLY=price_...
STRIPE_PREMIUM_YEARLY=price_...
STRIPE_ENTERPRISE_MONTHLY=price_...
STRIPE_ENTERPRISE_YEARLY=price_...

# Add-on Price IDs
STRIPE_COVER_LETTER_PRICE=price_...
STRIPE_RESUME_ADDON_PRICE=price_...
STRIPE_PRIORITY_ADDON_PRICE=price_...
```

### Initial Setup

1. **Create Stripe Products:**
```bash
cd /home/ahmed-elkordy/researchs/applyrush.ai/jobhire-ai-backend
python stripe_setup.py setup
```

2. **Copy Price IDs to .env:**
After running setup, copy the generated Price IDs to your `.env` file.

3. **Start Backend:**
```bash
python run_simple.py
```

---

## 1. Pricing Page

### POST `/api/upselling/pricing/create-checkout`

Create a Stripe checkout session for subscription plans.

**Request Body:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "plan_type": "premium",
  "billing_cycle": "monthly",
  "success_url": "http://localhost:3000/upselling/resume-customization?success=true",
  "cancel_url": "http://localhost:3000/upselling/pricing"
}
```

**Parameters:**
- `plan_type`: "basic" | "premium" | "enterprise"
- `billing_cycle`: "monthly" | "yearly"

**Response:**
```json
{
  "success": true,
  "session_id": "cs_test_...",
  "url": "https://checkout.stripe.com/pay/cs_test_...",
  "plan_type": "premium",
  "billing_cycle": "monthly"
}
```

**Usage in Frontend:**
```typescript
const response = await fetch('http://localhost:8000/api/upselling/pricing/create-checkout', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    user_id: session.user.id,
    email: session.user.email,
    plan_type: 'premium',
    billing_cycle: 'monthly',
    success_url: `${window.location.origin}/upselling/resume-customization?success=true`,
    cancel_url: `${window.location.origin}/upselling/pricing`
  })
});

const { url } = await response.json();
window.location.href = url; // Redirect to Stripe Checkout
```

**Features by Plan:**
- **Free**: 20 applications/day, basic AI, email support
- **Basic ($20/mo)**: 40 applications/day, GPT-4 Mini, basic analytics
- **Premium ($50/mo)**: 60 applications/day, GPT-4.1 Mini, priority support, resume customization
- **Enterprise ($99/mo)**: Unlimited applications, premium AI, 24/7 support, API access

---

## 2. Resume Customization

### POST `/api/upselling/resume-customization/enable`

Enable AI-powered resume customization addon.

**Request Body:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "enable_customization": true,
  "target_keywords": ["React", "Node.js", "AWS"]
}
```

**Response:**
```json
{
  "success": true,
  "addon_enabled": true,
  "estimated_improvement": "+44% more interview invitations",
  "sample_keywords": [
    "Agile methodology",
    "REST APIs",
    "GraphQL",
    "Docker",
    "AWS"
  ],
  "ats_score_boost": 35
}
```

### POST `/api/upselling/resume-customization/analyze`

Analyze resume against a specific job description.

**Request Body:**
```json
{
  "user_id": "user_123",
  "job_description": "We're looking for a Senior React Developer with 5+ years...",
  "current_resume_text": "John Doe\nSenior Software Engineer..."
}
```

**Response:**
```json
{
  "success": true,
  "match_score": 72,
  "missing_keywords": ["React", "Node.js", "Agile"],
  "suggestions": [
    "Add 'React' with version in skills section",
    "Quantify achievements with metrics",
    "Include 'Agile methodology' in project descriptions"
  ],
  "optimized_sections": ["skills", "experience", "summary"]
}
```

---

## 3. Cover Letter

### POST `/api/upselling/cover-letter/create-checkout`

Create checkout session for cover letter addon ($12 one-time).

**Request Body:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "success_url": "http://localhost:3000/upselling/premium-upgrade?success=true",
  "cancel_url": "http://localhost:3000/upselling/cover-letter"
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "cs_test_...",
  "url": "https://checkout.stripe.com/pay/cs_test_..."
}
```

### POST `/api/upselling/cover-letter/generate`

Generate AI-powered cover letter for a specific job.

**Request Body:**
```json
{
  "user_id": "user_123",
  "job_title": "Senior Software Engineer",
  "company_name": "TechCorp",
  "job_description": "We're seeking a talented engineer...",
  "user_experience": "5 years in full-stack development..."
}
```

**Response:**
```json
{
  "success": true,
  "cover_letter": "Dear Hiring Manager,\n\nI am writing to express...",
  "word_count": 250,
  "generated_at": "2025-09-30T10:30:00Z"
}
```

---

## 4. Premium Upgrade

### POST `/api/upselling/premium/upgrade`

Upgrade user to premium plan.

**Request Body:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "upgrade_to": "premium",
  "features_selected": [
    "gpt_4_1_mini",
    "priority_support",
    "advanced_analytics"
  ]
}
```

**Response:**
```json
{
  "success": true,
  "upgraded_to": "premium",
  "features_unlocked": [
    {
      "feature": "GPT-4.1 Mini Integration",
      "description": "Advanced AI for better job matching",
      "icon": "zap"
    },
    {
      "feature": "60 Jobs Per Day",
      "description": "Triple your daily application limit",
      "icon": "briefcase"
    },
    {
      "feature": "Priority Support",
      "description": "Get help faster with dedicated support",
      "icon": "headphones"
    }
  ],
  "daily_application_limit": 60,
  "ai_model": "gpt-4.1-mini",
  "priority_support": true
}
```

---

## 5. Priority Access

### POST `/api/upselling/priority-access/enable`

Enable priority access to new job postings.

**Request Body:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "enable_priority": true
}
```

**Response:**
```json
{
  "success": true,
  "priority_enabled": true,
  "notification_channels": ["email", "push", "sms"],
  "average_time_advantage": "Within first hour of posting",
  "alert_frequency": "Real-time (instant)"
}
```

### POST `/api/upselling/priority-access/configure-notifications`

Configure notification preferences.

**Request Body:**
```json
{
  "user_id": "user_123",
  "channels": ["email", "push"],
  "job_criteria": {
    "titles": ["Software Engineer", "Full Stack Developer"],
    "locations": ["Remote", "San Francisco"],
    "salary_min": 120000
  }
}
```

**Response:**
```json
{
  "success": true,
  "channels_enabled": ["email", "push"],
  "criteria_set": true,
  "estimated_alerts_per_day": 15
}
```

---

## 6. Create Password

### POST `/api/upselling/password/create`

Create permanent password after signup.

**Request Body:**
```json
{
  "email": "user@example.com",
  "temp_password": "TempPass123!",
  "new_password": "MySecure123!",
  "confirm_password": "MySecure123!"
}
```

**Response:**
```json
{
  "success": true,
  "user_id": "user_123",
  "token": "jwt_token_here",
  "profile_complete": true
}
```

### POST `/api/upselling/password/validate`

Validate password strength.

**Request Body:**
```json
{
  "password": "MyPassword123!"
}
```

**Response:**
```json
{
  "success": true,
  "strength": "strong",
  "requirements_met": {
    "length": true,
    "uppercase": true,
    "lowercase": true,
    "number": true,
    "special": true
  },
  "score": 5
}
```

---

## 7. Upload Resume

### POST `/api/upselling/resume/upload`

Upload and analyze resume with AI.

**Request (multipart/form-data):**
- `file`: Resume file (PDF, DOC, DOCX, TXT - max 10MB)
- `user_id`: string
- `email`: string
- `first_name`: string
- `last_name`: string
- `phone_number`: string

**Response:**
```json
{
  "success": true,
  "resume_id": "resume_abc123",
  "file_url": "https://storage.applyrush.ai/resumes/resume_abc123.pdf",
  "analysis": {
    "total_experience_years": 5,
    "job_titles": ["Senior Software Engineer", "Software Developer"],
    "companies": ["Tech Corp", "StartupXYZ"],
    "education": ["B.S. Computer Science"],
    "certifications": ["AWS Certified Developer"]
  },
  "ats_score": 78,
  "suggestions": [
    "Add more quantifiable achievements",
    "Include keywords from target job descriptions",
    "Add a professional summary at the top"
  ],
  "extracted_skills": [
    "Python",
    "JavaScript",
    "React",
    "Node.js",
    "AWS",
    "Docker"
  ]
}
```

**Frontend Usage:**
```typescript
const formData = new FormData();
formData.append('file', resumeFile);
formData.append('user_id', userId);
formData.append('email', email);
formData.append('first_name', firstName);
formData.append('last_name', lastName);
formData.append('phone_number', phoneNumber);

const response = await fetch('http://localhost:8000/api/upselling/resume/upload', {
  method: 'POST',
  body: formData
});
```

---

## 8. Companies to Exclude

### POST `/api/upselling/exclusions/save`

Save list of excluded companies.

**Request Body:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "excluded_companies": ["Meta", "Amazon", "Uber", "Tesla"],
  "excluded_categories": ["bigtech", "consulting"]
}
```

**Response:**
```json
{
  "success": true,
  "total_excluded": 12,
  "company_names": ["Meta", "Amazon", "Uber", "Tesla", "Google", "Microsoft"],
  "estimated_jobs_filtered": 60
}
```

### GET `/api/upselling/exclusions/categories`

Get available exclusion categories.

**Response:**
```json
{
  "success": true,
  "categories": [
    {
      "id": "consulting",
      "label": "Consulting firms",
      "description": "Management and technology consulting companies",
      "example_companies": ["Accenture", "Deloitte", "McKinsey"]
    },
    {
      "id": "bigtech",
      "label": "Big Tech",
      "description": "Large technology companies",
      "example_companies": ["Google", "Meta", "Amazon"]
    }
  ]
}
```

---

## Subscription Management

### GET `/api/user/{user_id}/subscription`

Get user's current subscription status and features.

**Response:**
```json
{
  "success": true,
  "user_id": "user_123",
  "subscription": {
    "plan_type": "premium",
    "status": "active",
    "billing_cycle": "monthly",
    "next_billing_date": "2025-10-30",
    "trial_ends_at": null
  },
  "features": {
    "daily_application_limit": 60,
    "ai_model": "gpt-4.1-mini",
    "priority_support": true,
    "resume_customization": true,
    "cover_letter_generation": true,
    "priority_access": false,
    "analytics": "advanced"
  },
  "addons": ["resume_customization", "cover_letter"],
  "usage": {
    "applications_today": 12,
    "applications_this_month": 145,
    "cover_letters_generated": 23
  }
}
```

**Use this endpoint to:**
- Check if user has access to specific features
- Enforce application limits
- Show/hide premium features in UI
- Display subscription status

**Frontend Middleware Example:**
```typescript
// Protect premium features
async function checkFeatureAccess(userId: string, feature: string) {
  const response = await fetch(`http://localhost:8000/api/user/${userId}/subscription`);
  const data = await response.json();
  return data.features[feature] === true;
}

// Usage
if (!await checkFeatureAccess(userId, 'resume_customization')) {
  router.push('/upselling/resume-customization');
}
```

---

## Stripe Webhooks

### POST `/api/webhooks/stripe`

Handle Stripe webhook events.

**Supported Events:**
- `checkout.session.completed` - Subscription/payment completed
- `customer.subscription.updated` - Subscription changed
- `customer.subscription.deleted` - Subscription cancelled
- `invoice.payment_succeeded` - Payment successful
- `invoice.payment_failed` - Payment failed

**Setup Webhook:**
1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://yourdomain.com/api/webhooks/stripe`
3. Select events to listen for
4. Copy webhook signing secret to `.env` as `STRIPE_WEBHOOK_SECRET`

**Test Locally with Stripe CLI:**
```bash
stripe listen --forward-to localhost:8000/api/webhooks/stripe
stripe trigger checkout.session.completed
```

---

## Complete Flow Example

### Frontend Integration Example

```typescript
// 1. Pricing Page - User selects Premium Monthly
const checkoutResponse = await fetch('http://localhost:8000/api/upselling/pricing/create-checkout', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    user_id: 'user_123',
    email: 'user@example.com',
    plan_type: 'premium',
    billing_cycle: 'monthly',
    success_url: `${window.location.origin}/upselling/resume-customization?success=true`,
    cancel_url: `${window.location.origin}/upselling/pricing`
  })
});
const { url } = await checkoutResponse.json();
window.location.href = url; // Redirect to Stripe

// 2. After successful payment, user returns to resume-customization page
// Check URL params: ?success=true

// 3. Enable resume customization addon
await fetch('http://localhost:8000/api/upselling/resume-customization/enable', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    user_id: 'user_123',
    email: 'user@example.com',
    enable_customization: true
  })
});

// 4. Continue through flow...
```

---

## Testing

### Test with Stripe Test Mode

Use these test card numbers:
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **3D Secure**: `4000 0025 0000 3155`

Expiry: Any future date
CVC: Any 3 digits
ZIP: Any 5 digits

### Test Endpoints

```bash
# Test pricing checkout
curl -X POST http://localhost:8000/api/upselling/pricing/create-checkout \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "email": "test@example.com",
    "plan_type": "premium",
    "billing_cycle": "monthly"
  }'

# Test subscription status
curl http://localhost:8000/api/user/test_user/subscription
```

---

## Error Handling

All endpoints return errors in this format:

```json
{
  "detail": "Error message here"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid/missing token)
- `404` - Not Found
- `500` - Internal Server Error

---

## Security Considerations

1. **Always verify user authentication** before processing requests
2. **Validate Stripe webhook signatures** to prevent fraud
3. **Use HTTPS** in production
4. **Never expose secret keys** in frontend code
5. **Implement rate limiting** on payment endpoints
6. **Store sensitive data encrypted** in database

---

## Next Steps

1. Run `python stripe_setup.py setup` to create products
2. Update `.env` with actual Stripe Price IDs
3. Implement database storage for subscription data
4. Add authentication middleware
5. Set up webhook endpoint in Stripe Dashboard
6. Test complete flow end-to-end
7. Deploy to production with HTTPS

---

**Documentation Version:** 1.0
**Last Updated:** September 30, 2025
**Backend:** FastAPI with Stripe Integration
**Frontend:** Next.js 15 with NextAuth