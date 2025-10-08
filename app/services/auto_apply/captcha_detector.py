"""
CAPTCHA Detector - Detect various CAPTCHA types on job application forms
"""

from typing import Dict, Any, Optional
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class CAPTCHAType:
    """CAPTCHA types"""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    CLOUDFLARE_TURNSTILE = "cloudflare_turnstile"
    NONE = "none"
    UNKNOWN = "unknown"


class CAPTCHADetector:
    """Detect CAPTCHA systems on web pages"""

    def __init__(self, page: Page):
        """Initialize CAPTCHA detector"""
        self.page = page

    async def detect(self) -> Dict[str, Any]:
        """
        Detect CAPTCHA on current page

        Returns:
            Dictionary with detection results:
            {
                "detected": bool,
                "type": str,
                "sitekey": Optional[str],
                "element": Optional[Locator]
            }
        """
        try:
            # Check for reCAPTCHA v2
            if await self.has_recaptcha_v2():
                sitekey = await self._extract_recaptcha_sitekey()
                return {
                    "detected": True,
                    "type": CAPTCHAType.RECAPTCHA_V2,
                    "sitekey": sitekey
                }

            # Check for reCAPTCHA v3
            if await self.has_recaptcha_v3():
                sitekey = await self._extract_recaptcha_sitekey()
                return {
                    "detected": True,
                    "type": CAPTCHAType.RECAPTCHA_V3,
                    "sitekey": sitekey
                }

            # Check for hCaptcha
            if await self.has_hcaptcha():
                sitekey = await self._extract_hcaptcha_sitekey()
                return {
                    "detected": True,
                    "type": CAPTCHAType.HCAPTCHA,
                    "sitekey": sitekey
                }

            # Check for Cloudflare Turnstile
            if await self.has_cloudflare_turnstile():
                return {
                    "detected": True,
                    "type": CAPTCHAType.CLOUDFLARE_TURNSTILE,
                    "sitekey": None
                }

            # No CAPTCHA detected
            return {
                "detected": False,
                "type": CAPTCHAType.NONE,
                "sitekey": None
            }

        except Exception as e:
            logger.error(f"CAPTCHA detection error: {str(e)}")
            return {
                "detected": False,
                "type": CAPTCHAType.UNKNOWN,
                "error": str(e)
            }

    async def has_recaptcha_v2(self) -> bool:
        """Check if page has reCAPTCHA v2"""
        try:
            # Check for iframe
            iframe_selector = 'iframe[src*="recaptcha"]'
            iframe = await self.page.query_selector(iframe_selector)
            if iframe:
                return True

            # Check for g-recaptcha element
            element = await self.page.query_selector('.g-recaptcha')
            return element is not None

        except:
            return False

    async def has_recaptcha_v3(self) -> bool:
        """Check if page has reCAPTCHA v3"""
        try:
            # Check for grecaptcha object in page
            has_grecaptcha = await self.page.evaluate('''
                () => {
                    return typeof grecaptcha !== 'undefined' &&
                           typeof grecaptcha.execute === 'function';
                }
            ''')

            if has_grecaptcha:
                return True

            # Check for reCAPTCHA badge
            badge = await self.page.query_selector('.grecaptcha-badge')
            return badge is not None

        except:
            return False

    async def has_hcaptcha(self) -> bool:
        """Check if page has hCaptcha"""
        try:
            # Check for iframe
            iframe = await self.page.query_selector('iframe[src*="hcaptcha"]')
            if iframe:
                return True

            # Check for h-captcha element
            element = await self.page.query_selector('.h-captcha')
            return element is not None

        except:
            return False

    async def has_cloudflare_turnstile(self) -> bool:
        """Check if page has Cloudflare Turnstile"""
        try:
            # Check for Cloudflare challenge page
            title = await self.page.title()
            if 'cloudflare' in title.lower() or 'just a moment' in title.lower():
                return True

            # Check for turnstile element
            element = await self.page.query_selector('[data-sitekey]')
            if element:
                content = await self.page.content()
                if 'turnstile' in content.lower():
                    return True

            return False

        except:
            return False

    async def _extract_recaptcha_sitekey(self) -> Optional[str]:
        """Extract reCAPTCHA site key"""
        try:
            # Try to get from g-recaptcha element
            element = await self.page.query_selector('.g-recaptcha')
            if element:
                sitekey = await element.get_attribute('data-sitekey')
                if sitekey:
                    return sitekey

            # Try to extract from page source
            content = await self.page.content()
            import re
            match = re.search(r'data-sitekey="([^"]+)"', content)
            if match:
                return match.group(1)

            return None

        except:
            return None

    async def _extract_hcaptcha_sitekey(self) -> Optional[str]:
        """Extract hCaptcha site key"""
        try:
            element = await self.page.query_selector('.h-captcha')
            if element:
                sitekey = await element.get_attribute('data-sitekey')
                if sitekey:
                    return sitekey

            return None

        except:
            return None

    async def wait_for_manual_solve(self, timeout: int = 120000) -> bool:
        """
        Wait for user to manually solve CAPTCHA

        Args:
            timeout: Maximum wait time in milliseconds (default 2 minutes)

        Returns:
            True if CAPTCHA solved, False if timeout
        """
        try:
            start_time = await self.page.evaluate('Date.now()')

            while True:
                # Check if CAPTCHA still present
                detection = await self.detect()
                if not detection["detected"]:
                    logger.info("CAPTCHA solved!")
                    return True

                # Check timeout
                current_time = await self.page.evaluate('Date.now()')
                if current_time - start_time > timeout:
                    logger.warning("CAPTCHA solve timeout")
                    return False

                # Wait before checking again
                await self.page.wait_for_timeout(2000)

        except Exception as e:
            logger.error(f"Error waiting for CAPTCHA solve: {str(e)}")
            return False


__all__ = ["CAPTCHADetector", "CAPTCHAType"]
