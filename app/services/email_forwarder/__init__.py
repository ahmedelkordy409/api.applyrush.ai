"""
Email Forwarder Service
Handle email forwarding for job applications
"""

from .forwarder_service import EmailForwarderService, ForwardingEmail
from .email_parser import ApplicationEmailParser
from .email_tracker import EmailApplicationTracker

__all__ = [
    "EmailForwarderService",
    "ForwardingEmail",
    "ApplicationEmailParser",
    "EmailApplicationTracker",
]
