"""
Advanced Auto-Apply Service
Handles complex application scenarios: multi-step forms, CAPTCHAs, custom questions, file uploads
Production-ready like jobhire.ai
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from bson import ObjectId
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import stealth_async
import anthropic
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class CaptchaSolver:
    """
    Solve different types of CAPTCHAs
    """

    def __init__(self):
        self.two_captcha_key = settings.TWO_CAPTCHA_API_KEY
        self.capsolver_key = settings.CAPSOLVER_API_KEY

    async def solve_recaptcha_v2(self, page: Page, sitekey: str) -> str:
        """
        Solve reCAPTCHA v2 using 2Captcha service
        """
        import httpx

        url = page.url

        # Submit CAPTCHA to 2Captcha
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://2captcha.com/in.php",
                data={
                    "key": self.two_captcha_key,
                    "method": "userrecaptcha",
                    "googlekey": sitekey,
                    "pageurl": url,
                    "json": 1
                }
            )
            result = response.json()

            if result["status"] != 1:
                raise Exception(f"2Captcha error: {result.get('request')}")

            captcha_id = result["request"]

            # Poll for result
            for _ in range(60):  # Wait up to 2 minutes
                await asyncio.sleep(2)

                check_response = await client.get(
                    f"https://2captcha.com/res.php?key={self.two_captcha_key}&action=get&id={captcha_id}&json=1"
                )
                check_result = check_response.json()

                if check_result["status"] == 1:
                    return check_result["request"]

            raise Exception("CAPTCHA timeout")

    async def solve_recaptcha_v3(self, page: Page, sitekey: str, action: str = "submit") -> str:
        """
        Solve reCAPTCHA v3 using CapSolver
        """
        import httpx

        url = page.url

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.capsolver.com/createTask",
                json={
                    "clientKey": self.capsolver_key,
                    "task": {
                        "type": "ReCaptchaV3TaskProxyLess",
                        "websiteURL": url,
                        "websiteKey": sitekey,
                        "pageAction": action
                    }
                }
            )
            result = response.json()

            if result["errorId"] != 0:
                raise Exception(f"CapSolver error: {result.get('errorDescription')}")

            task_id = result["taskId"]

            # Poll for result
            for _ in range(60):
                await asyncio.sleep(2)

                check_response = await client.post(
                    "https://api.capsolver.com/getTaskResult",
                    json={
                        "clientKey": self.capsolver_key,
                        "taskId": task_id
                    }
                )
                check_result = check_response.json()

                if check_result["status"] == "ready":
                    return check_result["solution"]["gRecaptchaResponse"]

            raise Exception("CAPTCHA timeout")

    async def solve_hcaptcha(self, page: Page, sitekey: str) -> str:
        """
        Solve hCaptcha using 2Captcha
        """
        import httpx

        url = page.url

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://2captcha.com/in.php",
                data={
                    "key": self.two_captcha_key,
                    "method": "hcaptcha",
                    "sitekey": sitekey,
                    "pageurl": url,
                    "json": 1
                }
            )
            result = response.json()

            if result["status"] != 1:
                raise Exception(f"2Captcha error: {result.get('request')}")

            captcha_id = result["request"]

            # Poll for result
            for _ in range(60):
                await asyncio.sleep(2)

                check_response = await client.get(
                    f"https://2captcha.com/res.php?key={self.two_captcha_key}&action=get&id={captcha_id}&json=1"
                )
                check_result = check_response.json()

                if check_result["status"] == 1:
                    return check_result["request"]

            raise Exception("CAPTCHA timeout")


class FormAnalyzer:
    """
    Analyze and classify form fields intelligently
    """

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def detect_all_fields(self, page: Page) -> List[Dict]:
        """
        Detect all form fields on the page
        """
        fields = []

        # Text inputs
        text_inputs = await page.query_selector_all('input[type="text"], input[type="email"], input[type="tel"], input:not([type]), textarea')
        for input_elem in text_inputs:
            field_info = await self._analyze_input(input_elem, page)
            if field_info:
                fields.append(field_info)

        # Select dropdowns
        selects = await page.query_selector_all('select')
        for select in selects:
            field_info = await self._analyze_select(select, page)
            if field_info:
                fields.append(field_info)

        # Radio buttons
        radios = await page.query_selector_all('input[type="radio"]')
        radio_groups = {}
        for radio in radios:
            name = await radio.get_attribute('name')
            if name not in radio_groups:
                radio_groups[name] = []
            radio_groups[name].append(radio)

        for name, radio_list in radio_groups.items():
            field_info = await self._analyze_radio_group(name, radio_list, page)
            if field_info:
                fields.append(field_info)

        # Checkboxes
        checkboxes = await page.query_selector_all('input[type="checkbox"]')
        for checkbox in checkboxes:
            field_info = await self._analyze_checkbox(checkbox, page)
            if field_info:
                fields.append(field_info)

        # File uploads
        file_inputs = await page.query_selector_all('input[type="file"]')
        for file_input in file_inputs:
            field_info = await self._analyze_file_input(file_input, page)
            if field_info:
                fields.append(field_info)

        return fields

    async def _analyze_input(self, input_elem, page: Page) -> Optional[Dict]:
        """Analyze text input field"""
        try:
            selector = await self._get_selector(input_elem, page)
            label = await self._find_label(input_elem, page)
            placeholder = await input_elem.get_attribute('placeholder') or ""
            input_type = await input_elem.get_attribute('type') or "text"
            is_required = await input_elem.get_attribute('required') is not None
            name = await input_elem.get_attribute('name') or ""
            input_id = await input_elem.get_attribute('id') or ""

            # Classify field
            field_type = self._classify_field(label, placeholder, name, input_id, input_type)

            return {
                "selector": selector,
                "type": "input",
                "input_type": input_type,
                "field_type": field_type,
                "label": label,
                "placeholder": placeholder,
                "is_required": is_required,
                "name": name,
                "id": input_id
            }
        except Exception as e:
            logger.error(f"Error analyzing input: {e}")
            return None

    async def _analyze_select(self, select_elem, page: Page) -> Optional[Dict]:
        """Analyze select dropdown"""
        try:
            selector = await self._get_selector(select_elem, page)
            label = await self._find_label(select_elem, page)
            is_required = await select_elem.get_attribute('required') is not None
            name = await select_elem.get_attribute('name') or ""

            # Get options
            options = []
            option_elements = await select_elem.query_selector_all('option')
            for opt in option_elements:
                text = await opt.inner_text()
                value = await opt.get_attribute('value')
                options.append({"text": text.strip(), "value": value})

            field_type = self._classify_field(label, "", name, "", "select")

            return {
                "selector": selector,
                "type": "select",
                "field_type": field_type,
                "label": label,
                "is_required": is_required,
                "name": name,
                "options": options
            }
        except Exception as e:
            logger.error(f"Error analyzing select: {e}")
            return None

    async def _analyze_radio_group(self, name: str, radios: List, page: Page) -> Optional[Dict]:
        """Analyze radio button group"""
        try:
            if not radios:
                return None

            first_radio = radios[0]
            label = await self._find_label(first_radio, page)

            options = []
            for radio in radios:
                radio_label = await self._find_label(radio, page)
                value = await radio.get_attribute('value')
                options.append({"text": radio_label, "value": value})

            field_type = self._classify_field(label, "", name, "", "radio")

            return {
                "selector": f'input[name="{name}"]',
                "type": "radio",
                "field_type": field_type,
                "label": label,
                "name": name,
                "options": options,
                "is_required": False  # Detect from form validation
            }
        except Exception as e:
            logger.error(f"Error analyzing radio group: {e}")
            return None

    async def _analyze_checkbox(self, checkbox_elem, page: Page) -> Optional[Dict]:
        """Analyze checkbox"""
        try:
            selector = await self._get_selector(checkbox_elem, page)
            label = await self._find_label(checkbox_elem, page)
            name = await checkbox_elem.get_attribute('name') or ""
            value = await checkbox_elem.get_attribute('value') or "on"

            field_type = self._classify_field(label, "", name, "", "checkbox")

            return {
                "selector": selector,
                "type": "checkbox",
                "field_type": field_type,
                "label": label,
                "name": name,
                "value": value,
                "is_required": False
            }
        except Exception as e:
            logger.error(f"Error analyzing checkbox: {e}")
            return None

    async def _analyze_file_input(self, file_elem, page: Page) -> Optional[Dict]:
        """Analyze file upload input"""
        try:
            selector = await self._get_selector(file_elem, page)
            label = await self._find_label(file_elem, page)
            accept = await file_elem.get_attribute('accept') or ""
            is_required = await file_elem.get_attribute('required') is not None

            # Determine file type (resume, cover letter, etc.)
            field_type = self._classify_file_input(label, accept)

            return {
                "selector": selector,
                "type": "file",
                "field_type": field_type,
                "label": label,
                "accept": accept,
                "is_required": is_required
            }
        except Exception as e:
            logger.error(f"Error analyzing file input: {e}")
            return None

    async def _get_selector(self, element, page: Page) -> str:
        """Generate CSS selector for element"""
        element_id = await element.get_attribute('id')
        if element_id:
            return f'#{element_id}'

        name = await element.get_attribute('name')
        if name:
            tag = await element.evaluate('el => el.tagName.toLowerCase()')
            input_type = await element.get_attribute('type')
            if input_type:
                return f'{tag}[name="{name}"][type="{input_type}"]'
            return f'{tag}[name="{name}"]'

        # Fallback: generate XPath
        return await element.evaluate('''el => {
            let path = [];
            while (el.parentElement) {
                let siblings = Array.from(el.parentElement.children);
                let index = siblings.indexOf(el) + 1;
                path.unshift(el.tagName.toLowerCase() + `:nth-child(${index})`);
                el = el.parentElement;
            }
            return path.join(' > ');
        }''')

    async def _find_label(self, element, page: Page) -> str:
        """Find label text for form element"""
        # Try associated label
        element_id = await element.get_attribute('id')
        if element_id:
            label_elem = await page.query_selector(f'label[for="{element_id}"]')
            if label_elem:
                return await label_elem.inner_text()

        # Try parent label
        parent_label = await element.evaluate('''el => {
            let current = el;
            while (current) {
                if (current.tagName === 'LABEL') {
                    return current.innerText;
                }
                current = current.parentElement;
            }
            return null;
        }''')

        if parent_label:
            return parent_label.strip()

        # Try placeholder
        placeholder = await element.get_attribute('placeholder')
        if placeholder:
            return placeholder.strip()

        # Try name attribute
        name = await element.get_attribute('name')
        if name:
            return name.replace('_', ' ').replace('-', ' ').title()

        return "Unknown Field"

    def _classify_field(self, label: str, placeholder: str, name: str, element_id: str, input_type: str) -> str:
        """
        Classify field type based on label, placeholder, name, etc.
        """
        text = f"{label} {placeholder} {name} {element_id}".lower()

        # First name
        if any(kw in text for kw in ['first name', 'firstname', 'fname', 'given name']):
            return "first_name"

        # Last name
        if any(kw in text for kw in ['last name', 'lastname', 'lname', 'family name', 'surname']):
            return "last_name"

        # Full name
        if any(kw in text for kw in ['full name', 'name', 'your name']):
            return "full_name"

        # Email
        if any(kw in text for kw in ['email', 'e-mail', 'mail']):
            return "email"

        # Phone
        if any(kw in text for kw in ['phone', 'telephone', 'mobile', 'cell']):
            return "phone"

        # Address
        if 'address' in text and 'email' not in text:
            return "address"

        # City
        if 'city' in text:
            return "city"

        # State
        if any(kw in text for kw in ['state', 'province', 'region']):
            return "state"

        # Zip code
        if any(kw in text for kw in ['zip', 'postal', 'postcode']):
            return "zip_code"

        # LinkedIn
        if 'linkedin' in text:
            return "linkedin"

        # Portfolio/Website
        if any(kw in text for kw in ['website', 'portfolio', 'personal site']):
            return "portfolio"

        # Resume/CV
        if any(kw in text for kw in ['resume', 'cv', 'curriculum']):
            return "resume"

        # Cover letter
        if any(kw in text for kw in ['cover letter', 'motivation letter']):
            return "cover_letter"

        # Years of experience
        if 'experience' in text and 'year' in text:
            return "years_experience"

        # Education
        if any(kw in text for kw in ['education', 'degree', 'university', 'school']):
            return "education"

        # Work authorization
        if any(kw in text for kw in ['authorization', 'eligible', 'visa', 'sponsorship']):
            return "work_authorization"

        # Salary expectation
        if any(kw in text for kw in ['salary', 'compensation', 'expected pay']):
            return "salary"

        # Custom question
        if any(kw in text for kw in ['why', 'how', 'describe', 'tell us', 'what makes']):
            return "custom_question"

        return "unknown"

    def _classify_file_input(self, label: str, accept: str) -> str:
        """Classify file input type"""
        label_lower = label.lower()
        accept_lower = accept.lower()

        if 'resume' in label_lower or 'cv' in label_lower:
            return "resume"

        if 'cover' in label_lower or 'letter' in label_lower:
            return "cover_letter"

        if 'portfolio' in label_lower:
            return "portfolio"

        if 'transcript' in label_lower:
            return "transcript"

        if '.pdf' in accept_lower or '.doc' in accept_lower:
            return "document"

        return "file"


class CustomQuestionAnswerer:
    """
    Answer custom application questions using AI
    """

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def answer_question(
        self,
        question: str,
        user_data: Dict,
        job_data: Dict,
        max_words: Optional[int] = None
    ) -> str:
        """
        Generate answer to custom question using AI
        """
        # Build context
        context = self._build_context(user_data, job_data)

        prompt = f"""
