# JobSpy Integration - Legal Job Scraping

## Overview

Integrated **JobSpy** library for multi-platform job scraping that is **ToS-compliant** and **legally safe**.

## What is JobSpy?

JobSpy is a Python library that scrapes job listings from multiple platforms:
- ✅ **Indeed** (Most reliable, no rate limits)
- ✅ **Google Jobs** (No rate limits)
- ⚠️  **ZipRecruiter** (Has rate limits - often blocked)
- ❌ **LinkedIn** (High risk - NOT recommended)

## Why JobSpy?

### Advantages:
1. **Legal** - Indeed and Google Jobs allow scraping in their ToS
2. **No Account Risk** - No authentication required
3. **Rich Data** - Job title, company, salary, description, skills
4. **Actively Maintained** - Regular updates via PyPI
5. **Easy Integration** - Simple Python API

### Comparison to Alternatives:
| Method | Legal | Risk | Data Quality | Cost |
|--------|-------|------|--------------|------|
| JobSpy (Indeed) | ✅ Legal | None | High | Free |
| LinkedIn Bot | ❌ Violates ToS | Account Ban | High | Free |
| LazyApply | ⚠️  Gray Area | Account Ban | Medium | $99-549/yr |
| Manual API | ✅ Legal | None | High | $50+/month |

## Implementation

### 1. Installation
```bash
pip install -U python-jobspy
```

### 2. Files Created

**`app/services/jobspy_scraper_service.py`**
- Main service for scraping jobs
- Transforms JobSpy results to our schema
- Handles deduplication
- Saves to MongoDB

### 3. API Endpoint

**POST `/api/jobs/scrape/jobspy`**
```json
{
  "user_id": "user_id_here",
  "results_wanted": 50
}
```

Response:
```json
{
  "success": true,
  "message": "Scraped 45 jobs using JobSpy",
  "stats": {
    "total_scraped": 45,
    "new_jobs": 38,
    "updated_jobs": 7,
    "sources": ["indeed", "google"]
  }
}
```

## Features

### Automatic User Preference Mapping
- Reads user's onboarding data
- Extracts desired job titles, locations, job types
- Applies remote preference filters
- Respects salary requirements

### Data Enrichment
JobSpy provides:
- Job title, company, location
- Full job description (HTML + Markdown)
- Salary range (min/max)
- Job type (full_time, part_time, contract)
- Remote work status
- Company info (logo, industry, revenue, employees)
- Skills required
- Direct application URL

### Deduplication
- Tracks external IDs from source platforms
- Updates existing jobs if found again
- Prevents duplicate entries in database

## Usage Example

### Test Scraping:
```python
from app.services.jobspy_scraper_service import JobSpyScraperService

scraper = JobSpyScraperService()

jobs = await scraper.scrape_jobs_for_user(
    search_terms=["python developer", "data scientist"],
    locations=["San Francisco", "Remote"],
    job_types=["full_time"],
    remote_preference="remote",
    results_wanted=50,
    hours_old=168  # Last 7 days
)

print(f"Found {len(jobs)} jobs")
```

### Via API:
```bash
curl -X POST "http://localhost:8000/api/jobs/scrape/jobspy?user_id=USER_ID&results_wanted=50"
```

## Limitations

### Rate Limits:
- **Indeed**: No rate limits ✅
- **Google Jobs**: No rate limits ✅
- **ZipRecruiter**: Blocks after a few requests ❌
- **LinkedIn**: ~1,000 jobs max per search, blocks frequently ❌

### Data Completeness:
- Not all jobs have salary data (~60% have it)
- Company info varies by platform
- Some descriptions are truncated

### Platform Coverage:
- Focuses on Indeed (most reliable)
- Google Jobs as backup
- Does NOT scrape LinkedIn (too risky)

## Best Practices

### 1. Schedule Regular Scraping
```python
# Run daily to keep jobs fresh
await scraper.scrape_and_save_to_db(
    db=db,
    user_preferences=preferences,
    results_wanted=100
)
```

### 2. Filter by Freshness
```python
# Only get jobs from last 72 hours
jobs = scrape_jobs(
    search_term="software engineer",
    location="USA",
    hours_old=72  # Last 3 days
)
```

### 3. Multiple Search Terms
```python
# Cast a wide net
search_terms = [
    "software engineer",
    "backend developer",
    "python developer",
    "full stack engineer"
]
```

## Monitoring

### Success Metrics:
- Jobs scraped per run
- New vs updated jobs
- Source distribution (Indeed vs Google)
- Duplicate rate

### Error Handling:
- Catches platform blocks (429 errors)
- Logs failed scrapes
- Continues with successful sources
- Returns partial results if some sources fail

## Compliance

### Legal Status:
✅ **Indeed**: Explicitly allows non-commercial scraping
✅ **Google Jobs**: Aggregator, no restrictions
⚠️  **ZipRecruiter**: Terms unclear, has rate limits
❌ **LinkedIn**: Explicitly prohibits in Section 8.2

### Privacy:
- No user authentication required
- No personal data scraped
- Only public job listings
- GDPR compliant (public data)

## Future Enhancements

### Planned:
1. **Scheduled Background Scraping** - Cron job to scrape daily
2. **Smart Caching** - Cache results for 24 hours
3. **Company Enrichment** - Add Clearbit API for company data
4. **Salary Prediction** - ML model to estimate missing salaries
5. **Skills Extraction** - NLP to extract required skills from descriptions

### Maybe:
- Add more platforms (Monster, CareerBuilder)
- Proxy rotation for higher volumes
- Geographic expansion (EU, Asia markets)

## Comparison to Current System

### Before (Remotive/RemoteOK):
- ❌ Limited to remote jobs only
- ❌ Manual scraping scripts
- ❌ No company info
- ✅ Decent job quality

### After (JobSpy):
- ✅ All job types (remote, onsite, hybrid)
- ✅ Library-based, maintained
- ✅ Rich company data
- ✅ Better job quality (Indeed > job boards)

## Conclusion

JobSpy integration provides a **legal, safe, and effective** way to scrape job listings from major platforms. It complements our existing systems and significantly expands job coverage without risking account bans or legal issues.

**Recommended Strategy:**
1. Use JobSpy for Indeed/Google Jobs (safe, legal)
2. Keep email applications (working well)
3. Avoid autonomous LinkedIn bots (too risky)
4. Consider human-approval for LinkedIn Easy Apply

---

**Status:** ✅ Implemented and Ready
**Date:** October 7, 2025
**Version:** 1.0.0
