"""
Field Detector - Smart form field detection and filling
Handles various naming conventions and selector strategies
"""

from typing import Dict, Any, List, Optional
import logging
from playwright.async_api import Page, Locator

logger = logging.getLogger(__name__)


class FieldDetector:
    """Smart field detection and filling for job application forms"""

    # Field selector mappings (prioritized)
    FIELD_SELECTORS = {
        'first_name': [
            'input[name*="first" i][name*="name" i]',
            'input[id*="first" i][id*="name" i]',
            'input[placeholder*="first name" i]',
            'input[aria-label*="first name" i]',
            'label:has-text("First Name") + input',
            'input[name="fname"]',
            'input[name="firstName"]',
        ],
        'last_name': [
            'input[name*="last" i][name*="name" i]',
            'input[id*="last" i][id*="name" i]',
            'input[placeholder*="last name" i]',
            'input[aria-label*="last name" i]',
            'label:has-text("Last Name") + input',
            'input[name="lname"]',
            'input[name="lastName"]',
        ],
        'full_name': [
            'input[name*="full" i][name*="name" i]',
            'input[name="name"]',
            'input[placeholder*="full name" i]',
            'input[placeholder*="your name" i]',
        ],
        'email': [
            'input[type="email"]',
            'input[name*="email" i]',
            'input[id*="email" i]',
            'input[placeholder*="email" i]',
            'input[aria-label*="email" i]',
        ],
        'phone': [
            'input[type="tel"]',
            'input[name*="phone" i]',
            'input[name*="mobile" i]',
            'input[id*="phone" i]',
            'input[placeholder*="phone" i]',
            'input[aria-label*="phone" i]',
        ],
        'linkedin': [
            'input[name*="linkedin" i]',
            'input[id*="linkedin" i]',
            'input[placeholder*="linkedin" i]',
            'input[placeholder*="profile url" i]',
        ],
        'portfolio': [
            'input[name*="portfolio" i]',
            'input[name*="website" i]',
            'input[name*="github" i]',
            'input[placeholder*="portfolio" i]',
            'input[placeholder*="personal website" i]',
        ],
        'location': [
            'input[name*="location" i]',
            'input[name*="city" i]',
            'input[id*="location" i]',
            'input[placeholder*="location" i]',
            'input[placeholder*="city" i]',
        ],
        'resume': [
            'input[type="file"][name*="resume" i]',
            'input[type="file"][name*="cv" i]',
            'input[type="file"][id*="resume" i]',
            'input[type="file"]',
        ],
        'cover_letter_file': [
            'input[type="file"][name*="cover" i]',
            'input[type="file"][name*="letter" i]',
        ],
        'cover_letter_text': [
            'textarea[name*="cover" i]',
            'textarea[name*="letter" i]',
            'textarea[placeholder*="cover letter" i]',
        ],
        'additional_info': [
            'textarea[name*="additional" i]',
            'textarea[name*="info" i]',
            'textarea[name*="message" i]',
            'textarea[name*="comments" i]',
        ],
    }

    def __init__(self, page: Page):
        """Initialize field detector with page"""
        self.page = page

    async def find_and_fill(
        self,
        field_type: str,
        value: str,
        required: bool = True
    ) -> bool:
        """
        Find field by type and fill with value

        Args:
            field_type: Type of field (e.g., 'first_name', 'email')
            value: Value to fill
            required: Whether field is required

        Returns:
            True if filled successfully, False otherwise
        """
        try:
            selectors = self.FIELD_SELECTORS.get(field_type, [])

            for selector in selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        # Scroll into view
                        await element.scroll_into_view_if_needed()

                        # Clear existing value
                        await element.fill('')

                        # Fill with new value
                        await element.fill(value)

                        # Verify fill succeeded
                        filled_value = await element.input_value()
                        if filled_value == value:
                            logger.info(f"Filled {field_type} with selector: {selector}")
                            return True

                except Exception as e:
                    # Try next selector
                    continue

            if required:
                logger.warning(f"Required field '{field_type}' not found")
            else:
                logger.debug(f"Optional field '{field_type}' not found")

            return False

        except Exception as e:
            logger.error(f"Error filling {field_type}: {str(e)}")
            return False

    async def fill_all_basic_fields(self, user_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Fill all basic application fields

        Args:
            user_data: Dictionary with user information

        Returns:
            Dictionary mapping field_type to status ('filled', 'not_found', 'error')
        """
        results = {}

        # Field mapping
        field_mapping = {
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'full_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
            'email': user_data.get('email', ''),
            'phone': user_data.get('phone', ''),
            'linkedin': user_data.get('linkedin_url', ''),
            'portfolio': user_data.get('portfolio_url', ''),
            'location': user_data.get('location', ''),
        }

        for field_type, value in field_mapping.items():
            if not value:
                results[field_type] = 'skipped_empty'
                continue

            success = await self.find_and_fill(
                field_type=field_type,
                value=value,
                required=(field_type in ['first_name', 'last_name', 'email'])
            )

            results[field_type] = 'filled' if success else 'not_found'

        return results

    async def fill_textarea_field(
        self,
        field_type: str,
        content: str
    ) -> bool:
        """Fill textarea fields (cover letter, additional info)"""
        try:
            selectors = self.FIELD_SELECTORS.get(field_type, [])

            for selector in selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.scroll_into_view_if_needed()
                        await element.fill(content)
                        logger.info(f"Filled textarea {field_type}")
                        return True
                except:
                    continue

            return False

        except Exception as e:
            logger.error(f"Error filling textarea {field_type}: {str(e)}")
            return False

    async def detect_and_fill_location(self, location: str) -> bool:
        """
        Detect and fill location field (may be autocomplete)
        """
        try:
            success = await self.find_and_fill('location', location, required=False)

            if success:
                # Wait for autocomplete to appear
                await self.page.wait_for_timeout(1000)

                # Try to select first autocomplete option
                try:
                    autocomplete_option = await self.page.query_selector(
                        '[role="option"]:first-child, .autocomplete-item:first-child'
                    )
                    if autocomplete_option:
                        await autocomplete_option.click()
                        logger.info("Selected autocomplete location")
                except:
                    pass

            return success

        except Exception as e:
            logger.error(f"Location fill error: {str(e)}")
            return False

    async def check_all_required_fields_filled(self) -> Dict[str, Any]:
        """
        Check if all required fields are filled

        Returns:
            Dictionary with validation results
        """
        try:
            # Find all required fields
            required_fields = await self.page.query_selector_all(
                'input[required], textarea[required], select[required]'
            )

            empty_required = []

            for field in required_fields:
                # Check if field is visible
                if not await field.is_visible():
                    continue

                # Get field value
                tag_name = await field.evaluate('el => el.tagName')

                if tag_name.lower() == 'select':
                    value = await field.evaluate('el => el.value')
                else:
                    value = await field.input_value()

                if not value or value.strip() == '':
                    # Get field name for debugging
                    field_name = await field.get_attribute('name') or await field.get_attribute('id') or 'unknown'
                    empty_required.append(field_name)

            return {
                "all_filled": len(empty_required) == 0,
                "empty_fields": empty_required,
                "total_required": len(required_fields)
            }

        except Exception as e:
            logger.error(f"Required field check error: {str(e)}")
            return {
                "all_filled": False,
                "error": str(e)
            }


__all__ = ["FieldDetector"]
