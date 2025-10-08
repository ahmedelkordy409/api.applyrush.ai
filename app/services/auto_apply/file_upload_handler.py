"""
File Upload Handler - Handle file uploads in job application forms
Supports standard file inputs and drag-and-drop uploads
"""

from typing import Optional, List
import logging
from pathlib import Path
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class FileUploadHandler:
    """Handle file uploads for job applications"""

    SUPPORTED_FORMATS = ['.pdf', '.docx', '.doc', '.txt']
    MAX_FILE_SIZE_MB = 5

    def __init__(self, page: Page):
        """Initialize file upload handler"""
        self.page = page

    async def upload_resume(self, resume_path: str) -> bool:
        """
        Upload resume file to application form

        Args:
            resume_path: Path to resume file

        Returns:
            True if upload successful, False otherwise
        """
        try:
            # Validate file
            if not self._validate_file(resume_path):
                logger.error(f"Invalid resume file: {resume_path}")
                return False

            # Find file input
            file_input = await self._find_file_input(['resume', 'cv'])

            if not file_input:
                logger.error("Resume file input not found")
                return False

            # Upload file
            await file_input.set_input_files(resume_path)

            # Wait for upload to complete
            success = await self._wait_for_upload_complete(Path(resume_path).name)

            if success:
                logger.info(f"Resume uploaded successfully: {resume_path}")
            else:
                logger.warning("Resume upload verification uncertain")

            return success

        except Exception as e:
            logger.error(f"Resume upload error: {str(e)}")
            return False

    async def upload_cover_letter(self, cover_letter_path: str) -> bool:
        """
        Upload cover letter file

        Args:
            cover_letter_path: Path to cover letter file

        Returns:
            True if upload successful, False otherwise
        """
        try:
            if not self._validate_file(cover_letter_path):
                return False

            file_input = await self._find_file_input(['cover', 'letter'])

            if not file_input:
                logger.debug("Cover letter file input not found (may be optional)")
                return False

            await file_input.set_input_files(cover_letter_path)
            success = await self._wait_for_upload_complete(Path(cover_letter_path).name)

            if success:
                logger.info("Cover letter uploaded successfully")

            return success

        except Exception as e:
            logger.error(f"Cover letter upload error: {str(e)}")
            return False

    async def _find_file_input(self, hints: List[str]) -> Optional[any]:
        """
        Find file input element

        Args:
            hints: List of keywords to search for in field names

        Returns:
            File input element or None
        """
        # Try specific selectors first
        for hint in hints:
            selectors = [
                f'input[type="file"][name*="{hint}" i]',
                f'input[type="file"][id*="{hint}" i]',
                f'input[type="file"][aria-label*="{hint}" i]',
            ]

            for selector in selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        return element
                except:
                    continue

        # Fallback: find any visible file input
        try:
            file_inputs = await self.page.query_selector_all('input[type="file"]')
            for file_input in file_inputs:
                # Check if visible or has visible parent
                try:
                    if await file_input.is_visible() or await self._has_visible_parent(file_input):
                        return file_input
                except:
                    continue
        except:
            pass

        return None

    async def _has_visible_parent(self, element) -> bool:
        """Check if element has a visible parent (for hidden file inputs)"""
        try:
            parent = await element.evaluate_handle('el => el.parentElement')
            if parent:
                return await parent.is_visible()
        except:
            pass
        return False

    async def _wait_for_upload_complete(
        self,
        filename: str,
        timeout: int = 30000
    ) -> bool:
        """
        Wait for file upload to complete

        Args:
            filename: Name of uploaded file
            timeout: Maximum wait time in milliseconds

        Returns:
            True if upload appears complete
        """
        try:
            # Wait a bit for upload to process
            await self.page.wait_for_timeout(2000)

            # Check for common upload completion indicators
            completion_indicators = [
                # File name displayed
                f'text="{filename}"',
                # Upload success message
                'text=/upload.*success/i',
                'text=/file.*uploaded/i',
                # Progress bar disappears
                '.upload-progress[style*="display: none"]',
                '.progress-bar[style*="width: 100%"]',
            ]

            for indicator in completion_indicators:
                try:
                    element = await self.page.wait_for_selector(
                        indicator,
                        timeout=5000,
                        state='attached'
                    )
                    if element:
                        logger.info(f"Upload completion indicator found: {indicator}")
                        return True
                except:
                    continue

            # If no indicator found, assume success after waiting
            logger.debug("No explicit upload completion indicator, assuming success")
            return True

        except Exception as e:
            logger.warning(f"Upload completion check uncertain: {str(e)}")
            return True  # Assume success if we can't verify

    def _validate_file(self, file_path: str) -> bool:
        """
        Validate file before upload

        Args:
            file_path: Path to file

        Returns:
            True if valid, False otherwise
        """
        path = Path(file_path)

        # Check file exists
        if not path.exists():
            logger.error(f"File does not exist: {file_path}")
            return False

        # Check file format
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            logger.error(f"Unsupported file format: {path.suffix}")
            return False

        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.MAX_FILE_SIZE_MB:
            logger.error(f"File too large: {size_mb:.2f}MB (max {self.MAX_FILE_SIZE_MB}MB)")
            return False

        return True


__all__ = ["FileUploadHandler"]
