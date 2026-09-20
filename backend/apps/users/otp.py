"""Real OTP issuance + verification (P0-2, ADR-003).

Replaces the deterministic "123456" stub: 6-digit codes, hashed at rest,
10-minute expiry, max 5 verify attempts, resend cooldown, per-phone + per-IP
daily caps, and phone↔code binding. The SMS provider is an abstraction —
the concrete provider wires in when Siju picks one; the response-returning
stub survives ONLY behind DEBUG.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from abc import ABC, abstractmethod
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from apps.users.models import OtpCode

logger = logging.getLogger(__name__)


class OtpError(Exception):
    """An OTP flow error surfaced to the client as a 400 field/detail error."""


class OtpRateLimited(OtpError):
    """The request exceeded an OTP rate limit."""


def _hash_code(phone: str, code: str) -> str:
    """Bind the code to its phone before hashing (code+phone binding)."""
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def _generate_code(length: int = 6) -> str:
    """Cryptographically random numeric code of ``length`` digits."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


class OtpSender(ABC):
    """SMS delivery abstraction — the concrete provider wires in later
    (the SMS provider pick + credentials are pending a product decision)."""

    name = "abstract"

    @abstractmethod
    def send_otp(self, phone: str, code: str) -> None:
        """Deliver ``code`` to ``phone``."""


class ConsoleOtpSender(OtpSender):
    """Logs the OTP for QA testing (never returned in API responses)."""

    name = "console"

    def send_otp(self, phone: str, code: str) -> None:
        logger.info("OTP for %s: %s", phone, code)


class StubOtpSender(OtpSender):
    """Returns the code to the caller — DEBUG/test ONLY (a prod blocker)."""

    name = "stub"
    code: str | None = None

    def send_otp(self, phone: str, code: str) -> None:
        self.code = code


def get_otp_sender():
    """Resolve the configured sender; the stub requires DEBUG."""
    backend = getattr(settings, "OTP_SENDER", "console")
    if backend == "console":
        return ConsoleOtpSender()
    if backend == "stub":
        if not settings.DEBUG:
            raise ImproperlyConfigured("The OTP stub sender is DEBUG-only.")
        return StubOtpSender()
    # A concrete SMS provider will be registered here once the pick lands.
    raise ImproperlyConfigured(f"Unknown OTP_SENDER: {backend}")


def issue_otp(phone: str, tenant, ip: str | None = None, sender: OtpSender | None = None) -> int:
    """Generate, store and deliver an OTP for ``phone`` (P0-2).

    Enforces the resend cooldown and the per-phone + per-IP daily caps.

    Returns:
        Seconds until the code expires.
    """
    now = timezone.now()
    day_start = now - timedelta(hours=24)

    cooldown = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
    latest = OtpCode.objects.filter(phone=phone).order_by("-created_at").first()
    if latest and now - latest.created_at < timedelta(seconds=cooldown):
        raise OtpError("Please wait before requesting another code.")

    per_phone_cap = getattr(settings, "OTP_DAILY_LIMIT_PER_PHONE", 10)
    phone_today = OtpCode.objects.filter(phone=phone, created_at__gte=day_start).count()
    if phone_today >= per_phone_cap:
        raise OtpRateLimited("Daily OTP limit reached for this phone.")

    per_ip_cap = getattr(settings, "OTP_DAILY_LIMIT_PER_IP", 50)
    if ip:
        ip_today = OtpCode.objects.filter(ip=ip, created_at__gte=day_start).count()
        if ip_today >= per_ip_cap:
            raise OtpRateLimited("Daily OTP limit reached.")

    code = _generate_code()
    ttl = getattr(settings, "OTP_TTL_SECONDS", 600)
    OtpCode.objects.create(
        phone=phone,
        tenant=tenant,
        code_hash=_hash_code(phone, code),
        ip=ip,
        expires_at=now + timedelta(seconds=ttl),
    )
    (sender or get_otp_sender()).send_otp(phone, code)
    return ttl


def verify_otp(phone: str, code: str, tenant=None) -> OtpCode:
    """Verify ``code`` for ``phone`` (P0-2).

    Enforces phone↔code binding (optionally scoped to the resolved tenant),
    the 10-minute expiry, the max 5 attempts and single-use consumption.

    Returns:
        The consumed :class:`~apps.users.models.OtpCode` row.
    """
    max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
    rows = OtpCode.objects.filter(phone=phone, is_used=False)
    if tenant is not None:
        rows = rows.filter(tenant=tenant)
    row = rows.order_by("-created_at").first()
    if row is None:
        raise OtpError("No active code. Request a new one.")
    if row.expires_at and row.expires_at < timezone.now():
        raise OtpError("This code has expired. Request a new one.")
    if row.attempts >= max_attempts:
        raise OtpError("Too many attempts. Request a new one.")

    candidate_hash = _hash_code(phone, code)
    row.attempts += 1
    row.save(update_fields=["attempts"])

    if not hmac.compare_digest(row.code_hash, candidate_hash):
        raise OtpError("Invalid code.")
    row.is_used = True
    row.save(update_fields=["is_used"])
    return row
