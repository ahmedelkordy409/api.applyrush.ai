# Email Application System - Complete Guide

## 🎯 Overview

The Email Application System enables **real job applications** via email instead of just storing data in the database. It includes:

1. **Unique Forwarding Emails** - Each user gets `firstname.userid@apply.applyrush.ai`
2. **Actual Email Sending** - Sends real applications with resume attachments
3. **Reply Tracking** - Automatically tracks company responses
4. **Smart Email Parsing** - Detects interview invites, offers, rejections
5. **Status Auto-Update** - Updates application status based on company replies

---

## 🏗️ Architecture

### Components

1. **EmailForwardingService** (`email_forwarding_service.py`)
   - Creates unique forwarding emails per user
   - Tracks received emails
   - Parses email types (interview/offer/rejection)
   - Forwards to user's real email

2. **JobApplicationEmailService** (`job_application_email_service.py`)
   - Sends actual job applications via SMTP
   - Attaches resume PDFs
   - Uses forwarding email as Reply-To
   - Records sent emails

3. **BackgroundJobService** (`background_jobs.py`)
   - Integrates email sending with auto-apply
   - Checks if jobs support email applications
   - Falls back to database-only if no email available

---

## 📧 How It Works

### Step 1: User Onboarding
When a user signs up, the system creates a unique forwarding email:

```
Format: {firstname}.{userid}@apply.applyrush.ai
Example: john.68e228dc@apply.applyrush.ai
```

**Database Record:**
```javascript
// Collection: forwarding_emails
{
  "_id": ObjectId("..."),
  "user_id": ObjectId("68e228dcb3cb0ec651a59537"),
  "forwarding_address": "john.68e228dc@apply.applyrush.ai",
  "user_real_email": "john@gmail.com",
  "applications_using": [],  // Job IDs that used this email
  "emails_received_count": 0,
  "last_email_at": null,
  "status": "active",
  "created_at": ISODate("2025-10-05T...")
}
```

### Step 2: Job Matching
The system finds relevant jobs and checks if they support email applications:

```python
def _can_apply_via_email(job):
    # Checks for:
    # - apply_email field
    # - application_email field
    # - contact_email field
    # - mailto: links in apply_url
    return True/False
```

### Step 3: Sending Application
When auto-applying, the system:

1. **Composes Professional Email**
   - Subject: `Application for {Job Title} - {User Name}`
   - Body: AI-generated cover letter or template
   - Signature: Contact info + social links

2. **Attaches Resume**
   - Filename: `{FirstName}_{LastName}_Resume.pdf`
   - MIME type: `application/pdf`

3. **Sets Reply-To Header**
   - Reply-To: `john.68e228dc@apply.applyrush.ai`
   - From: `noreply@applyrush.ai`

4. **Sends via SMTP**
   - Uses configured SMTP server (Gmail/SendGrid/AWS SES)
   - Logs success/failure

**Email Structure:**
```
From: noreply@applyrush.ai
To: hiring@company.com
Reply-To: john.68e228dc@apply.applyrush.ai
Subject: Application for Senior Software Engineer - John Doe

Dear Hiring Manager,

I am writing to express my interest in the Senior Software Engineer
position at YourCompany...

[AI-generated cover letter or template]

Best regards,
John Doe

---
Email: john@gmail.com
Phone: +1 234 567 8900
LinkedIn: linkedin.com/in/johndoe
Portfolio: johndoe.com

This application was submitted via ApplyRush.AI
```

**Attachments:**
- `John_Doe_Resume.pdf`

### Step 4: Database Recording
The system creates multiple records:

