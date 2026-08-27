"""Email service using SendGrid."""

from __future__ import annotations

import logging
import os

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str = "",
    from_email: str | None = None,
) -> bool:
    """Send an email via SendGrid (or console in dev).

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_content: HTML body content.
        text_content: Plain-text fallback body.
        from_email: Override sender address, or use DEFAULT_FROM_EMAIL.

    Returns:
        ``True`` if the email was sent successfully, ``False`` otherwise.
    """
    if not settings.DEBUG and not settings.SENDGRID_API_KEY:
        # In production without SendGrid, log and skip
        logger.warning(
            "Email not sent (no SENDGRID_API_KEY): %s — %s",
            to_email,
            subject,
        )
        return False

    try:
        email = EmailMessage(
            subject=subject,
            body=text_content,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_verification_email(user, request) -> bool:
    """Send email verification link to a newly registered user.

    Args:
        user: The user who just registered.
        request: The HTTP request (used to build the verification URL).

    Returns:
        ``True`` if the email was sent successfully, ``False`` otherwise.
    """
    from apps.users.models import EmailVerificationToken

    token = EmailVerificationToken.create_token(user)
    verify_url = f"{_get_base_url(request)}/api/v1/auth/verify-email/{token.token}/"

    subject = "Verify your email — FitNation"
    html_content = f"""
    <h2>Welcome to FitNation, {user.first_name}!</h2>
    <p>Please verify your email address by clicking the button below:</p>
    <a href="{verify_url}" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;margin:16px 0;">Verify Email</a>
    <p>This link expires in 24 hours. If you didn't create an account, you can ignore this email.</p>
    """
    text_content = f"Welcome to FitNation! Verify your email: {verify_url}"

    return send_email(user.email, subject, html_content, text_content)


def _get_base_url(request) -> str:
    """Get the base URL for building email links.

    Args:
        request: The HTTP request, or ``None`` in CLI/management contexts.

    Returns:
        The base URL string (e.g. ``https://app.fitnationapp.com``).
    """
    if request:
        return f"{request.scheme}://{request.get_host()}"
    return os.environ.get("APP_BASE_URL", "https://app.fitnationapp.com")
