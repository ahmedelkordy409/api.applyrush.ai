"""
Advanced Browser Auto-Apply Service
Handles complex multi-step applications with anti-bot detection bypass
"""

import asyncio
import logging
import random
import os
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from datetime import datetime

logger = logging.getLogger(__name__)


class BrowserAutoApplyService:
    """Advanced browser automation for job applications"""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.captcha_solver_api_key = os.getenv("ANTICAPTCHA_API_KEY", "")

    async def init_browser(self, headless: bool = True):
        """Initialize browser with anti-detection measures"""
        playwright = await async_playwright().start()

        # Launch browser with stealth settings
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
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
            permissions=['geolocation'],
            java_script_enabled=True,
        )

        # Add anti-detection scripts
        await self.context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        logger.info("🌐 Browser initialized with anti-detection")

    async def close_browser(self):
        """Close browser and context"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def human_like_typing(self, page: Page, selector: str, text: str, delay_range: tuple = (50, 150)):
        """Type text with human-like delays"""
        element = await page.wait_for_selector(selector, timeout=10000)
        await element.click()

        for char in text:
            await element.type(char, delay=random.randint(*delay_range))

        # Random pause after typing
        await asyncio.sleep(random.uniform(0.1, 0.3))

    async def human_like_click(self, page: Page, selector: str):
        """Click with human-like delay"""
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.3, 0.7))

    async def solve_recaptcha(self, page: Page) -> bool:
        """Solve reCAPTCHA using anti-captcha service"""
        try:
            # Check if reCAPTCHA exists
            recaptcha = await page.query_selector('iframe[src*="recaptcha"]')
            if not recaptcha:
                return True  # No CAPTCHA found

            if not self.captcha_solver_api_key:
                logger.warning("⚠️  reCAPTCHA found but no API key configured")
                return False

            # Get site key
            site_key = await page.evaluate("""
                () => {
                    const elem = document.querySelector('.g-recaptcha');
                    return elem ? elem.getAttribute('data-sitekey') : null;
                }
            """)

            if not site_key:
                logger.error("❌ Could not extract reCAPTCHA site key")
                return False

            # Solve using anti-captcha API
            solution = await self._solve_recaptcha_with_api(
                site_key=site_key,
                page_url=page.url
            )

            if solution:
                # Inject solution
                await page.evaluate(f"""
                    document.getElementById('g-recaptcha-response').innerHTML = '{solution}';
                """)
                logger.info("✅ reCAPTCHA solved successfully")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error solving reCAPTCHA: {e}")
            return False

    async def _solve_recaptcha_with_api(self, site_key: str, page_url: str) -> Optional[str]:
        """Use Anti-Captcha API to solve reCAPTCHA"""
        # This is a placeholder - implement actual API integration
        # Example: 2Captcha, Anti-Captcha, CapSolver, etc.
        logger.info(f"🔐 Solving reCAPTCHA for site key: {site_key[:20]}...")

        # TODO: Implement actual API call
        # For now, return None to indicate manual intervention needed
        return None

    async def detect_and_fill_form(self, page: Page, user_data: Dict[str, Any], job_data: Dict[str, Any]) -> bool:
        """Intelligently detect and fill application forms"""
        try:
            logger.info("🔍 Detecting form fields...")

            # Wait for form to load
            await page.wait_for_load_state('networkidle', timeout=15000)
            await asyncio.sleep(random.uniform(1, 2))

            # Common field mappings
            field_mappings = {
                # Name fields
                'first_name': ['input[name*="first"], input[id*="first"], input[placeholder*="First"]'],
                'last_name': ['input[name*="last"], input[id*="last"], input[placeholder*="Last"]'],
                'full_name': ['input[name*="name"], input[id*="name"], input[placeholder*="Name"]'],

                # Contact fields
                'email': ['input[type="email"], input[name*="email"], input[id*="email"]'],
                'phone': ['input[type="tel"], input[name*="phone"], input[id*="phone"], input[placeholder*="Phone"]'],

                # Address fields
                'address': ['input[name*="address"], input[id*="address"]'],
                'city': ['input[name*="city"], input[id*="city"]'],
                'state': ['select[name*="state"], input[name*="state"]'],
                'zip': ['input[name*="zip"], input[name*="postal"]'],

                # Work fields
                'linkedin': ['input[name*="linkedin"], input[id*="linkedin"]'],
                'website': ['input[name*="website"], input[name*="portfolio"]'],

                # File uploads
                'resume': ['input[type="file"][name*="resume"], input[type="file"][id*="resume"]'],
                'cover_letter': ['textarea[name*="cover"], textarea[id*="cover"]'],
            }

            # Fill detected fields
            filled_count = 0

            for field_type, selectors in field_mappings.items():
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            value = self._get_user_value(field_type, user_data, job_data)
                            if value:
                                if field_type == 'resume':
                                    await element.set_input_files(value)
                                elif 'textarea' in selector:
                                    await self.human_like_typing(page, selector, value)
                                else:
                                    await self.human_like_typing(page, selector, value)

                                filled_count += 1
                                logger.info(f"✅ Filled {field_type}")
                                break
                    except Exception as e:
                        logger.debug(f"Could not fill {field_type}: {e}")
                        continue

            logger.info(f"📝 Filled {filled_count} form fields")
            return filled_count > 0

        except Exception as e:
            logger.error(f"❌ Error filling form: {e}")
            return False

    def _get_user_value(self, field_type: str, user_data: Dict, job_data: Dict) -> Optional[str]:
        """Get appropriate value for field type"""
        profile = user_data.get('profile', {})

        value_map = {
            'first_name': profile.get('first_name', ''),
            'last_name': profile.get('last_name', ''),
            'full_name': profile.get('full_name', ''),
            'email': user_data.get('email', ''),
            'phone': profile.get('phone', ''),
            'address': profile.get('address', ''),
            'city': profile.get('city', ''),
            'state': profile.get('state', ''),
            'zip': profile.get('zip_code', ''),
            'linkedin': profile.get('linkedin_url', ''),
            'website': profile.get('portfolio_url', ''),
            'resume': user_data.get('resume_path', ''),
            'cover_letter': user_data.get('cover_letter', ''),
        }

        return value_map.get(field_type, '')

    async def handle_multi_step_form(self, page: Page, user_data: Dict, job_data: Dict) -> bool:
        """Handle multi-step application forms"""
        try:
            step = 1
            max_steps = 10
            total_fields_filled = 0
            any_button_clicked = False

            while step <= max_steps:
                logger.info(f"📄 Processing step {step}...")

                # Fill current step
                filled = await self.detect_and_fill_form(page, user_data, job_data)
                if filled:
                    total_fields_filled += 1

                # Check for CAPTCHA
                captcha_solved = await self.solve_recaptcha(page)
                if not captcha_solved:
                    logger.error("❌ CAPTCHA present but could not be solved")
                    return False

                # Look for next/continue/submit button
                next_button_selectors = [
                    'button:has-text("Next")',
                    'button:has-text("Continue")',
                    'button:has-text("Submit")',
                    'button:has-text("Apply")',
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'a:has-text("Next")',
                ]

                button_clicked = False
                for selector in next_button_selectors:
                    try:
                        button = await page.query_selector(selector)
                        if button and await button.is_visible():
                            await self.human_like_click(page, selector)
                            button_clicked = True
                            any_button_clicked = True
                            logger.info(f"✅ Clicked: {selector}")

                            # Wait for navigation or form update
                            try:
                                await page.wait_for_load_state('networkidle', timeout=5000)
                            except:
                                await asyncio.sleep(2)

                            break
                    except Exception as e:
                        continue

                if not button_clicked:
                    # No more buttons found - check if we actually did anything
                    if total_fields_filled == 0 and not any_button_clicked:
                        logger.error("❌ No form fields filled and no buttons clicked - application failed")
                        return False

                    # Check for success confirmation
                    if await self._check_submission_success(page):
                        logger.info("✅ Application submitted successfully!")
                        return True

                    logger.warning("⚠️  No more steps found but no success confirmation detected")
                    return False

                # Check if application was submitted after clicking
                if await self._check_submission_success(page):
                    logger.info("✅ Application submitted successfully!")
                    return True

                step += 1

            logger.warning("⚠️  Reached maximum steps without completion")
            return False

        except Exception as e:
            logger.error(f"❌ Error in multi-step form: {e}")
            return False

    async def _check_submission_success(self, page: Page) -> bool:
        """Check if application was successfully submitted"""
        success_indicators = [
            'text=/success/i',
            'text=/thank you/i',
            'text=/application.*submitted/i',
            'text=/application.*received/i',
            'text=/we.*received/i',
        ]

        for indicator in success_indicators:
            try:
                element = await page.query_selector(indicator)
                if element:
                    return True
            except:
                continue

        return False

    async def apply_to_job(
        self,
        job_url: str,
        user_data: Dict[str, Any],
        job_data: Dict[str, Any],
        resume_path: Optional[str] = None,
        cover_letter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Main method to apply to a job via browser automation"""
        try:
            logger.info(f"🚀 Starting browser application to: {job_url}")

            # Initialize browser if not already done
            if not self.browser:
                await self.init_browser(headless=True)

            # Create new page
            page = await self.context.new_page()

            # Navigate to job URL
            await page.goto(job_url, wait_until='networkidle', timeout=30000)
            logger.info(f"📍 Navigated to: {page.url}")

            # Random human-like delay
            await asyncio.sleep(random.uniform(2, 4))

            # Look for "Apply" button
            apply_button_selectors = [
                'button:has-text("Apply")',
                'a:has-text("Apply")',
                'button:has-text("Apply Now")',
                'a:has-text("Apply Now")',
                'button[class*="apply"]',
                'a[class*="apply"]',
            ]

            button_found = False
            for selector in apply_button_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button and await button.is_visible():
                        await self.human_like_click(page, selector)
                        button_found = True
                        logger.info("✅ Clicked Apply button")
                        break
                except:
                    continue

            if not button_found:
                logger.warning("⚠️  No Apply button found, assuming already on form")

            # Wait for form to appear
            await asyncio.sleep(random.uniform(1, 2))

            # Add user data
            enhanced_user_data = {
                **user_data,
                'resume_path': resume_path,
                'cover_letter': cover_letter
            }

            # Handle multi-step form
            success = await self.handle_multi_step_form(page, enhanced_user_data, job_data)

            # Take screenshot for verification
            screenshot_path = f"/tmp/application_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path)

            await page.close()

            return {
                'success': success,
                'method': 'browser_automation',
                'url': job_url,
                'screenshot': screenshot_path,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Error applying to job: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': 'browser_automation',
                'url': job_url
            }