**Applications Collection:**
```javascript
{
  "_id": ObjectId("..."),
  "user_id": "68e228dcb3cb0ec651a59537",
  "job_id": "68e23456789...",
  "job": { /* full job data */ },
  "status": "applied",
  "source": "auto_apply",
  "application_method": "email",  // ← Indicates real email sent
  "application_result": {
    "success": true,
    "method": "email",
    "recipient": "hiring@company.com",
    "forwarding_email": "john.68e228dc@apply.applyrush.ai",
    "sent_at": "2025-10-05T..."
  },
  "cover_letter": "...",
  "resume_version": "v2.3",
  "forwarding_email": "john.68e228dc@apply.applyrush.ai",
  "applied_at": ISODate("2025-10-05T..."),
  "created_at": ISODate("2025-10-05T...")
}
```

**Sent Emails Collection:**
```javascript
{
  "_id": ObjectId("..."),
  "user_id": ObjectId("68e228dcb3cb0ec651a59537"),
  "job_id": "68e23456789...",
  "job_title": "Senior Software Engineer",
  "company": "YourCompany",
  "sent_to": "hiring@company.com",
  "reply_to_forwarding": "john.68e228dc@apply.applyrush.ai",
  "sent_at": ISODate("2025-10-05T..."),
  "email_type": "job_application",
  "status": "sent"
}
```

### Step 5: Receiving Company Replies
When the company replies to `john.68e228dc@apply.applyrush.ai`:

1. **Email Received** (via webhook/SMTP server)
2. **Parse Email Content**
   - Extract sender, subject, body
   - Detect email type using keywords

3. **Email Type Detection:**
   ```python
   # Types detected:
   - "interview" → Keywords: interview, schedule, call, meeting
   - "rejection" → Keywords: regret, unfortunately, not moving forward
   - "offer" → Keywords: offer, congratulations, pleased to offer
   - "info_request" → Keywords: additional information, reference check
   - "general" → Everything else
   ```

4. **Auto-Update Application Status:**
   ```python
   if email_type == "interview":
       status = "interview"
   elif email_type == "offer":
       status = "offer"
   elif email_type == "rejection":
       status = "rejected"
   ```

5. **Forward to User's Real Email:**
   ```
   From: notifications@apply.applyrush.ai
   To: john@gmail.com
   Subject: Fwd: Interview Invitation - Senior Software Engineer

   [Original company email content]
   ```

---

## 🔧 Configuration

### SMTP Settings
Add to `.env`:
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@applyrush.ai
FROM_NAME=ApplyRush.AI
```

### Email Forwarding Domain
The forwarding domain is configured in `EmailForwardingService`:
```python
def __init__(self, db, domain: str = "apply.applyrush.ai"):
    self.domain = domain
```

**DNS Setup Required:**
1. Add MX records for `apply.applyrush.ai`
2. Configure email receiving webhook/SMTP server
3. Point to your backend API endpoint for processing

---

## 🧪 Testing

### Run Test Script
```bash
cd /home/ahmed-elkordy/researchs/applyrush.ai/jobhire-ai-backend
python scripts/test_email_application.py
```

### Manual Testing
1. Find a test job with email application
2. Trigger auto-apply
3. Check if email was sent
4. Reply to the forwarding email
5. Verify reply is received and parsed

---

## 📊 Monitoring

### Check Application Method
```javascript
// MongoDB query
db.applications.find({
  "application_method": "email"
})

// Count email vs database-only
db.applications.aggregate([
  {
    $group: {
      _id: "$application_method",
      count: { $sum: 1 }
    }
  }
])
```

### View Sent Emails
```javascript
db.sent_emails.find({
  "email_type": "job_application"
}).sort({ sent_at: -1 })
```

### Check Forwarding Email Stats
```javascript
db.forwarding_emails.find({
  "user_id": ObjectId("...")
})
```

---

## 🚀 Production Deployment

### 1. Email Service Setup
Choose one:
- **Gmail SMTP** (for testing, 500 emails/day limit)
- **SendGrid** (recommended, 100 emails/day free)
- **AWS SES** (production-grade, $0.10 per 1000 emails)
- **Mailgun** (good for high volume)

### 2. Domain Configuration
1. Purchase/configure domain: `apply.applyrush.ai`
2. Add DNS records:
   ```
   MX 10 mail.apply.applyrush.ai
   TXT "v=spf1 include:_spf.applyrush.ai ~all"
   ```
3. Setup DKIM for better deliverability

### 3. Email Receiving
Options:
- **AWS SES + Lambda** (auto-parse and forward)
- **SendGrid Inbound Parse** (webhook to API)
- **Cloudflare Email Routing** (forward to webhook)

### 4. Rate Limiting
Add rate limits to prevent spam:
```python
# Max 50 applications per user per day
MAX_APPLICATIONS_PER_DAY = 50

