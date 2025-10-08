"""
Auto-Apply Module
Browser automation for job applications with email forwarding support
"""

from .base_applicator import BaseApplicator, ApplicationResult
from .email_applicator import EmailApplicator
from .field_detector import FieldDetector
from .file_upload_handler import FileUploadHandler
from .captcha_detector import CAPTCHADetector

__all__ = [
    "BaseApplicator",
    "ApplicationResult",
    "EmailApplicator",
    "FieldDetector",
    "FileUploadHandler",
    "CAPTCHADetector",
]
