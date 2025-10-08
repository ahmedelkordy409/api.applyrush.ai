"""
LinkedIn Job Application Service
Handles automated job applications on LinkedIn using browser automation
"""

import asyncio
import json
import time
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    ElementClickInterceptedException,
    StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager

import structlog
from app.core.config import settings
from app.core.database import get_database

logger = structlog.get_logger()


class LinkedInApplicationStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"
    REQUIRES_MANUAL = "requires_manual"
    DAILY_LIMIT_REACHED = "daily_limit_reached"


@dataclass
class LinkedInJob:
    job_id: str
    title: str
    company: str
    location: str
    posted_time: str
    job_url: str
    easy_apply: bool = False
    salary_range: Optional[str] = None
    job_description: Optional[str] = None


@dataclass
class ApplicationResult:
    job_id: str
    status: LinkedInApplicationStatus
    message: str
    timestamp: datetime
    application_data: Dict[str, Any] = None
    error_details: Optional[str] = None


class LinkedInAutomation:
    """LinkedIn job application automation using Selenium"""
    
    def __init__(self):
        self.driver = None
        self.wait = None
        self.logged_in = False
        self.daily_applications = 0
        self.max_daily_applications = settings.LINKEDIN_APPLY_LIMIT
        
        # Random delays to mimic human behavior
        self.min_delay = 2
        self.max_delay = 5
        
    async def initialize_browser(self) -> bool:
        """Initialize Chrome browser with proper configuration"""
        try:
            chrome_options = Options()
            
            if settings.LINKEDIN_HEADLESS:
                chrome_options.add_argument("--headless")
            
            # Anti-detection measures
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            # Performance optimizations
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")
            chrome_options.page_load_strategy = 'eager'
            
            self.driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Remove automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 10)
            
            logger.info("Browser initialized successfully")
            return True
            
        except Exception as e:
            logger.error("Failed to initialize browser", error=str(e))
            return False
    
    async def login_to_linkedin(self) -> bool:
        """Login to LinkedIn with provided credentials"""
        if not settings.LINKEDIN_EMAIL or not settings.LINKEDIN_PASSWORD:
            logger.error("LinkedIn credentials not provided in environment variables")
            return False
        
        try:
            logger.info("Attempting to login to LinkedIn")
            self.driver.get("https://www.linkedin.com/login")
            
            # Random delay
            await self._random_delay()
            
            # Find and fill email
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            await self._human_type(email_field, settings.LINKEDIN_EMAIL)
            
            # Find and fill password
            password_field = self.driver.find_element(By.ID, "password")
            await self._human_type(password_field, settings.LINKEDIN_PASSWORD)
            
            # Click sign in
            sign_in_btn = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            sign_in_btn.click()
            
            # Wait for redirect and check if logged in
            await asyncio.sleep(5)
            
            # Check if we're on the feed page (successful login)
            if "feed" in self.driver.current_url or "dashboard" in self.driver.current_url:
                self.logged_in = True
                logger.info("Successfully logged in to LinkedIn")
                return True
            else:
                # Check for verification challenge
                if "challenge" in self.driver.current_url:
                    logger.warning("LinkedIn requires verification - manual intervention needed")
                    return False
                
                logger.error("Login failed - redirected to unexpected page", url=self.driver.current_url)
                return False
                
        except Exception as e:
            logger.error("LinkedIn login failed", error=str(e))
            return False
    
    async def search_jobs(self, 
                         keywords: str, 
                         location: str = "", 
                         easy_apply_only: bool = True,
                         posted_within: str = "24h") -> List[LinkedInJob]:
        """Search for jobs on LinkedIn"""
        
        if not self.logged_in:
            logger.error("Must be logged in to search jobs")
            return []
        
        try:
            # Build search URL
            base_url = "https://www.linkedin.com/jobs/search/"
            params = {
                "keywords": keywords,
                "location": location,
                "f_TPR": f"r{self._convert_time_filter(posted_within)}",
                "f_AL": "true" if easy_apply_only else None
            }
            
            search_url = base_url + "?" + "&".join([f"{k}={v}" for k, v in params.items() if v])
            
            logger.info("Searching for jobs", keywords=keywords, location=location, url=search_url)
            self.driver.get(search_url)
            
            await self._random_delay(3, 6)
            
            # Wait for job listings to load
            job_cards = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".job-search-card"))
            )
            
            jobs = []
            for card in job_cards[:20]:  # Limit to first 20 jobs
                try:
                    job = await self._extract_job_info(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.warning("Failed to extract job info", error=str(e))
                    continue
            
            logger.info("Found jobs", count=len(jobs))
            return jobs
            
        except Exception as e:
            logger.error("Job search failed", error=str(e))
            return []
    
    async def apply_to_job(self, job: LinkedInJob, user_data: Dict[str, Any]) -> ApplicationResult:
        """Apply to a single job using LinkedIn Easy Apply"""
        
        if self.daily_applications >= self.max_daily_applications:
            return ApplicationResult(
                job_id=job.job_id,
                status=LinkedInApplicationStatus.DAILY_LIMIT_REACHED,
                message="Daily application limit reached",
                timestamp=datetime.utcnow()
            )
        
        try:
            logger.info("Applying to job", job_id=job.job_id, title=job.title, company=job.company)
            
            # Navigate to job page
            self.driver.get(job.job_url)
            await self._random_delay(2, 4)
            
            # Look for Easy Apply button
            try:
                easy_apply_btn = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".jobs-apply-button"))
                )
                
                if "Easy Apply" not in easy_apply_btn.text:
                    return ApplicationResult(
                        job_id=job.job_id,
                        status=LinkedInApplicationStatus.SKIPPED,
                        message="Not an Easy Apply job",
                        timestamp=datetime.utcnow()
                    )
                
                easy_apply_btn.click()
                await self._random_delay(1, 3)
                
            except TimeoutException:
                return ApplicationResult(
                    job_id=job.job_id,
                    status=LinkedInApplicationStatus.FAILED,
                    message="Easy Apply button not found",
                    timestamp=datetime.utcnow()
                )
            
            # Process application form(s)
            application_data = await self._process_application_flow(user_data)
            
            if application_data.get("success"):
                self.daily_applications += 1
                
                return ApplicationResult(
                    job_id=job.job_id,
                    status=LinkedInApplicationStatus.APPLIED,
                    message="Successfully applied",
                    timestamp=datetime.utcnow(),
                    application_data=application_data
                )
            else:
                return ApplicationResult(
                    job_id=job.job_id,
                    status=LinkedInApplicationStatus.FAILED,
                    message=application_data.get("error", "Application failed"),
                    timestamp=datetime.utcnow(),
                    error_details=application_data.get("details")
                )
                
        except Exception as e:
            logger.error("Job application failed", job_id=job.job_id, error=str(e))
            return ApplicationResult(
                job_id=job.job_id,
                status=LinkedInApplicationStatus.FAILED,
                message=str(e),
                timestamp=datetime.utcnow(),
                error_details=str(e)
            )
    
    async def _process_application_flow(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the multi-step Easy Apply application flow"""
        
        try:
            step_count = 0
            max_steps = 5
            
            while step_count < max_steps:
                # Check if we're in a modal
                modal_present = len(self.driver.find_elements(By.CSS_SELECTOR, ".jobs-easy-apply-modal")) > 0
                
                if not modal_present:
                    break
                
                step_count += 1
                logger.info("Processing application step", step=step_count)
                
                # Fill form fields on current step
                await self._fill_current_step_fields(user_data)
                
                # Look for Next or Submit button
                next_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".artdeco-button--primary, [aria-label*='Continue'], [aria-label*='Submit'], [aria-label*='Review']"
                )
                
                if not next_buttons:
                    # Try alternative selectors
                    next_buttons = self.driver.find_elements(By.XPATH, 
                        "//button[contains(text(), 'Next') or contains(text(), 'Continue') or contains(text(), 'Submit') or contains(text(), 'Review')]"
                    )
                
                if next_buttons:
                    # Click the first enabled button
                    for btn in next_buttons:
                        if btn.is_enabled():
                            await self._human_click(btn)
                            await self._random_delay(1, 3)
                            break
                    else:
                        # No enabled button found
                        logger.warning("No enabled next/submit button found")
                        break
                else:
                    logger.warning("No next/submit button found")
                    break
                
                # Check if application was submitted
                success_indicators = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".artdeco-inline-feedback--success, [data-test-modal-id='application-submitted']"
                )
                
                if success_indicators:
                    logger.info("Application submitted successfully")
                    return {"success": True, "steps_completed": step_count}
                
                # Check for errors
                error_indicators = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".artdeco-inline-feedback--error, .form-element-error"
                )
                
                if error_indicators:
                    error_text = error_indicators[0].text if error_indicators[0].text else "Form validation error"
                    logger.warning("Application form error", error=error_text)
                    return {"success": False, "error": error_text, "details": "Form validation failed"}
            
            # If we exit the loop without success, consider it failed
            return {"success": False, "error": "Application flow incomplete", "details": f"Completed {step_count} steps"}
            
        except Exception as e:
            logger.error("Application flow processing failed", error=str(e))
            return {"success": False, "error": str(e), "details": "Exception during application flow"}
    
    async def _fill_current_step_fields(self, user_data: Dict[str, Any]):
        """Fill form fields in the current application step"""
        
        # Phone number field
        phone_fields = self.driver.find_elements(By.CSS_SELECTOR, 
            "input[type='tel'], input[placeholder*='phone'], input[name*='phone']"
        )
        if phone_fields and user_data.get("phone"):
            await self._human_type(phone_fields[0], user_data["phone"])
        
        # Text inputs (experience, custom questions)
        text_fields = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
        for field in text_fields:
            placeholder = field.get_attribute("placeholder") or ""
            if "years" in placeholder.lower() and "experience" in placeholder.lower():
                if user_data.get("years_experience"):
                    await self._human_type(field, str(user_data["years_experience"]))
        
        # Dropdowns
        dropdowns = self.driver.find_elements(By.CSS_SELECTOR, "select")
        for dropdown in dropdowns:
            # Handle common dropdown types
            label = dropdown.get_attribute("aria-label") or ""
            if "work authorization" in label.lower():
                self._select_dropdown_option(dropdown, "Yes")
            elif "visa" in label.lower() and "sponsorship" in label.lower():
                self._select_dropdown_option(dropdown, "No")
        
        # Checkboxes for legal agreements
        checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for checkbox in checkboxes:
            if not checkbox.is_selected():
                await self._human_click(checkbox)
        
        await self._random_delay(0.5, 1.5)
    
    def _select_dropdown_option(self, dropdown, desired_text: str):
        """Select option from dropdown by text content"""
        try:
            from selenium.webdriver.support.ui import Select
            select = Select(dropdown)
            
            # Try to find option containing desired text
            for option in select.options:
                if desired_text.lower() in option.text.lower():
                    select.select_by_visible_text(option.text)
                    break
        except Exception as e:
            logger.warning("Failed to select dropdown option", error=str(e))
    
    async def _extract_job_info(self, job_card) -> Optional[LinkedInJob]:
        """Extract job information from a job card element"""
        try:
            # Job title and link
            title_element = job_card.find_element(By.CSS_SELECTOR, ".job-search-card__title a")
            title = title_element.text.strip()
            job_url = title_element.get_attribute("href")
            job_id = self._extract_job_id(job_url)
            
            # Company name
            company_element = job_card.find_element(By.CSS_SELECTOR, ".job-search-card__subtitle-link")
            company = company_element.text.strip()
            
            # Location
            location_element = job_card.find_element(By.CSS_SELECTOR, ".job-search-card__location")
            location = location_element.text.strip()
            
            # Posted time
            posted_element = job_card.find_element(By.CSS_SELECTOR, ".job-search-card__listdate")
            posted_time = posted_element.get_attribute("datetime") or posted_element.text.strip()
            
            # Check for Easy Apply
            easy_apply = len(job_card.find_elements(By.CSS_SELECTOR, ".job-search-card__easy-apply")) > 0
            
            # Salary (if available)
            salary_elements = job_card.find_elements(By.CSS_SELECTOR, ".job-search-card__salary-info")
            salary_range = salary_elements[0].text.strip() if salary_elements else None
            
            return LinkedInJob(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                posted_time=posted_time,
                job_url=job_url,
                easy_apply=easy_apply,
                salary_range=salary_range
            )
            
        except Exception as e:
            logger.warning("Failed to extract job info", error=str(e))
            return None
    
    def _extract_job_id(self, job_url: str) -> str:
        """Extract job ID from LinkedIn job URL"""
        try:
            # LinkedIn job URLs contain the job ID
            import re
            match = re.search(r'/jobs/view/(\d+)', job_url)
            return match.group(1) if match else job_url.split('/')[-1]
        except:
            return job_url.split('/')[-1]
    
    def _convert_time_filter(self, time_str: str) -> str:
        """Convert time filter to LinkedIn format"""
        time_map = {
            "24h": "86400",
            "1d": "86400", 
            "7d": "604800",
            "1w": "604800",
            "30d": "2592000",
            "1m": "2592000"
        }
        return time_map.get(time_str.lower(), "86400")
    
    async def _human_type(self, element, text: str):
        """Type text in a human-like manner"""
        element.clear()
        for char in text:
            element.send_keys(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))
    
    async def _human_click(self, element):
        """Click element with human-like delay"""
        await asyncio.sleep(random.uniform(0.1, 0.3))
        element.click()
    
    async def _random_delay(self, min_seconds: float = None, max_seconds: float = None):
        """Add random delay to mimic human behavior"""
        min_delay = min_seconds or self.min_delay
        max_delay = max_seconds or self.max_delay
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
    
    async def close_browser(self):
        """Close browser and cleanup"""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")


class LinkedInService:
    """High-level LinkedIn job application service"""
    
    def __init__(self):
        self.automation = LinkedInAutomation()
    
    async def bulk_apply_jobs(self, 
                             user_id: int,
                             keywords: str,
                             location: str = "",
                             user_data: Dict[str, Any] = None,
                             max_applications: int = 10) -> Dict[str, Any]:
        """Apply to multiple jobs in bulk"""
        
        results = {
            "total_searched": 0,
            "total_applied": 0,
            "applications": [],
            "errors": [],
            "status": "completed"
        }
        
        try:
            # Initialize browser and login
            if not await self.automation.initialize_browser():
                raise Exception("Failed to initialize browser")
            
            if not await self.automation.login_to_linkedin():
                raise Exception("Failed to login to LinkedIn")
            
            # Search for jobs
            jobs = await self.automation.search_jobs(
                keywords=keywords,
                location=location,
                easy_apply_only=True
            )
            
            results["total_searched"] = len(jobs)
            
            # Apply to jobs
            applications_sent = 0
            for job in jobs:
                if applications_sent >= max_applications:
                    break
                
                if not job.easy_apply:
                    continue
                
                result = await self.automation.apply_to_job(job, user_data or {})
                results["applications"].append({
                    "job_id": result.job_id,
                    "job_title": job.title,
                    "company": job.company,
                    "status": result.status.value,
                    "message": result.message,
                    "timestamp": result.timestamp.isoformat()
                })
                
                if result.status == LinkedInApplicationStatus.APPLIED:
                    applications_sent += 1
                    await self._save_application_record(user_id, job, result)
                elif result.status == LinkedInApplicationStatus.FAILED:
                    results["errors"].append({
                        "job_id": result.job_id,
                        "error": result.message,
                        "details": result.error_details
                    })
                
                # Add delay between applications
                await self.automation._random_delay(3, 8)
            
            results["total_applied"] = applications_sent
            
        except Exception as e:
            logger.error("Bulk job application failed", error=str(e))
            results["status"] = "failed"
            results["error"] = str(e)
        
        finally:
            await self.automation.close_browser()
        
        return results
    
    async def _save_application_record(self, 
                                     user_id: int, 
                                     job: LinkedInJob, 
                                     result: ApplicationResult):
        """Save application record to database"""
        try:
            database = await get_database()
            
            await database.execute(
                """
                INSERT INTO linkedin_applications 
                (user_id, job_id, job_title, company, location, application_url, 
                 status, applied_at, application_data)
                VALUES 
                (:user_id, :job_id, :job_title, :company, :location, :application_url,
                 :status, :applied_at, :application_data)
                """,
                {
                    "user_id": user_id,
                    "job_id": job.job_id,
                    "job_title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "application_url": job.job_url,
                    "status": result.status.value,
                    "applied_at": result.timestamp,
                    "application_data": json.dumps(result.application_data or {})
                }
            )
            
        except Exception as e:
            logger.error("Failed to save application record", error=str(e))


# Global service instance
linkedin_service = LinkedInService()