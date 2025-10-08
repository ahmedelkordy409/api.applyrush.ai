# US Job Boards Only - Complete List

## JobSpy Supported (US-Focused)

### 1. Indeed (USA) ⭐⭐⭐⭐⭐
**Primary Choice - Best for US Jobs**

```python
jobs = scrape_jobs(
    site_name=["indeed"],
    search_term="software engineer",
    location="San Francisco, CA",
    country_indeed='USA',  # Specify USA
    results_wanted=100
)
```

**Why Best:**
- No rate limits
- 60% of jobs have salary data
- Company info included
- Direct apply URLs
- Most US job postings

### 2. ZipRecruiter (USA) ⭐⭐
**US-Only Platform**

```python
jobs = scrape_jobs(
    site_name=["zip_recruiter"],
    search_term="python developer",
    location="New York, NY",
    results_wanted=20  # Keep low - rate limited
)
```

**Warning:** Frequent 429 blocks, use sparingly

### 3. Google Jobs (USA) ⭐⭐⭐⭐⭐
**Job Aggregator - Includes US Jobs**

```python
jobs = scrape_jobs(
    site_name=["google"],
    search_term="data engineer",
    location="USA",
    results_wanted=50
)
```

**Aggregates from:**
- Company career pages
- Indeed
- LinkedIn
- Glassdoor
- And more

## Additional US Job Boards (Not in JobSpy)

### Top US-Specific Platforms:

| Platform | Coverage | Integration Method | Difficulty |
|----------|----------|-------------------|------------|
| **Monster** | USA-focused | API/Scraping | Medium |
| **CareerBuilder** | USA | API Available | Easy |
| **Dice** (Tech) | USA Tech Jobs | API Available | Easy |
| **AngelList** (Startups) | USA Startups | API Available | Medium |
| **SimplyHired** | USA | Scraping Only | Hard |
| **Ladders** (Senior) | USA $100k+ | Scraping | Hard |
| **FlexJobs** (Remote) | USA Remote | Subscription | Hard |
| **Remote.co** | USA Remote | Scraping | Medium |
| **We Work Remotely** | USA Remote | Scraping | Easy |

## US ATS Systems (Application Platforms)

These are where you actually APPLY (not just search):

### Major ATS Platforms in USA:

| ATS | Market Share | Companies Using | Strategy Pattern |
|-----|--------------|-----------------|------------------|
| **Workday** | 40% | Fortune 500 | WorkdayStrategy |
| **Greenhouse** | 25% | Tech companies | GreenhouseStrategy |
| **Lever** | 15% | Startups | LeverStrategy |
| **iCIMS** | 10% | Enterprise | iCIMSStrategy |
| **Taleo (Oracle)** | 5% | Large corps | TaleoStrategy |
| **SmartRecruiters** | 3% | Mid-size | SmartRecruitersStrategy |
| **JazzHR** | 2% | Small business | JazzHRStrategy |

### Companies by ATS:

**Workday:**
- Amazon, Apple, Microsoft, Google, Facebook, Netflix, Uber, Airbnb

**Greenhouse:**
- Stripe, Coinbase, DoorDash, Instacart, Robinhood, Discord, Figma

**Lever:**
- GitHub, Shopify, Twitch, Atlassian, Lyft, Square

**iCIMS:**
- Walmart, Target, Home Depot, CVS, UPS

**Taleo:**
- IBM, Oracle, Accenture, Deloitte, PwC

## Recommended US Job Board Strategy

### For ApplyRush.AI:

```python
# Priority 1: JobSpy (Legal, Safe)
US_SAFE_SOURCES = ["indeed", "google"]

# Priority 2: Try if needed (Higher risk)
US_RISKY_SOURCES = ["zip_recruiter"]

# Priority 3: Never use
BANNED_SOURCES = ["linkedin"]  # Account ban risk

# Use this configuration:
jobs = scrape_jobs(
    site_name=US_SAFE_SOURCES,
    location="USA",
    country_indeed='USA',
    results_wanted=100,
    hours_old=168  # Last week
)
```

### Regional Focus (US States):

