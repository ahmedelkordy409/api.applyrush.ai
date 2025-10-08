"""
Test JobSpy library for multi-platform job scraping
"""
from jobspy import scrape_jobs
import pandas as pd

# Test Indeed scraping (most reliable, no rate limits)
print("🔍 Testing JobSpy - Indeed Scraper")
print("=" * 50)

jobs = scrape_jobs(
    site_name=["indeed", "zip_recruiter"],
    search_term="python developer",
    location="USA",
    results_wanted=10,
    hours_old=72,  # Jobs posted in last 72 hours
    country_indeed='USA'
)

print(f"\n✅ Found {len(jobs)} jobs")
print("\n📊 Available columns:")
print(jobs.columns.tolist())

if len(jobs) > 0:
    print("\n📝 Sample job:")
    sample = jobs.iloc[0]
    print(f"Title: {sample['title']}")
    print(f"Company: {sample['company']}")
    print(f"Location: {sample['location']}")
    print(f"Job Type: {sample.get('job_type', 'N/A')}")
    print(f"Salary: {sample.get('min_amount', 'N/A')} - {sample.get('max_amount', 'N/A')}")
    print(f"Posted: {sample.get('date_posted', 'N/A')}")
    print(f"Description (first 200 chars): {str(sample['description'])[:200]}...")
    print(f"Job URL: {sample.get('job_url', 'N/A')}")

# Save to CSV for inspection
jobs.to_csv('/tmp/jobspy_test_results.csv', index=False)
print(f"\n💾 Saved results to /tmp/jobspy_test_results.csv")
