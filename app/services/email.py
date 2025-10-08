"""
Email service for sending notifications and magic links
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import aiosmtplib
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending various types of emails"""

    def __init__(self):
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', '')
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
        self.from_email = getattr(settings, 'FROM_EMAIL', 'noreply@applyrush.ai')
        self.from_name = getattr(settings, 'FROM_NAME', 'ApplyRush.AI')

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email using SMTP"""
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = f"{self.from_name} <{self.from_email}>"
            message['To'] = to_email

            # Add text part
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                message.attach(text_part)

            # Add HTML part
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)

            # Send email
            async with aiosmtplib.SMTP(hostname=self.smtp_server, port=self.smtp_port) as server:
                await server.starttls()
                await server.login(self.smtp_username, self.smtp_password)
                await server.send_message(message)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def _get_magic_link_template(self, magic_link_url: str) -> tuple[str, str]:
        """Get magic link email template"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Sign in to ApplyRush.AI</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 40px;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #2563eb;
                }}
                .button {{
                    display: inline-block;
                    background-color: #2563eb;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 20px 0;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    font-size: 14px;
                    color: #6b7280;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">ApplyRush.AI</div>
            </div>

            <h2>Sign in to your account</h2>

            <p>Click the button below to sign in to your ApplyRush.AI account. This link will expire in 15 minutes.</p>

            <p style="text-align: center;">
                <a href="{magic_link_url}" class="button">Sign In</a>
            </p>

            <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #2563eb;">{magic_link_url}</p>

            <div class="footer">
                <p>If you didn't request this email, you can safely ignore it.</p>
                <p>&copy; 2024 ApplyRush.AI. All rights reserved.</p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Sign in to ApplyRush.AI

        Click the link below to sign in to your account:
        {magic_link_url}

        This link will expire in 15 minutes.

        If you didn't request this email, you can safely ignore it.

        © 2024 ApplyRush.AI. All rights reserved.
        """

        return html_content, text_content

    def _get_welcome_template(self, user_name: str, temp_password: Optional[str] = None) -> tuple[str, str]:
        """Get welcome email template"""
        password_section = ""
        if temp_password:
            password_section = f"""
            <p><strong>Temporary Password:</strong> {temp_password}</p>
            <p>Please change this password after your first login for security.</p>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Welcome to ApplyRush.AI</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 40px;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #2563eb;
                }}
                .button {{
                    display: inline-block;
                    background-color: #2563eb;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 6px;
                    margin: 20px 0;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    font-size: 14px;
                    color: #6b7280;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">ApplyRush.AI</div>
            </div>

            <h2>Welcome to ApplyRush.AI!</h2>

            <p>Hi {user_name or 'there'},</p>

            <p>Welcome to ApplyRush.AI! We're excited to have you join our platform for AI-powered job applications.</p>

            {password_section}

            <p>Get started by completing your profile and uploading your resume to receive personalized job matches.</p>

            <p style="text-align: center;">
                <a href="{settings.FRONTEND_URL}/dashboard" class="button">Get Started</a>
            </p>

            <div class="footer">
                <p>If you have any questions, feel free to reach out to our support team.</p>
                <p>&copy; 2024 ApplyRush.AI. All rights reserved.</p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Welcome to ApplyRush.AI!

        Hi {user_name or 'there'},

        Welcome to ApplyRush.AI! We're excited to have you join our platform for AI-powered job applications.

        {"Temporary Password: " + temp_password if temp_password else ""}
        {"Please change this password after your first login for security." if temp_password else ""}

        Get started by completing your profile and uploading your resume to receive personalized job matches.

        Visit: {settings.FRONTEND_URL}/dashboard

        If you have any questions, feel free to reach out to our support team.

        © 2024 ApplyRush.AI. All rights reserved.
        """

        return html_content, text_content


# Initialize email service
email_service = EmailService()


async def send_magic_link_email(email: str, magic_link_url: str) -> bool:
    """Send magic link authentication email"""
    try:
        html_content, text_content = email_service._get_magic_link_template(magic_link_url)

        success = await email_service.send_email(
            to_email=email,
            subject="Sign in to ApplyRush.AI",
            html_content=html_content,
            text_content=text_content
        )

        return success
    except Exception as e:
        logger.error(f"Failed to send magic link email: {str(e)}")
        return False


async def send_welcome_email(email: str, user_name: Optional[str] = None, temp_password: Optional[str] = None) -> bool:
    """Send welcome email to new users"""
    try:
        html_content, text_content = email_service._get_welcome_template(user_name, temp_password)

        success = await email_service.send_email(
            to_email=email,
            subject="Welcome to ApplyRush.AI!",
            html_content=html_content,
            text_content=text_content
        )

        return success
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        return False


async def send_application_notification(email: str, job_title: str, company: str) -> bool:
    """Send job application confirmation email"""
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Application Submitted - ApplyRush.AI</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">Application Submitted Successfully!</h2>

                <p>Your application for <strong>{job_title}</strong> at <strong>{company}</strong> has been submitted successfully.</p>

                <p>We'll keep you updated on the status of your application.</p>

                <p>Best of luck!</p>
                <p>The ApplyRush.AI Team</p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Application Submitted Successfully!

        Your application for {job_title} at {company} has been submitted successfully.

        We'll keep you updated on the status of your application.

        Best of luck!
        The ApplyRush.AI Team
        """

        success = await email_service.send_email(
            to_email=email,
            subject=f"Application Submitted: {job_title} at {company}",
            html_content=html_content,
            text_content=text_content
        )

        return success
    except Exception as e:
        logger.error(f"Failed to send application notification email: {str(e)}")
        return False


async def send_password_reset_email(email: str, reset_link: str) -> bool:
    """Send password reset email"""
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Reset Your Password - ApplyRush.AI</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">Reset Your Password</h2>

                <p>You requested to reset your password for your ApplyRush.AI account.</p>

                <p>Click the button below to reset your password:</p>

                <p style="text-align: center;">
                    <a href="{reset_link}" style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Reset Password</a>
                </p>

                <p>This link will expire in 1 hour for security reasons.</p>

                <p>If you didn't request this password reset, you can safely ignore this email.</p>

                <p>Best regards,<br>The ApplyRush.AI Team</p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Reset Your Password

        You requested to reset your password for your ApplyRush.AI account.

        Click the link below to reset your password:
        {reset_link}

        This link will expire in 1 hour for security reasons.

        If you didn't request this password reset, you can safely ignore this email.

        Best regards,
        The ApplyRush.AI Team
        """

        success = await email_service.send_email(
            to_email=email,
            subject="Reset Your Password - ApplyRush.AI",
            html_content=html_content,
            text_content=text_content
        )

        return success
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        return False