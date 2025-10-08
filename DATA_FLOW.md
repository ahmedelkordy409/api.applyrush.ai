# ApplyRush.AI - Complete Data Flow Documentation

## Overview
This document explains how user data flows through the entire system, from onboarding to auto-apply.

## Data Collection Points

### 1. Onboarding Flow (`/onboarding/*`)
**Collected Data:**
```json
{
  "work_authorization": "us_citizen | green_card | work_visa | need_sponsorship",
  "salary_min": 100000,
  "salary_max": 150000,
  "salary_currency": "USD",
  "work_situation": "employed | unemployed | student | freelance",
  "job_titles": ["Software Engineer", "Full Stack Developer"],
  "years_of_experience": 5,
  "education_level": "bachelors | masters | phd",
  "industries": ["Technology", "Finance"],
  "timezone": "America/New_York",
  "relocation_willing": true,
  "preferred_locations": ["New York", "San Francisco", "Remote"],
  "work_location_preference": "remote | hybrid | onsite | flexible",
  "work_types": ["full_time", "contract"],
  "visa_sponsorship_needed": false,
  "skills": ["Python", "React", "Node.js"],
  "excluded_companies": ["Company A", "Company B"]
}
```

**Stored in MongoDB:**
- Collection: `users`
- Field: `onboarding_data`

---

### 2. Profile Page (`/dashboard/profile`)
**Collected Data:**
```json
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "github_url": "https://github.com/johndoe",
  "portfolio_url": "https://johndoe.com",
  "bio": "Experienced software engineer...",
  "resume_url": "https://storage.../resume.pdf"
}
```

**Stored in MongoDB:**
- Collection: `users`
- Fields: `profile.*`

---

### 3. Settings Page (`/dashboard/settings`)
**Collected Data:**
```json
{
  "match_threshold": "open | good-fit | top",
  "approval_mode": "instant | delayed | approval",
  "auto_apply_delay": 24,
  "search_active": true,
  "ai_features": {
    "cover_letters": true,
    "resume_enhancement": true
  }
}
```

**Stored in MongoDB:**
- Collection: `users`
- Field: `preferences`

---

### 4. Resume Management
**Collected Data:**
```json
{
  "user_id": "user_123",
  "filename": "resume.pdf",
  "file_url": "https://storage.../resume.pdf",
  "is_primary": true,
  "parsed_data": {
    "skills": ["Python", "JavaScript"],
    "experience": [
      {
        "company": "Tech Corp",
        "position": "Senior Engineer",
        "duration": "2020-2023"
      }
    ],
    "education": [
      {
        "institution": "MIT",
        "degree": "BS Computer Science",
        "year": 2015
      }
    ]
  },
  "ats_optimized": true
}
```

**Stored in MongoDB:**
- Collection: `resumes`

---

## Background Job Processing

### Job Matching Algorithm

The background job runs **every 30 minutes** and performs these steps:

#### Step 1: Find Active Users
```python
active_users = await db.users.find({
    "preferences.search_active": True
}).to_list(length=None)
```

#### Step 2: For Each User, Calculate Match Scores

**Scoring Breakdown (Total: 100 points):**

1. **Job Title Match (25 points)**
   - Uses: `onboarding_data.job_titles`
   - Exact match: 25 points
   - Partial match: 15-20 points
   - Keyword overlap: 10-15 points

2. **Salary Match (20 points)**
   - Uses: `onboarding_data.salary_min`, `salary_max`
   - Perfect fit: 20 points
   - Above minimum: 15-18 points
   - Below minimum: 0 points

3. **Location Match (15 points)**
   - Uses: `onboarding_data.preferred_locations`, `relocation_willing`
   - Remote job: 15 points (if user wants remote)
   - Exact location match: 15 points
   - Willing to relocate: 10 points

4. **Work Type Match (15 points)**
   - Uses: `onboarding_data.work_types`, `work_location_preference`
   - Perfect match: 15 points
   - Partial match: 8-10 points

5. **Experience Match (10 points)**
   - Uses: `onboarding_data.years_of_experience`, `education_level`
   - Perfect fit: 10 points
   - Close match: 7-8 points
   - Overqualified: 5 points

6. **Industry Match (10 points)**
   - Uses: `onboarding_data.industries`
   - Industry mentioned in job: 10 points

7. **Skills Match (5 points)**
   - Uses: `onboarding_data.skills`, `resumes.parsed_data.skills`
   - 5+ skills match: 5 points
   - 3+ skills match: 4 points
   - 1+ skills match: 3 points

**User Preference Adjustments:**
- `match_threshold: "top"` → Requires 85+ score
- `match_threshold: "good-fit"` → Requires 70+ score
- `match_threshold: "open"` → Requires 60+ score

#### Step 3: Apply Hard Filters

Before adding to queue, check:
1. **Excluded Companies**: Skip if `job.company` in `onboarding_data.excluded_companies`
2. **Visa Sponsorship**: Skip if user needs sponsorship but job doesn't offer it
3. **Work Authorization**: Check compatibility

#### Step 4: Add to Application Queue