# Max 200 emails per hour globally
MAX_EMAILS_PER_HOUR = 200
```

---

## 💡 Features

### ✅ Implemented
- [x] Unique forwarding email per user
- [x] Email application sending with attachments
- [x] Reply-To header for tracking
- [x] Cover letter integration
- [x] Resume attachment
- [x] Database recording
- [x] Email type detection
- [x] Auto-status updates
- [x] Integration with auto-apply

### 🔮 Future Enhancements
- [ ] Email template customization per user
- [ ] Follow-up email automation
- [ ] Email analytics dashboard
- [ ] A/B testing for email templates
- [ ] Multi-language support
- [ ] Calendar integration for interview scheduling
- [ ] Email signature customization
- [ ] Thread tracking (multiple replies)

---

## 🐛 Troubleshooting

### Email Not Sending
1. Check SMTP credentials in `.env`
2. Verify SMTP server allows the connection
3. Check firewall/port 587 access
4. Review logs: `tail -f logs/email_service.log`

### Forwarding Email Not Working
1. Verify DNS MX records
2. Check email receiving webhook is configured
3. Test with: `dig apply.applyrush.ai MX`

### Application Shows "database_only"
1. Job doesn't have email application method
2. Add `apply_email` field to job
3. Or update job scraper to extract email

---

## 📝 Code Examples

### Create Forwarding Email
```python
from app.services.email_forwarding_service import EmailForwardingService

service = EmailForwardingService(db)
email_doc = service.create_user_forwarding_email(user_id)
print(f"Forwarding email: {email_doc['forwarding_address']}")
```

### Send Job Application
```python
from app.services.job_application_email_service import send_job_application_email

result = await send_job_application_email(
    db=db,
    user_id="68e228dcb3cb0ec651a59537",
    job_data={
        "id": "job123",
        "title": "Senior Engineer",
        "company": "TechCo",
        "apply_email": "hiring@techco.com"
    },
    resume_path="/path/to/resume.pdf",
    cover_letter="Dear Hiring Manager..."
)

if result["success"]:
    print(f"Sent to {result['recipient']}")
```

### Parse Received Email
```python
from app.services.email_forwarding_service import EmailForwardingService

service = EmailForwardingService(db)
email_doc = service.save_received_email({
    "to": "john.68e228dc@apply.applyrush.ai",
    "from": "hiring@company.com",
    "subject": "Interview Invitation",
    "body": "We'd like to schedule an interview..."
})

# Auto-detects type and updates application status
print(f"Email type: {email_doc['email_type']}")  # "interview"
```

---

## 🎓 Summary

**What You Get:**
1. ✅ **Real Applications** - Actual emails sent to companies
2. ✅ **Professional** - Well-formatted with resume attachments
3. ✅ **Trackable** - Unique email per user tracks all replies
4. ✅ **Automated** - Integrates with auto-apply system
5. ✅ **Smart** - Auto-detects interview invites and offers
6. ✅ **Scalable** - Uses proven email services

**vs. Just Database Updates:**
- ❌ Database only: Company never sees application
- ✅ Email system: Real application submitted
- ✅ Company can reply and schedule interviews
- ✅ System auto-updates status based on responses

---

Made with ❤️ by ApplyRush.AI Team
