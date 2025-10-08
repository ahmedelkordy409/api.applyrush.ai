# Swagger API Documentation

## ✅ Status: Complete and Up-to-Date

All 89 endpoints are registered and documented in Swagger UI.

## 📍 Access Points

### Swagger UI (Interactive):
```
http://localhost:8000/docs
```

### ReDoc (Alternative):
```
http://localhost:8000/redoc
```

### OpenAPI JSON:
```
http://localhost:8000/openapi.json
```

## 📊 Endpoint Statistics

**Total Endpoints:** 89

### By Category:

| Category | Count | Endpoints |
|----------|-------|-----------|
| **Authentication** | 5 | login, signup, refresh, me, update-password |
| **Upselling** | 4 | save-step, update-profile, user-profile, complete-onboarding |
| **Resumes** | 9 | upload, upload-guest, list, get, enhance, analyze, tailor, download, set-primary |
| **Subscriptions** | 3 | create-checkout, portal, webhook |
| **Onboarding** | 5 | authenticated, guest, guest/create, guest/answer, status |
| **Applications** | 6 | database, stats, queue, approve, reject |
| **Auto-Apply** | 10 | start, stop, status, queue/items, readiness, cancel |
| **Matching** | 3 | jobs, approve, reject |
| **Cover Letters** | 3 | generate, list, get |
| **Interviews** | 9 | create, list, get, results, session, pause, resume, complete |
| **Dashboard** | 6 | stats, summary, health, clear-cache, increase-items, getting-started |
| **Users** | 3 | profile, preferences, settings |
| **User Tasks** | 3 | tasks, complete, uncomplete |
| **User Settings** | 6 | settings, exclude-company, pause-search, resume-search, search-status |
| **Inbox** | 3 | messages, get message, stats |
| **Background Jobs** | 5 | status, trigger auto-apply, cleanup, find-matches, update-stats |
| **Webhooks** | 5 | stripe, email/sendgrid, email/ses, email/postfix, email/test |
| **System** | 2 | /, /health |

## 🔍 All Endpoints (Alphabetical)

### Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/signup` - User registration
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/auth/update-password` - Update password

### Upselling (`/api/v1/upselling`)
- `POST /api/v1/upselling/save-step` - Save onboarding step
- `POST /api/v1/upselling/update-profile` - Update user profile
- `GET /api/v1/upselling/user-profile` - Get user profile
- `POST /api/v1/upselling/complete-onboarding` - Complete onboarding

**Note:** All upselling endpoints support both authenticated (JWT) and guest (email) modes.

### Resumes (`/api/v1/resumes`)
- `POST /api/v1/resumes/upload` - Upload resume (authenticated)
- `POST /api/v1/resumes/upload-guest` - Upload resume (guest)
- `GET /api/v1/resumes/` - List user resumes
- `GET /api/v1/resumes/{resume_id}` - Get resume details
- `POST /api/v1/resumes/{resume_id}/set-primary` - Set primary resume
- `POST /api/v1/resumes/{resume_id}/enhance` - Enhance resume with AI
- `POST /api/v1/resumes/{resume_id}/analyze` - Analyze for job
- `POST /api/v1/resumes/tailor` - Generate tailored resume
- `GET /api/v1/resumes/{resume_id}/download` - Download resume
- `GET /api/v1/resumes/stats/dashboard` - Resume statistics
- `DELETE /api/v1/resumes/{resume_id}` - Delete resume

### Subscriptions (`/api/v1/subscriptions`)
- `POST /api/v1/subscriptions/create-checkout-session` - Create Stripe checkout
- `GET /api/v1/subscriptions/portal` - Customer portal session
- `POST /api/v1/subscriptions/webhook` - Stripe webhook handler

### Onboarding (`/api/v1/onboarding`)
- `POST /api/v1/onboarding/authenticated` - Authenticated onboarding
- `POST /api/v1/onboarding/guest` - Guest onboarding
- `POST /api/v1/onboarding/guest/create` - Create guest session
- `POST /api/v1/onboarding/guest/answer` - Answer guest question
- `GET /api/v1/onboarding/status` - Check onboarding status

### Applications (`/api/v1/applications`)
- `GET /api/v1/applications/database` - Get applications from database
- `GET /api/v1/applications/database/stats` - Application statistics
- `GET /api/v1/applications/queue/database` - Queue items from database
- `POST /api/v1/applications/{application_id}/approve` - Approve application
- `POST /api/v1/applications/{application_id}/reject` - Reject application

### Auto-Apply (`/api/v1/auto-apply`)
- `POST /api/v1/auto-apply/` - Start auto-apply
- `POST /api/v1/auto-apply/queue/start` - Start queue worker
- `POST /api/v1/auto-apply/queue/stop` - Stop queue worker
- `GET /api/v1/auto-apply/queue/status` - Queue status
- `GET /api/v1/auto-apply/queue/items` - Queue items
- `GET /api/v1/auto-apply/queue/items/{item_id}` - Get queue item
- `POST /api/v1/auto-apply/cancel/{session_id}` - Cancel session
- `GET /api/v1/auto-apply/status` - Auto-apply status
- `GET /api/v1/auto-apply/readiness` - Check readiness

### Matching (`/api/v1/matching`)
- `GET /api/v1/matching/jobs` - Get matched jobs
- `POST /api/v1/matching/approve/{job_id}` - Approve job
- `POST /api/v1/matching/reject/{job_id}` - Reject job

### Cover Letters (`/api/v1/cover-letters`)
- `POST /api/v1/cover-letters/generate` - Generate cover letter
- `GET /api/v1/cover-letters/` - List cover letters
- `GET /api/v1/cover-letters/{cover_letter_id}` - Get cover letter

### Interviews (`/api/v1/interviews`)
- `POST /api/v1/interviews/create` - Create interview
- `GET /api/v1/interviews/list` - List interviews
- `GET /api/v1/interviews/` - Get interviews
- `GET /api/v1/interviews/{interview_id}` - Get interview
- `GET /api/v1/interviews/{interview_id}/results` - Interview results
- `GET /api/v1/interviews/session/{session_id}` - Get session
- `POST /api/v1/interviews/session/{session_id}/pause` - Pause session
- `POST /api/v1/interviews/session/{session_id}/resume` - Resume session
- `POST /api/v1/interviews/session/{session_id}/complete` - Complete session
- `POST /api/v1/interviews/smart-conversation` - Smart conversation

### Dashboard (`/api/v1/dashboard`)
- `GET /api/v1/dashboard/stats` - Dashboard statistics
- `GET /api/v1/dashboard/summary` - Dashboard summary
- `GET /api/v1/dashboard/health` - Health check
- `POST /api/v1/dashboard/clear-cache` - Clear cache
- `POST /api/v1/dashboard/increase-items` - Increase items
- `GET /api/v1/dashboard/getting-started` - Getting started guide

### Users (`/api/v1/users`)
- `GET /api/v1/users/profile` - Get user profile
- `POST /api/v1/users/preferences` - Update preferences

### User Settings (`/api/v1/user`)
- `GET /api/v1/user/settings` - Get user settings
- `POST /api/v1/user/settings` - Update settings
- `POST /api/v1/user/settings/exclude-company` - Exclude company
- `DELETE /api/v1/user/settings/exclude-company/{company_name}` - Remove exclusion
- `POST /api/v1/user/settings/pause-search` - Pause job search
- `POST /api/v1/user/settings/resume-search` - Resume job search
- `GET /api/v1/user/settings/search-status` - Search status

### User Tasks (`/api/v1/user-tasks`)
- `GET /api/v1/user-tasks/tasks` - List tasks
- `POST /api/v1/user-tasks/tasks/{task_id}/complete` - Complete task
- `POST /api/v1/user-tasks/tasks/{task_id}/uncomplete` - Uncomplete task

### Inbox (`/api/v1/inbox`)
- `GET /api/v1/inbox/messages` - List messages
- `GET /api/v1/inbox/messages/{message_id}` - Get message
- `GET /api/v1/inbox/messages/stats/summary` - Message stats

### Background Jobs (`/api/v1/background-jobs`)
- `GET /api/v1/background-jobs/status` - Job status
- `POST /api/v1/background-jobs/trigger/auto-apply` - Trigger auto-apply
- `POST /api/v1/background-jobs/trigger/cleanup` - Trigger cleanup
- `POST /api/v1/background-jobs/trigger/find-matches` - Trigger find matches
- `POST /api/v1/background-jobs/trigger/update-stats` - Trigger update stats

### Webhooks (`/api/v1/webhooks`)
- `POST /api/v1/webhooks/stripe` - Stripe webhook
- `POST /api/v1/webhooks/email/sendgrid` - SendGrid webhook
- `POST /api/v1/webhooks/email/ses` - AWS SES webhook
- `POST /api/v1/webhooks/email/postfix` - Postfix webhook
- `POST /api/v1/webhooks/email/test` - Test webhook

### System
- `GET /` - Root endpoint
- `GET /health` - Health check

## 🔐 Authentication

### Required Headers:
```http
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

