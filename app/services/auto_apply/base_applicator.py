"""
Base Applicator - Browser automation foundation for job applications
Integrates with existing ApplyRush.AI email forwarding system
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import random
import logging
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)


class ApplicationStatus(str, Enum):
    """Application submission status"""
    SUCCESS = "success"
    FAILED = "failed"
    CAPTCHA_REQUIRED = "captcha_required"
    LOGIN_REQUIRED = "login_required"
    ALREADY_APPLIED = "already_applied"
    TIMEOUT = "timeout"
    UNKNOWN_ERROR = "unknown_error"


class ATSType(str, Enum):
    """Applicant Tracking System types"""
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    TALEO = "taleo"
    ICIMS = "icims"
    GENERIC = "generic"
    EMAIL = "email"


@dataclass
class ApplicationResult:
    """Result of job application attempt"""
    success: bool
    status: ApplicationStatus
    ats_type: ATSType
    job_url: str
    steps_completed: List[str]
    errors: List[str]
    warnings: List[str]
    screenshot_paths: List[str]
    submitted_at: Optional[datetime]
    confirmation_number: Optional[str]
    confirmation_email: Optional[str]
    email_forwarding_used: bool
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['status'] = self.status.value
        data['ats_type'] = self.ats_type.value
        if self.submitted_at:
            data['submitted_at'] = self.submitted_at.isoformat()
        return data


class BaseApplicator(ABC):
    """
    Base class for job application automation
    Integrates with ApplyRush.AI email forwarding system
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize applicator"""
        self.config = config or {}
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None
        self.screenshots: List[str] = []
        self.steps_completed: List[str] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

        # Email forwarding configuration
        self.email_forwarding_enabled = self.config.get('email_forwarding_enabled', True)
        self.forwarding_email_domain = self.config.get('forwarding_email_domain', 'apply.applyrush.ai')

        # Browser configuration
        self.headless = self.config.get('headless', True)
        self.timeout = self.config.get('timeout', 60000)  # 60 seconds
        self.slow_mo = self.config.get('slow_mo', 100)  # Slow down for human-like behavior

    async def apply(
        self,
        job_url: str,
        user_data: Dict[str, Any],
        resume_path: str,
        **kwargs
    ) -> ApplicationResult:
        """
        Main entry point for job application

        Args:
            job_url: URL of job posting
            user_data: User profile data
            resume_path: Path to resume file
            **kwargs: Additional parameters

        Returns:
            ApplicationResult with details of application attempt
        """
        try:
            logger.info(f"Starting application process for {job_url}")

            # Setup browser
            await self.setup_browser()

            # Navigate to job URL
            await self.navigate_to_job(job_url)

            # Detect ATS type
            ats_type = await self.detect_ats_type()
            logger.info(f"Detected ATS type: {ats_type.value}")

            # Check if already applied
            if await self.check_already_applied():
                return self._create_result(
                    success=False,
                    status=ApplicationStatus.ALREADY_APPLIED,
                    ats_type=ats_type,
                    job_url=job_url
                )

            # Prepare email forwarding address if enabled
            application_email = self._get_application_email(user_data)
            user_data['application_email'] = application_email

            # Fill application form
            await self.fill_form(user_data, resume_path)

            # Submit application
            submission_result = await self.submit_application()

            # Verify submission
            verification = await self.verify_success()

            # Take final screenshot
            await self.take_screenshot("final_state")

            # Create result
            result = self._create_result(
                success=verification['success'],
                status=ApplicationStatus.SUCCESS if verification['success'] else ApplicationStatus.FAILED,
                ats_type=ats_type,
                job_url=job_url,
                confirmation_number=verification.get('confirmation_number'),
                confirmation_email=application_email,
                email_forwarding_used=self.email_forwarding_enabled
            )

            return result

        except Exception as e:
            logger.error(f"Application failed: {str(e)}")
            self.errors.append(str(e))
            await self.take_screenshot("error_state")

            return self._create_result(
                success=False,
                status=ApplicationStatus.UNKNOWN_ERROR,
                ats_type=ATSType.GENERIC,
                job_url=job_url
            )

        finally:
            await self.cleanup_browser()

    async def setup_browser(self) -> None:
        """Setup Playwright browser with anti-detection measures"""
        try:
            playwright = await async_playwright().start()

            # Launch browser with stealth settings
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )

            # Create context with realistic settings
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )

            # Disable navigator.webdriver detection
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # Create page
            self.page = await self.context.new_page()
            self.page.set_default_timeout(self.timeout)

            self.steps_completed.append("browser_setup")
            logger.info("Browser setup completed")

        except Exception as e:
            logger.error(f"Browser setup failed: {str(e)}")
            raise

    async def navigate_to_job(self, job_url: str) -> None:
        """Navigate to job posting"""
        try:
            await self.page.goto(job_url, wait_until='networkidle', timeout=self.timeout)
            await self.human_delay(1, 3)
            await self.take_screenshot("job_page_loaded")
            self.steps_completed.append("navigation")
            logger.info(f"Navigated to {job_url}")
        except Exception as e:
            logger.error(f"Navigation failed: {str(e)}")
            raise

    @abstractmethod
    async def detect_ats_type(self) -> ATSType:
        """Detect which ATS system is being used"""
        pass

    @abstractmethod
    async def fill_form(self, user_data: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        """Fill application form with user data"""
        pass

    async def submit_application(self) -> Dict[str, Any]:
        """Submit the application form"""
        try:
            # Look for submit button
            submit_button = await self._find_submit_button()

            if submit_button:
                await self.take_screenshot("before_submit")
                await submit_button.click()
                await self.human_delay(2, 4)
                await self.take_screenshot("after_submit")
                self.steps_completed.append("submission")
                return {"success": True}
            else:
                self.errors.append("Submit button not found")
                return {"success": False, "error": "Submit button not found"}

        except Exception as e:
            logger.error(f"Submission failed: {str(e)}")
            self.errors.append(str(e))
            return {"success": False, "error": str(e)}

    async def verify_success(self) -> Dict[str, Any]:
        """Verify that application was submitted successfully"""
        try:
            # Wait for potential redirect or success message
            await self.page.wait_for_load_state('networkidle', timeout=10000)

            # Look for success indicators
            success_indicators = [
                'thank you',
                'application submitted',
                'success',
                'received your application',
                'we\'ll be in touch',
            ]

            page_text = await self.page.inner_text('body')
            page_text_lower = page_text.lower()

            for indicator in success_indicators:
                if indicator in page_text_lower:
                    # Try to extract confirmation number
                    confirmation = await self._extract_confirmation_number(page_text)
                    return {
                        "success": True,
                        "confirmation_number": confirmation,
                        "indicator_found": indicator
                    }

            return {"success": False, "error": "No success indicator found"}

        except Exception as e:
            logger.warning(f"Verification uncertain: {str(e)}")
            return {"success": False, "error": str(e)}

    async def check_already_applied(self) -> bool:
        """Check if user has already applied to this job"""
        try:
            page_text = await self.page.inner_text('body')
            already_applied_indicators = [
                'already applied',
                'application on file',
                'previously applied',
            ]

            for indicator in already_applied_indicators:
                if indicator in page_text.lower():
                    return True
            return False
        except:
            return False

    async def take_screenshot(self, name: str) -> str:
        """Take screenshot and save to file"""
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"screenshot_{name}_{timestamp}.png"
            filepath = Path(f"/tmp/applyrush_screenshots/{filename}")
            filepath.parent.mkdir(parents=True, exist_ok=True)

            await self.page.screenshot(path=str(filepath), full_page=True)
            self.screenshots.append(str(filepath))
            return str(filepath)
        except Exception as e:
            logger.warning(f"Screenshot failed: {str(e)}")
            return ""

    async def human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """Add random delay to mimic human behavior"""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def cleanup_browser(self) -> None:
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            logger.info("Browser cleanup completed")
        except Exception as e:
            logger.warning(f"Browser cleanup warning: {str(e)}")

    def _get_application_email(self, user_data: Dict[str, Any]) -> str:
        """
        Generate email forwarding address for application
        Format: {user_id}.{job_id}@apply.applyrush.ai
        """
        if not self.email_forwarding_enabled:
            return user_data.get('email', '')

        user_id = user_data.get('user_id', 'unknown')
        job_id = user_data.get('job_id', 'unknown')
        timestamp = datetime.utcnow().strftime('%Y%m%d')

        # Create unique forwarding email
        forwarding_email = f"{user_id}.{job_id}.{timestamp}@{self.forwarding_email_domain}"

        logger.info(f"Generated forwarding email: {forwarding_email}")
        return forwarding_email

    async def _find_submit_button(self) -> Optional[Any]:
        """Find submit button on page"""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Send Application")',
            'button:has-text("Submit Application")',
            'a:has-text("Submit")',
        ]

        for selector in submit_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    return element
            except:
                continue

        return None

    async def _extract_confirmation_number(self, text: str) -> Optional[str]:
        """Extract confirmation number from page text"""
        import re

        # Common patterns for confirmation numbers
        patterns = [
            r'confirmation\s*(?:number|code|#)?\s*:?\s*([A-Z0-9-]+)',
            r'application\s*(?:id|number)?\s*:?\s*([A-Z0-9-]+)',
            r'reference\s*(?:number|code)?\s*:?\s*([A-Z0-9-]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _create_result(
        self,
        success: bool,
        status: ApplicationStatus,
        ats_type: ATSType,
        job_url: str,
        confirmation_number: Optional[str] = None,
        confirmation_email: Optional[str] = None,
        email_forwarding_used: bool = False
    ) -> ApplicationResult:
        """Create ApplicationResult object"""
        return ApplicationResult(
            success=success,
            status=status,
            ats_type=ats_type,
            job_url=job_url,
            steps_completed=self.steps_completed.copy(),
            errors=self.errors.copy(),
            warnings=self.warnings.copy(),
            screenshot_paths=self.screenshots.copy(),
            submitted_at=datetime.utcnow() if success else None,
            confirmation_number=confirmation_number,
            confirmation_email=confirmation_email,
            email_forwarding_used=email_forwarding_used,
            metadata={
                "email_forwarding_domain": self.forwarding_email_domain if email_forwarding_used else None,
                "browser_headless": self.headless,
                "total_steps": len(self.steps_completed),
                "total_errors": len(self.errors),
                "total_warnings": len(self.warnings),
            }
        )


__all__ = ["BaseApplicator", "ApplicationResult", "ApplicationStatus", "ATSType"]