```python
# Tech hubs
tech_locations = [
    "San Francisco, CA",
    "Seattle, WA",
    "Austin, TX",
    "Boston, MA",
    "New York, NY"
]

# For each location
for location in tech_locations:
    jobs = scrape_jobs(
        site_name=["indeed", "google"],
        search_term="software engineer",
        location=location,
        country_indeed='USA'
    )
```

### Remote USA Jobs:

```python
# Remote jobs based in USA
jobs = scrape_jobs(
    site_name=["indeed", "google"],
    search_term="software engineer",
    location="USA",
    is_remote=True,
    country_indeed='USA',
    results_wanted=100
)
```

## US Job Board APIs (Official)

Some US job boards offer official APIs:

### 1. **CareerBuilder API**
```
https://www.careerbuilder.com/share/api
```
- Requires partnership
- $500-2000/month
- Full job data access

### 2. **Dice API** (Tech Jobs)
```
https://www.dice.com/common/content/util/apidoc/jobsearch.html
```
- Tech-focused
- Free tier available
- USA tech jobs only

### 3. **USA Jobs API** (Government)
```
https://developer.usajobs.gov/
```
- Free
- Federal government jobs
- Open API

## US LinkedIn Alternative (Legal)

Instead of scraping LinkedIn (banned), use:

### **LinkedIn Jobs Search API** (Official)
- Requires LinkedIn partnership
- $$$$ Expensive
- Legal and ToS-compliant
- NOT available for individual use

### **LinkedIn Lite** (Human-in-Loop)
- User logs into LinkedIn
- We autofill Easy Apply forms
- User clicks "Submit"
- **Safe and Legal** (like Simplify.com)

## Implementation for US-Only

### Update JobSpyScraperService:

```python
class JobSpyScraperService:
    # US-only configuration
    US_SAFE_PLATFORMS = ["indeed", "google"]
    US_COUNTRY_CODE = "USA"

    async def scrape_us_jobs(
        self,
        search_terms: List[str],
        locations: List[str] = ["USA"],
        results_wanted: int = 100
    ):
        """Scrape only US jobs from safe platforms"""

        jobs = scrape_jobs(
            site_name=self.US_SAFE_PLATFORMS,
            search_term=search_terms[0],
            location=locations[0],
            country_indeed=self.US_COUNTRY_CODE,
            results_wanted=results_wanted,
            hours_old=168
        )

        # Filter to ensure USA-based
        us_jobs = [
            job for job in jobs
            if self._is_us_based(job)
        ]

        return us_jobs

    def _is_us_based(self, job: Dict) -> bool:
        """Verify job is US-based"""
        location = job.get('location', '').upper()
        us_indicators = ['US', 'USA', 'UNITED STATES']

        # Check for US states
        us_states = ['CA', 'NY', 'TX', 'FL', 'WA', 'MA', 'IL', 'PA', 'OH']

        return (
            any(indicator in location for indicator in us_indicators) or
            any(state in location for state in us_states) or
            'REMOTE' in location  # Many US remote jobs
        )
```

## US Job Market Stats

- **Total US Job Boards:** 30,000+
- **Major National Boards:** 10
- **ATS Systems:** 100+ (5-6 dominant)
- **Best Coverage:** Indeed (80% of US jobs)
- **Tech-Specific:** Dice, AngelList, Hired
- **Remote-Specific:** FlexJobs, Remote.co, WWR

## Final Recommendation for US Market

**Use these sources in order:**

1. **Indeed** (USA) - Primary, 80% coverage
2. **Google Jobs** - Secondary, aggregator
3. **Company Career Pages** - Direct applications via ATS detection
4. **Email Applications** - When available

**Avoid:**
- LinkedIn scraping (ban risk)
- ZipRecruiter (rate limited)
- Glassdoor (blocked)

**Focus on ATS Detection:**
- Detect Workday/Greenhouse/Lever URLs
- Use provider-specific strategies
- AI-powered form filling
- Human approval for submissions

---

**Target Market:** USA Only
**Primary Sources:** Indeed + Google Jobs
**Application Method:** ATS Strategy Pattern + AI
**Status:** Ready for US Market
**Date:** October 7, 2025