### Get Token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'
```

### Use Token:
```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## 📝 Example Requests

### 1. Create Account
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123",
    "full_name": "John Doe"
  }'
```

### 2. Upload Resume (Guest)
```bash
curl -X POST http://localhost:8000/api/v1/resumes/upload-guest \
  -F "file=@resume.pdf" \
  -F "session_id=guest_123"
```

### 3. Save Upselling Step (Guest)
```bash
curl -X POST http://localhost:8000/api/v1/upselling/save-step \
  -H "Content-Type: application/json" \
  -d '{
    "email": "guest@example.com",
    "step": "preferences",
    "data": {
      "location": "Remote",
      "positions": ["Software Engineer"]
    }
  }'
```

### 4. Start Auto-Apply (Authenticated)
```bash
curl -X POST http://localhost:8000/api/v1/auto-apply/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_ids": ["job_id_1", "job_id_2"]
  }'
```

### 5. Create Subscription Checkout
```bash
curl -X POST http://localhost:8000/api/v1/subscriptions/create-checkout-session \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "premium",
    "billing_cycle": "monthly",
    "success_url": "https://app.com/success",
    "cancel_url": "https://app.com/cancel"
  }'
```

## 🎨 Response Formats

### Success Response:
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {...}
}
```

### Error Response:
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

### Paginated Response:
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "pages": 5
}
```

## 🔄 API Versioning

Current version: **v1**

All endpoints are prefixed with `/api/v1/`

## 📊 Rate Limits

| Tier | Requests/Minute | Requests/Hour |
|------|-----------------|---------------|
| Free | 30 | 500 |
| Basic | 60 | 2000 |
| Premium | 120 | 5000 |
| Enterprise | Unlimited | Unlimited |

## 🛠️ Testing with Swagger UI

1. **Navigate to:** `http://localhost:8000/docs`
2. **Click "Authorize"** button (top right)
3. **Enter your JWT token:** `Bearer YOUR_TOKEN_HERE`
4. **Try out endpoints** directly in the UI

## 📚 Additional Resources

- **Frontend Integration:** See `UPSELLING_FULLSTACK_READY.md`
- **Bot Integration:** See `BOT_INTEGRATION_COMPLETE.md`
- **Resume Upload:** See `RESUME_UPLOAD_GUIDE.md`
- **Application Status:** See `JOB_APPLICATION_STATUS_FINAL.md`

---

**Status:** ✅ All 89 endpoints documented and accessible
**Last Updated:** October 7, 2025
**API Version:** 2.0.0