You are helping a job applicant answer an application question.

Job Title: {job_data.get('title')}
Company: {job_data.get('company_name')}

Applicant Background:
{context}

Question: {question}

{'Maximum words: ' + str(max_words) if max_words else ''}

Write a compelling, honest answer that:
1. Directly addresses the question
2. Highlights relevant experience and skills
3. Shows enthusiasm for the role
4. Is professional and concise
5. Uses specific examples when possible

Answer:"""

        # Use Claude for better reasoning
        message = await self.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        answer = message.content[0].text.strip()

        # Ensure word limit
        if max_words:
            words = answer.split()
            if len(words) > max_words:
                answer = ' '.join(words[:max_words])

        return answer

    def _build_context(self, user_data: Dict, job_data: Dict) -> str:
        """Build context from user profile"""
        context_parts = []

        # Experience
        if user_data.get('onboarding', {}).get('years_of_experience'):
            years = user_data['onboarding']['years_of_experience']
            context_parts.append(f"- {years} years of experience")

        # Skills
        if user_data.get('job_preferences', {}).get('skills'):
            skills = ', '.join(user_data['job_preferences']['skills'][:10])
            context_parts.append(f"- Skills: {skills}")

        # Education
        if user_data.get('onboarding', {}).get('education_level'):
            edu = user_data['onboarding']['education_level']
            context_parts.append(f"- Education: {edu}")

        # Resume data (if parsed)
        resume = user_data.get('primary_resume')
        if resume and resume.get('parsed_data'):
            parsed = resume['parsed_data']

            # Work experience
            if parsed.get('work_experience'):
                recent_job = parsed['work_experience'][0]
                context_parts.append(f"- Recent role: {recent_job.get('position')} at {recent_job.get('company')}")

            # Professional summary
            if parsed.get('professional_summary'):
                context_parts.append(f"- Summary: {parsed['professional_summary']}")

        return '\n'.join(context_parts)


class AdvancedAutoApplyService:
    """
    Production-ready auto-apply service
    Handles all complex scenarios
    """

    def __init__(self, db):
        self.db = db
        self.captcha_solver = CaptchaSolver()
        self.form_analyzer = FormAnalyzer()
        self.question_answerer = CustomQuestionAnswerer()

    async def apply_to_job(
        self,
        user_id: str,
        job_id: str,
        resume_id: Optional[str] = None,
        cover_letter_id: Optional[str] = None,
        headless: bool = True
    ) -> Dict:
        """
        Complete auto-apply process with all edge cases handled
        """
        logger.info(f"Starting auto-apply for user {user_id}, job {job_id}")

        # 1. Load data
        user = self.db.users.find_one({"_id": ObjectId(user_id)})
        job = self.db.jobs.find_one({"_id": ObjectId(job_id)})

        if not user or not job:
            raise ValueError("User or job not found")

        # Get resume
        if resume_id:
            resume = self.db.resumes.find_one({"_id": ObjectId(resume_id)})
        else:
            resume = self.db.resumes.find_one({"user_id": ObjectId(user_id), "is_primary": True})

        # Get cover letter
        if cover_letter_id:
            cover_letter = self.db.cover_letters.find_one({"_id": ObjectId(cover_letter_id)})
        else:
            cover_letter = None

        # Get forwarding email
        forwarding_email_doc = self.db.forwarding_emails.find_one({"user_id": ObjectId(user_id)})
        forwarding_email = forwarding_email_doc["forwarding_address"] if forwarding_email_doc else user["email"]

        # 2. Start browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = await context.new_page()

            # Apply stealth mode
            await stealth_async(page)

            try:
                # 3. Navigate to application page
                apply_url = job.get('apply_url')
                if not apply_url:
                    raise ValueError("No apply URL found")

                logger.info(f"Navigating to: {apply_url}")
                await page.goto(apply_url, wait_until='networkidle', timeout=30000)

                # 4. Detect and click "Apply" button if needed
                await self._find_and_click_apply_button(page)

                # 5. Handle multi-step form
                max_steps = 10
                current_step = 0
                form_data_used = {}

                while current_step < max_steps:
                    logger.info(f"Processing form step {current_step + 1}")

                    # Wait for form to load
                    await page.wait_for_timeout(2000)

                    # 6. Detect CAPTCHA
                    captcha_solved = await self._handle_captcha(page)
                    if captcha_solved:
                        logger.info("CAPTCHA solved successfully")

                    # 7. Analyze form fields
                    fields = await self.form_analyzer.detect_all_fields(page)
                    logger.info(f"Detected {len(fields)} form fields")

                    if not fields:
                        # Check if we're done
                        if await self._is_application_complete(page):
                            logger.info("Application complete!")
                            break

                        # Check for errors
                        error_msg = await self._check_for_errors(page)
                        if error_msg:
                            raise Exception(f"Application error: {error_msg}")

                        # Move to next step
                        next_clicked = await self._click_next_button(page)
                        if not next_clicked:
                            break

                        current_step += 1
                        continue

                    # 8. Fill form fields
                    filled_fields = await self._fill_form_fields(
                        page,
                        fields,
                        user,
                        job,
                        resume,
                        cover_letter,
                        forwarding_email
                    )

                    form_data_used.update(filled_fields)

                    # 9. Take screenshot
                    screenshot_path = f"/tmp/applications/{user_id}_{job_id}_step_{current_step}.png"
                    await page.screenshot(path=screenshot_path)

                    # 10. Click "Next" or "Submit"
                    submitted = await self._click_submit_or_next(page)

                    if submitted:
                        logger.info("Application submitted!")

                        # Wait for confirmation
                        await page.wait_for_timeout(3000)

                        # Check for success
                        success = await self._verify_submission_success(page)

                        # Take final screenshot
                        final_screenshot = f"/tmp/applications/{user_id}_{job_id}_confirmation.png"
                        await page.screenshot(path=final_screenshot)

                        # Get confirmation number if available
                        confirmation_number = await self._extract_confirmation_number(page)

                        # Save application
                        application = self._save_application(
                            user_id,
                            job_id,
                            resume_id,
                            cover_letter_id,
                            forwarding_email,
                            form_data_used,
                            final_screenshot,
                            confirmation_number,
                            success
                        )

                        return {
                            "success": success,
                            "application_id": str(application["_id"]),
                            "confirmation_number": confirmation_number,
                            "screenshot": final_screenshot
                        }

                    current_step += 1

                # If we get here, application didn't complete
                raise Exception("Application did not complete within max steps")

            except Exception as e:
                logger.error(f"Auto-apply error: {str(e)}")

                # Save failed application
                self._save_failed_application(
                    user_id,
                    job_id,
                    str(e)
                )

                raise

            finally:
                await browser.close()

    async def _find_and_click_apply_button(self, page: Page):
        """Find and click the Apply button"""
        # Common apply button selectors
        apply_selectors = [
            'button:has-text("Apply")',
            'a:has-text("Apply")',
            'button:has-text("Apply Now")',
            'a:has-text("Apply Now")',
            'button[data-qa="apply"]',
            '.apply-button',
            '#apply-button'
        ]

        for selector in apply_selectors:
            try:
                apply_btn = await page.query_selector(selector)
                if apply_btn:
                    await apply_btn.click()
                    await page.wait_for_timeout(2000)
                    return True
            except:
                continue

        return False

    async def _handle_captcha(self, page: Page) -> bool:
        """Detect and solve CAPTCHA if present"""
        # Check for reCAPTCHA v2
        recaptcha_v2 = await page.query_selector('.g-recaptcha')
        if recaptcha_v2:
            sitekey = await recaptcha_v2.get_attribute('data-sitekey')
            solution = await self.captcha_solver.solve_recaptcha_v2(page, sitekey)

            # Inject solution
            await page.evaluate(f'''
                document.getElementById("g-recaptcha-response").innerHTML = "{solution}";
            ''')
            return True

        # Check for reCAPTCHA v3
        recaptcha_v3_script = await page.query_selector('script[src*="recaptcha/api.js"]')
        if recaptcha_v3_script:
            # Extract sitekey from page source
            page_content = await page.content()
            sitekey_match = re.search(r'data-sitekey="([^"]+)"', page_content)
            if sitekey_match:
                sitekey = sitekey_match.group(1)
                solution = await self.captcha_solver.solve_recaptcha_v3(page, sitekey)

                # Inject solution
                await page.evaluate(f'''
                    window.grecaptcha.execute = function() {{
                        return Promise.resolve("{solution}");
                    }};
                ''')
                return True

        # Check for hCaptcha
        hcaptcha = await page.query_selector('.h-captcha')
        if hcaptcha:
            sitekey = await hcaptcha.get_attribute('data-sitekey')
            solution = await self.captcha_solver.solve_hcaptcha(page, sitekey)

            # Inject solution
            await page.evaluate(f'''
                document.querySelector('[name="h-captcha-response"]').value = "{solution}";
            ''')
            return True

        return False

    async def _fill_form_fields(
        self,
        page: Page,
        fields: List[Dict],
        user: Dict,
        job: Dict,
        resume: Optional[Dict],
        cover_letter: Optional[Dict],
        forwarding_email: str
    ) -> Dict:
        """Fill all detected form fields"""
        filled_data = {}

        for field in fields:
            try:
                value = await self._get_value_for_field(field, user, job, resume, cover_letter, forwarding_email)

                if value is not None:
                    success = await self._fill_field(page, field, value)
                    if success:
                        filled_data[field['field_type']] = value

            except Exception as e:
                logger.error(f"Error filling field {field.get('label')}: {e}")

        return filled_data

    async def _get_value_for_field(
        self,
        field: Dict,
        user: Dict,
        job: Dict,
        resume: Optional[Dict],
        cover_letter: Optional[Dict],
        forwarding_email: str
    ) -> Any:
        """Get appropriate value for field based on type"""
        field_type = field['field_type']
        parsed_resume = resume.get('parsed_data', {}) if resume else {}

        # Map field types to values
        value_map = {
            "first_name": parsed_resume.get('personal_information', {}).get('full_name', '').split()[0] or user.get('profile', {}).get('first_name'),
            "last_name": parsed_resume.get('personal_information', {}).get('full_name', '').split()[-1] or user.get('profile', {}).get('last_name'),
            "full_name": parsed_resume.get('personal_information', {}).get('full_name') or f"{user.get('profile', {}).get('first_name', '')} {user.get('profile', {}).get('last_name', '')}",
            "email": forwarding_email,
            "phone": parsed_resume.get('personal_information', {}).get('phone') or user.get('profile', {}).get('phone'),
            "linkedin": parsed_resume.get('personal_information', {}).get('linkedin_url'),
            "portfolio": parsed_resume.get('personal_information', {}).get('portfolio_url'),
            "address": parsed_resume.get('personal_information', {}).get('location'),
            "city": parsed_resume.get('personal_information', {}).get('location', '').split(',')[0] if parsed_resume.get('personal_information', {}).get('location') else None,
            "years_experience": user.get('onboarding', {}).get('years_of_experience')
        }

        if field_type in value_map:
            return value_map[field_type]

        # Handle file uploads
        if field_type == "resume" and resume:
            return resume.get('file_path')

        if field_type == "cover_letter" and cover_letter:
            return cover_letter.get('file_path')

        # Handle custom questions
        if field_type == "custom_question":
            question = field.get('label', '')
            answer = await self.question_answerer.answer_question(
                question,
                user,
                job
            )
            return answer

        # Handle work authorization
        if field_type == "work_authorization":
            auth_status = user.get('onboarding', {}).get('work_authorization', 'authorized')
            return "Yes" if auth_status == "us_citizen" else "Require sponsorship"

        return None

    async def _fill_field(self, page: Page, field: Dict, value: Any) -> bool:
        """Fill a single form field"""
        try:
            selector = field['selector']

            if field['type'] == 'input':
                await page.fill(selector, str(value))
                return True

            elif field['type'] == 'select':
                # Find best matching option
                options = field.get('options', [])
                best_match = self._find_best_select_option(value, options)
                if best_match:
                    await page.select_option(selector, best_match['value'])
                    return True

            elif field['type'] == 'radio':
                # Find matching radio option
                options = field.get('options', [])
                best_match = self._find_best_select_option(value, options)
                if best_match:
                    await page.check(f'{selector}[value="{best_match["value"]}"]')
                    return True

            elif field['type'] == 'checkbox':
                # Check if value indicates should be checked
                if value in [True, 'yes', 'Yes', 'true', 'True']:
                    await page.check(selector)
                    return True

            elif field['type'] == 'file':
                # Upload file
                if value and isinstance(value, str):
                    await page.set_input_files(selector, value)
                    return True

        except Exception as e:
            logger.error(f"Error filling field {field.get('label')}: {e}")
            return False

        return False

    def _find_best_select_option(self, value: Any, options: List[Dict]) -> Optional[Dict]:
        """Find best matching option in select/radio"""
        value_str = str(value).lower()

        # Exact match
        for opt in options:
            if opt['text'].lower() == value_str:
                return opt

        # Partial match
        for opt in options:
            if value_str in opt['text'].lower() or opt['text'].lower() in value_str:
                return opt

        return None

    async def _click_submit_or_next(self, page: Page) -> bool:
        """Click Submit or Next button"""
        # Submit button selectors
        submit_selectors = [
            'button:has-text("Submit")',
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit Application")',
            'button:has-text("Apply")'
        ]

        for selector in submit_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    return True
            except:
                continue

        # Next button selectors
        next_selectors = [
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'a:has-text("Next")',
            'a:has-text("Continue")'
        ]

        for selector in next_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    return False
            except:
                continue

        return False

    async def _click_next_button(self, page: Page) -> bool:
        """Click Next/Continue button"""
        next_selectors = [
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'a:has-text("Next")',
            'a:has-text("Continue")'
        ]

        for selector in next_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(2000)
                    return True
            except:
                continue

        return False

    async def _is_application_complete(self, page: Page) -> bool:
        """Check if application is complete"""
        completion_indicators = [
            'text=Application submitted',
            'text=Thank you for applying',
            'text=We have received your application',
            'text=Application received',
            '.success-message',
            '.confirmation-message'
        ]

        for indicator in completion_indicators:
            try:
                elem = await page.query_selector(indicator)
                if elem:
                    return True
            except:
                continue

        return False

    async def _verify_submission_success(self, page: Page) -> bool:
        """Verify application was submitted successfully"""
        return await self._is_application_complete(page)

    async def _check_for_errors(self, page: Page) -> Optional[str]:
        """Check for error messages on page"""
        error_selectors = [
            '.error-message',
            '.alert-error',
            '.validation-error',
            '[role="alert"]'
        ]

        for selector in error_selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    return await elem.inner_text()
            except:
                continue

        return None

    async def _extract_confirmation_number(self, page: Page) -> Optional[str]:
        """Extract confirmation/application number if available"""
        page_text = await page.inner_text('body')

        # Look for patterns like "Application #12345" or "Confirmation: ABC123"
        patterns = [
            r'Application\s*#?\s*:?\s*([A-Z0-9-]+)',
            r'Confirmation\s*#?\s*:?\s*([A-Z0-9-]+)',
            r'Reference\s*#?\s*:?\s*([A-Z0-9-]+)',
            r'ID\s*:?\s*([A-Z0-9-]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _save_application(
        self,
        user_id: str,
        job_id: str,
        resume_id: Optional[str],
        cover_letter_id: Optional[str],
        forwarding_email: str,
        form_data: Dict,
        screenshot_path: str,
        confirmation_number: Optional[str],
        success: bool
    ) -> Dict:
        """Save successful application to database"""
        application_doc = {
            "user_id": ObjectId(user_id),
            "job_id": ObjectId(job_id),
            "resume_id": ObjectId(resume_id) if resume_id else None,
            "cover_letter_id": ObjectId(cover_letter_id) if cover_letter_id else None,
            "forwarding_email": forwarding_email,
            "method": "auto_apply",
            "form_data": form_data,
            "screenshot_url": screenshot_path,
            "confirmation_number": confirmation_number,
            "status": "submitted" if success else "failed",
            "auto_apply_success": success,
            "submitted_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = self.db.applications.insert_one(application_doc)
        application_doc["_id"] = result.inserted_id

        logger.info(f"Saved application {application_doc['_id']}")

        return application_doc

    def _save_failed_application(self, user_id: str, job_id: str, error: str):
        """Save failed application attempt"""
        application_doc = {
            "user_id": ObjectId(user_id),
            "job_id": ObjectId(job_id),
            "method": "auto_apply",
            "status": "failed",
            "auto_apply_success": False,
            "auto_apply_error": error,
            "created_at": datetime.utcnow()
        }

        self.db.applications.insert_one(application_doc)