```json
{
  "user_id": "user_123",
  "job_id": "job_456",
  "status": "pending | approved | rejected | auto_applied",
  "match_score": 85,
  "match_reasons": [
    "Job title matches your preferences (25%)",
    "Salary range aligns with expectations",
    "Location matches preferences",
    "Your skills match job requirements"
  ],
  "match_breakdown": {
    "title": 25,
    "salary": 20,
    "location": 15,
    "work_type": 15,
    "experience": 8,
    "industry": 10,
    "skills": 5
  },
  "job": { /* full job details */ },
  "created_at": "2025-10-05T12:00:00Z",
  "expires_at": "2025-10-12T12:00:00Z",
  "auto_apply_after": "2025-10-06T12:00:00Z"  // Based on approval_mode
}
```

---

### Auto-Apply Processing

Runs **every 5 minutes**:

#### Step 1: Find Ready Applications
```python
ready_applications = await db.application_queue.find({
    "status": "approved",
    "auto_apply_after": {"$lte": datetime.utcnow()}
}).to_list(length=100)
```

#### Step 2: For Each Application

1. **Get User Resume**
   ```python
   resume = await db.resumes.find_one({
       "user_id": user_id,
       "is_primary": True
   })
   ```

2. **Generate AI Cover Letter** (if enabled)
   ```python
   if user.preferences.ai_features.cover_letters:
       cover_letter = await ai_service.generate_cover_letter(
           user_profile=user,
           job_details=job,
           resume=resume
       )
   ```

3. **Create Application Record**
   ```json
   {
       "user_id": "user_123",
       "job_id": "job_456",
       "job": { /* full job details */ },
       "status": "applied",
       "source": "platform",
       "cover_letter": "Generated cover letter text...",
       "resume_version": "v1",
       "applied_at": "2025-10-06T12:00:00Z"
   }
   ```

4. **Update Queue Status**
   ```python
   await db.application_queue.update_one(
       {"_id": queue_item_id},
       {"$set": {"status": "auto_applied", "application_id": app_id}}
   )
   ```

---

## Frontend Data Display

### Preview Page (`/dashboard/preview`)

**Fetches:**
```python
# Pending applications
pending = await db.application_queue.find({
    "user_id": user_id,
    "status": "pending"
}).to_list(length=20)

# Approved applications
approved = await db.application_queue.find({
    "user_id": user_id,
    "status": "approved"
}).to_list(length=20)
```

**Displays:**
- Job title, company, location
- Match score with color coding (85+ = green, 70+ = blue, 60+ = yellow)
- Match reasons (why it's a good fit)
- Approval buttons (if in approval mode)
- Auto-apply countdown (if in delayed mode)

### Completed Page (`/dashboard/completed`)

**Fetches:**
```python
applications = await db.applications.find({
    "user_id": user_id
}).sort("applied_at", -1).to_list(length=100)
```

**Displays:**
- All submitted applications
- Status tracking (applied, reviewing, interview, offer, etc.)
- Application statistics
- Response rates

---

## MongoDB Collections Schema

### `users`
```json
{
  "_id": ObjectId,
  "email": String,
  "profile": {
    "full_name": String,
    "phone": String,
    // ... profile data
  },
  "onboarding_data": {
    "job_titles": [String],
    "salary_min": Number,
    // ... onboarding data
  },
  "preferences": {
    "match_threshold": String,
    "search_active": Boolean,
    // ... preferences
  }
}
```

### `application_queue`
```json
{
  "_id": ObjectId,
  "user_id": String,
  "job_id": String,
  "status": String,
  "match_score": Number,
  "match_reasons": [String],
  "match_breakdown": Object,
  "job": Object,
  "created_at": Date,
  "expires_at": Date,
  "auto_apply_after": Date
}
```

### `applications`
```json
{
  "_id": ObjectId,
  "user_id": String,
  "job_id": String,
  "job": Object,
  "status": String,
  "cover_letter": String,
  "resume_version": String,
  "applied_at": Date,
  "response_received_at": Date,
  "notes": String
}
```

### `resumes`
```json
{
  "_id": ObjectId,
  "user_id": String,
  "filename": String,
  "file_url": String,
  "is_primary": Boolean,
  "parsed_data": {
    "skills": [String],
    "experience": [Object],
    "education": [Object]
  },
  "ats_optimized": Boolean
}
```

---

## API Endpoints

### Data Collection
- `POST /api/v1/onboarding/complete` - Save onboarding data
- `PUT /api/v1/users/profile` - Update profile
- `PUT /api/v1/users/preferences` - Update settings
- `POST /api/v1/resumes/upload` - Upload resume

### Job Matching
- `GET /api/v1/applications/queue/database` - Get application queue
- `POST /api/v1/applications/queue/database` - Approve/reject/find matches
- `GET /api/v1/applications/database` - Get completed applications

### Background Jobs
- `GET /api/v1/background-jobs/status` - View scheduler status
- `POST /api/v1/background-jobs/trigger/find-matches` - Manual trigger
- `POST /api/v1/background-jobs/trigger/auto-apply` - Manual trigger

---

## Summary

**Data Flow:**
1. User completes onboarding → Stored in `users.onboarding_data`
2. User sets preferences in settings → Stored in `users.preferences`
3. Background job (every 30 min) → Finds jobs and calculates match scores
4. Jobs added to `application_queue` with scores
5. Frontend displays queue in Preview page
6. User approves OR auto-approve (based on `approval_mode`)
7. Auto-apply job (every 5 min) → Submits applications
8. Applications stored in `applications` collection
9. Frontend displays in Completed page

**Everything is connected and automated!** 🚀
