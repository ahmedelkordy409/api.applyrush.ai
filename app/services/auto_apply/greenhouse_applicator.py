"""
Greenhouse Applicator - Specialized applicator for Greenhouse.io ATS
Handles multi-step forms, custom questions, and demographic questions
"""

from typing import Dict, Any, Optional
import logging
from .base_applicator import BaseApplicator, ATSType
from .field_detector import FieldDetector
from .file_upload_handler import FileUploadHandler
from .captcha_detector import CAPTCHADetector

logger = logging.getLogger(__name__)


class GreenhouseApplicator(BaseApplicator):
    """Specialized applicator for Greenhouse.io job applications"""

    async def detect_ats_type(self) -> ATSType:
        """Detect if this is a Greenhouse application"""
        try:
            # Check URL
            url = self.page.url
            if 'greenhouse.io' in url or 'boards.greenhouse' in url:
                return ATSType.GREENHOUSE

            # Check for Greenhouse-specific elements
            greenhouse_indicators = [
                '#application_form',
                '[data-source="greenhouse"]',
                '.greenhouse-application',
            ]

            for selector in greenhouse_indicators:
                element = await self.page.query_selector(selector)
                if element:
                    return ATSType.GREENHOUSE

            return ATSType.GENERIC

        except Exception as e:
            logger.error(f"ATS detection error: {str(e)}")
            return ATSType.GENERIC

    async def fill_form(self, user_data: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        """
        Fill Greenhouse application form

        Greenhouse forms typically have:
        1. Basic information (name, email, phone)
        2. Resume upload
        3. Custom questions (role-specific)
        4. Demographic questions (optional)
        5. Legal agreements
        """
        try:
            # Initialize helpers
            field_detector = FieldDetector(self.page)
            file_handler = FileUploadHandler(self.page)
            captcha_detector = CAPTCHADetector(self.page)

            # Check for CAPTCHA
            captcha_result = await captcha_detector.detect()
            if captcha_result["detected"]:
                self.warnings.append(f"CAPTCHA detected: {captcha_result['type']}")
                logger.warning(f"CAPTCHA detected: {captcha_result['type']}")
                # In production, could integrate with CAPTCHA solving service
                # For now, we'll skip this application
                return {"success": False, "error": "CAPTCHA required"}

            # Step 1: Fill basic fields
            logger.info("Filling basic information fields")
            basic_fields_result = await field_detector.fill_all_basic_fields(user_data)
            self.steps_completed.append("basic_fields_filled")
            await self.take_screenshot("basic_fields_filled")

            # Step 2: Upload resume
            logger.info("Uploading resume")
            resume_uploaded = await file_handler.upload_resume(resume_path)
            if resume_uploaded:
                self.steps_completed.append("resume_uploaded")
            else:
                self.warnings.append("Resume upload may have failed")
            await self.take_screenshot("resume_uploaded")

            # Step 3: Handle custom questions
            logger.info("Handling custom questions")
            custom_questions_result = await self._handle_custom_questions(user_data)
            if custom_questions_result["success"]:
                self.steps_completed.append("custom_questions_answered")
            await self.take_screenshot("custom_questions_filled")

            # Step 4: Handle demographic questions (optional, skip)
            logger.info("Handling demographic questions")
            await self._handle_demographic_questions(skip=True)
            self.steps_completed.append("demographic_questions_handled")

            # Step 5: Check and accept legal agreements
            logger.info("Accepting legal agreements")
            await self._check_legal_agreements()
            self.steps_completed.append("legal_agreements_accepted")
            await self.take_screenshot("before_submit")

            # Step 6: Check if this is multi-step form
            has_next_button = await self._detect_next_button()
            if has_next_button:
                logger.info("Multi-step form detected, handling navigation")
                await self._handle_multistep_form(user_data, resume_path)

            return {
                "success": True,
                "basic_fields": basic_fields_result,
                "resume_uploaded": resume_uploaded,
                "custom_questions": custom_questions_result
            }

        except Exception as e:
            logger.error(f"Form filling error: {str(e)}")
            self.errors.append(str(e))
            return {"success": False, "error": str(e)}

    async def _handle_custom_questions(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle Greenhouse custom questions

        Custom questions can be:
        - Text inputs
        - Textareas
        - Select dropdowns
        - Radio buttons
        - Checkboxes
        """
        try:
            answered = 0

            # Find all visible text inputs and textareas that aren't basic fields
            custom_text_fields = await self.page.query_selector_all(
                'input[type="text"]:not([name*="name" i]):not([name*="email" i]):not([name*="phone" i]), '
                'textarea'
            )

            for field in custom_text_fields:
                if not await field.is_visible():
                    continue

                # Get question label
                field_id = await field.get_attribute('id')
                question_text = await self._extract_question_label(field_id)

                # Determine appropriate answer
                answer = self._generate_answer_for_question(question_text, user_data)

                if answer:
                    await field.scroll_into_view_if_needed()
                    await field.fill(answer)
                    answered += 1
                    await self.human_delay(0.5, 1.5)

            # Handle select dropdowns
            select_fields = await self.page.query_selector_all('select')
            for select in select_fields:
                if not await select.is_visible():
                    continue

                # Select a reasonable option (avoid selecting placeholder)
                options = await select.query_selector_all('option')
                if len(options) > 1:
                    # Select second option (first is usually placeholder)
                    await select.select_option(index=1)
                    answered += 1

            logger.info(f"Answered {answered} custom questions")
            return {"success": True, "questions_answered": answered}

        except Exception as e:
            logger.error(f"Custom questions error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_demographic_questions(self, skip: bool = True) -> None:
        """
        Handle optional demographic questions

        Greenhouse typically has optional demographic questions about:
        - Race/ethnicity
        - Gender
        - Veteran status
        - Disability status

        Args:
            skip: If True, select "Prefer not to answer" options
        """
        try:
            if not skip:
                return  # Skip demographic questions for privacy

            # Look for "Prefer not to answer" options
            prefer_not_to_answer = await self.page.query_selector_all(
                'input[value*="prefer not" i], '
                'input[value*="decline" i], '
                'option:has-text("Prefer not to answer")'
            )

            for element in prefer_not_to_answer:
                if await element.is_visible():
                    tag_name = await element.evaluate('el => el.tagName')

                    if tag_name.lower() == 'input':
                        input_type = await element.get_attribute('type')
                        if input_type in ['radio', 'checkbox']:
                            await element.click()
                            await self.human_delay(0.3, 0.7)

            logger.info("Demographic questions handled (skipped)")

        except Exception as e:
            logger.warning(f"Demographic questions handling warning: {str(e)}")

    async def _check_legal_agreements(self) -> None:
        """Check all legal agreement checkboxes"""
        try:
            # Find all checkboxes with legal-related text
            legal_keywords = ['agree', 'terms', 'consent', 'privacy', 'acknowledge', 'accept']

            checkboxes = await self.page.query_selector_all('input[type="checkbox"]')

            for checkbox in checkboxes:
                if not await checkbox.is_visible():
                    continue

                # Get associated label text
                checkbox_id = await checkbox.get_attribute('id')
                label_text = await self._extract_question_label(checkbox_id)

                # Check if this is a legal agreement
                if any(keyword in label_text.lower() for keyword in legal_keywords):
                    # Check if not already checked
                    is_checked = await checkbox.is_checked()
                    if not is_checked:
                        await checkbox.scroll_into_view_if_needed()
                        await checkbox.check()
                        await self.human_delay(0.3, 0.7)
                        logger.info(f"Checked legal agreement: {label_text[:50]}...")

        except Exception as e:
            logger.warning(f"Legal agreements handling warning: {str(e)}")

    async def _detect_next_button(self) -> bool:
        """Detect if form has a Next/Continue button (multi-step)"""
        try:
            next_button_selectors = [
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'input[value="Next"]',
                'input[value="Continue"]',
            ]

            for selector in next_button_selectors:
                button = await self.page.query_selector(selector)
                if button and await button.is_visible():
                    return True

            return False

        except:
            return False

    async def _handle_multistep_form(self, user_data: Dict[str, Any], resume_path: str) -> None:
        """
        Handle multi-step Greenhouse forms

        Navigate through multiple form pages
        """
        try:
            max_steps = 10  # Safety limit
            current_step = 0

            while current_step < max_steps:
                current_step += 1

                # Check if there's a next button
                has_next = await self._detect_next_button()

                if not has_next:
                    logger.info("No more steps, form complete")
                    break

                # Click next button
                next_button_selectors = [
                    'button:has-text("Next")',
                    'button:has-text("Continue")',
                ]

                clicked = False
                for selector in next_button_selectors:
                    try:
                        button = await self.page.query_selector(selector)
                        if button and await button.is_visible():
                            await button.scroll_into_view_if_needed()
                            await self.take_screenshot(f"step_{current_step}_before_next")
                            await button.click()
                            await self.page.wait_for_load_state('networkidle', timeout=10000)
                            await self.human_delay(1, 2)
                            await self.take_screenshot(f"step_{current_step}_after_next")
                            clicked = True
                            self.steps_completed.append(f"completed_step_{current_step}")
                            break
                    except:
                        continue

                if not clicked:
                    logger.warning("Could not click next button")
                    break

                # Fill any new fields that appeared
                field_detector = FieldDetector(self.page)
                await field_detector.fill_all_basic_fields(user_data)
                await self._handle_custom_questions(user_data)

            logger.info(f"Completed {current_step} form steps")

        except Exception as e:
            logger.error(f"Multi-step form navigation error: {str(e)}")
            self.errors.append(f"Multi-step navigation: {str(e)}")

    async def _extract_question_label(self, field_id: Optional[str]) -> str:
        """Extract question label text for a field"""
        try:
            if not field_id:
                return ""

            # Look for associated label
            label = await self.page.query_selector(f'label[for="{field_id}"]')
            if label:
                return await label.inner_text()

            # Look for nearby text
            field = await self.page.query_selector(f'#{field_id}')
            if field:
                # Get aria-label
                aria_label = await field.get_attribute('aria-label')
                if aria_label:
                    return aria_label

                # Get placeholder
                placeholder = await field.get_attribute('placeholder')
                if placeholder:
                    return placeholder

            return ""

        except:
            return ""

    def _generate_answer_for_question(self, question: str, user_data: Dict[str, Any]) -> str:
        """
        Generate appropriate answer for custom question

        Args:
            question: Question text
            user_data: User profile data

        Returns:
            Answer text
        """
        question_lower = question.lower()

        # Availability question
        if any(word in question_lower for word in ['when can you start', 'start date', 'availability']):
            return user_data.get('availability', '2 weeks notice')

        # Salary question
        if any(word in question_lower for word in ['salary', 'compensation', 'expected pay']):
            salary = user_data.get('salary_expectation')
            if salary:
                return str(salary)
            return "Negotiable based on total compensation package"

        # Sponsorship question
        if 'sponsor' in question_lower or 'visa' in question_lower or 'work authorization' in question_lower:
            return user_data.get('work_authorized', 'Yes')

        # Why company / why this role
        if any(word in question_lower for word in ['why', 'interested', 'motivates you']):
            company = user_data.get('company_name', 'the company')
            role = user_data.get('job_title', 'this role')
            return f"I am excited about the opportunity at {company} because my skills and experience align well with {role}. I am particularly interested in contributing to your team's success."

        # Experience question
        if 'experience' in question_lower:
            years = user_data.get('experience_years', 3)
            return f"I have {years} years of relevant experience in this field."

        # Default professional response
        return "I believe my background makes me a strong candidate for this position and I am excited about the opportunity to contribute to your team."


__all__ = ["GreenhouseApplicator"]
