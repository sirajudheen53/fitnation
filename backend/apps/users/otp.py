"""Real OTP issuance + verification (anchors & hardening: FBOS-011 §4).

Replaces the deterministic "123456" stub: 6-digit codes, hashed at rest,
10-minute expiry, max 5 verify attempts, resend cooldown, per-phone + per-IP
daily caps, and phone↔code binding.

Delivery is a per-tenant sender chain (FBOS-011 §4.2, issue #66): WATI
WhatsApp template (tenant config) → Gupshup WhatsApp template (tenant
config) → MSG91 SMS (platform config) → loud failure (503). Gupshup's /msg
API 202-acks ANY submit (issue #73), so its leg carries an approved-template
delivery gate (issue #74): the template-management API must show
``fitnation_otp`` APPROVED before a send is trusted — otherwise (and for any
provider-side rejection) the leg raises and the chain propagates to SMS.
The response-returning ``stub`` and the ``console`` logger survive ONLY
behind DEBUG — ``resolve_otp_senders`` refuses both in production, so
shipping with codes going to logs or API responses is structurally impossible.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import logging
import secrets
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

import requests

from apps.notifications.services.channels import (
    GUPSHUP_ACCEPTED_STATUS,
    gupshup_template_status,
    normalize_msisdn,
    post_gupshup_template,
    post_msg91_flow,
    post_wati_template,
    wati_template_endpoint,
)
from apps.notifications.services.router import OTP_CHANNEL_BY_SENDER, gupshup_ready
from apps.users.models import OtpCode

logger = logging.getLogger(__name__)

# WATI approved template (one-time setup in the tenant's WATI console):
# "{{1}} is your {{2}} login code. Valid for {{3}} minutes. Never share this code."
WATI_OTP_TEMPLATE_NAME = "fitnation_otp"
# Gupshup approved template — the same platform-wide slug, approved once in
# the tenant's Gupshup console (issue #66). Shape per issue #85: an
# Authentication-category body whose only variable is the code, so sends
# carry params=[code] and nothing else — deliberately diverging from WATI's
# same-name 3-variable template (see GupshupOtpSender).
GUPSHUP_OTP_TEMPLATE_NAME = "fitnation_otp"


class OtpError(Exception):
    """An OTP flow error surfaced to the client as a 400 field/detail error."""


class OtpRateLimited(OtpError):
    """The request exceeded an OTP rate limit."""


class OtpDeliveryError(Exception):
    """Every configured delivery channel failed (or none is configured).

    Surfaced as a loud 503 with generic copy — never a silent log-file drop.
    ``reason`` is a short machine-readable code (``not_configured``,
    ``daily_cap_reached``, ``template_not_approved``, ``provider_error``,
    ``http_<status>``, ``transport_error``) and ``channels`` the per-leg
    failure map — both flow into the 503 body so the mobile app / operator
    can see WHY delivery is down. Never carries secrets or provider
    credentials.
    """

    def __init__(self, message: str, *, reason: str = "error", channels: list[dict] | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.channels = channels if channels is not None else []


@dataclass(frozen=True)
class OtpIssueResult:
    """Outcome of a successful OTP issuance (issue #74).

    Attributes:
        expires_in: Seconds until the issued code expires.
        channel: The semantic channel that carried the code — ``whatsapp``
            (sent-ok) or ``sms`` (degraded) for real chains, ``console`` /
            ``stub`` in DEBUG. Exposed to the requesting app so it can hint
            "check your messages" on degradation; it is NOT a registration
            signal — the anchor resolution ladder stays non-enumerating.
    """

    expires_in: int
    channel: str


def _http_failure_reason(exc: Exception) -> str:
    """Classify a transport exception without leaking provider detail."""
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int) and not isinstance(status, bool):
        return f"http_{status}"
    return "transport_error"


def _hash_code(phone: str, code: str) -> str:
    """Bind the code to its phone before hashing (code+phone binding)."""
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def _generate_code(length: int = 6) -> str:
    """Cryptographically random numeric code of ``length`` digits."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def _tenant_gym_name(tenant) -> str:
    """Display name used in OTP message copy (never sensitive data)."""
    return getattr(tenant, "name", None) or "FitNation"


class OtpSender(ABC):
    """Delivery abstraction for one OTP channel.

    Concrete senders raise :class:`OtpDeliveryError` on any failure so
    :func:`issue_otp` can fall through to the next channel in the chain.
    """

    name = "abstract"

    @abstractmethod
    def send_otp(self, phone: str, code: str, tenant=None) -> None:
        """Deliver ``code`` to ``phone``.

        Args:
            phone: The member's phone number.
            code: The 6-digit code (never logged at INFO+ by senders).
            tenant: The issuing tenant (gym name for message copy).
        """


class ConsoleOtpSender(OtpSender):
    """Logs the OTP for QA testing (never returned in API responses).

    Dev/staging only — :func:`resolve_otp_senders` never returns it when
    ``DEBUG=False``.
    """

    name = "console"

    def send_otp(self, phone: str, code: str, tenant=None) -> None:
        """Log the code for local QA."""
        logger.info("OTP for %s: %s", phone, code)


class StubOtpSender(OtpSender):
    """Returns the code to the caller — DEBUG/test ONLY (a prod blocker)."""

    name = "stub"
    code: str | None = None

    def send_otp(self, phone: str, code: str, tenant=None) -> None:
        """Capture the code so the DEBUG-only API response can echo it."""
        self.code = code


class WatiOtpSender(OtpSender):
    """Delivers the OTP over WhatsApp via the tenant's own WATI account.

    Business-initiated messages outside the 24h customer-service window must
    use an approved WATI *template*, not ``sendSessionMessage`` (FBOS-011
    correction #10). Tenants store a full session-message URL in
    ``wati_endpoint``; :meth:`template_endpoint` normalizes it to the template
    path so no tenant-facing config migration is needed.
    """

    name = "wati"

    def __init__(self, tenant, *, poster=None) -> None:
        """Bind the sender to one tenant's WATI configuration.

        Args:
            tenant: The tenant whose WATI credentials are used.
            poster: Injectable HTTP post callable (tests).
        """
        self.tenant = tenant
        self.poster = poster or requests.post

    @staticmethod
    def is_configured_for(tenant) -> bool:
        """Whether the tenant has WhatsApp OTP delivery available.

        Args:
            tenant: The tenant to inspect.

        Returns:
            ``True`` when WATI is enabled and an API key is set.
        """
        return bool(tenant is not None and tenant.is_wati_enabled and tenant.wati_api_key)

    @staticmethod
    def template_endpoint(stored_endpoint: str, to_msisdn: str, template_name: str = WATI_OTP_TEMPLATE_NAME) -> str:
        """Derive the WATI template-message URL from the stored endpoint.

        Thin wrapper over
        :func:`apps.notifications.services.channels.wati_template_endpoint`.

        Args:
            stored_endpoint: The tenant's configured WATI URL (either form).
            to_msisdn: Recipient in ``<country_code><number>`` form.
            template_name: The WATI-approved template slug.

        Returns:
            The full template-message URL.
        """
        return wati_template_endpoint(stored_endpoint, to_msisdn, template_name)

    def _under_daily_budget(self) -> bool:
        """Per-tenant WhatsApp OTP budget (protects the gym's WATI wallet).

        Returns:
            ``True`` while today's count is below ``TENANT_WATI_OTP_DAILY_CAP``.
        """
        return _under_whatsapp_daily_budget(self.tenant.pk, self.name)

    def _count_sent(self) -> None:
        """Increment today's per-tenant WATI OTP counter (best-effort)."""
        _count_whatsapp_otp(self.tenant.pk, self.name)

    def send_otp(self, phone: str, code: str, tenant=None) -> None:
        """POST the template message; raise ``OtpDeliveryError`` on any failure.

        Args:
            phone: The member's phone number.
            code: The 6-digit code.
            tenant: Unused (the tenant is bound at construction).
        """
        del tenant
        if not self.is_configured_for(self.tenant):
            raise OtpDeliveryError("WATI is not configured for this tenant", reason="not_configured")
        if not self._under_daily_budget():
            raise OtpDeliveryError("Tenant WATI OTP daily cap reached", reason="daily_cap_reached")

        to = normalize_msisdn(phone, getattr(settings, "OTP_DEFAULT_COUNTRY_CODE", "91"))
        try:
            post_wati_template(
                self.tenant,
                WATI_OTP_TEMPLATE_NAME,
                to,
                [code, _tenant_gym_name(self.tenant), "10"],
                poster=self.poster,
            )
        except Exception as exc:
            raise OtpDeliveryError(f"WATI delivery failed: {exc}", reason=_http_failure_reason(exc)) from exc
        self._count_sent()


def _under_whatsapp_daily_budget(tenant_pk, provider: str) -> bool:
    """Per-tenant per-provider WhatsApp OTP budget (protects the BSP wallet).

    Args:
        tenant_pk: The issuing tenant's id (counter is scoped to it).
        provider: ``wati`` or ``gupshup`` (each wallet counts separately).

    Returns:
        ``True`` while today's count is below ``TENANT_WATI_OTP_DAILY_CAP``.
    """
    from django.core.cache import cache

    cap = int(getattr(settings, "TENANT_WATI_OTP_DAILY_CAP", 200))
    key = f"{provider}-otp:{tenant_pk}:{date.today().isoformat()}"  # noqa: DTZ011 — local-date OTP windows
    try:
        return (cache.get(key) or 0) < cap
    except Exception:  # noqa: BLE001 - fail open to the next channel
        return True


def _count_whatsapp_otp(tenant_pk, provider: str) -> None:
    """Increment today's per-tenant per-provider OTP counter (best-effort).

    Args:
        tenant_pk: The issuing tenant's id.
        provider: ``wati`` or ``gupshup``.
    """
    from django.core.cache import cache

    key = f"{provider}-otp:{tenant_pk}:{date.today().isoformat()}"  # noqa: DTZ011 — local-date OTP windows
    try:
        cache.set(key, (cache.get(key) or 0) + 1, timeout=172800)
    except Exception:  # noqa: BLE001 - accounting must never block delivery
        logger.warning("%s OTP budget counter not updated (cache unavailable)", provider)


class GupshupOtpSender(OtpSender):
    """Delivers the OTP over WhatsApp via the tenant's own Gupshup app (#66).

    The second WhatsApp BSP in the delivery chain. Template shape (issue #85
    realignment): the Gupshup console template is an AUTHENTICATION-category
    template named ``fitnation_otp`` with the strict body — essentially only
    the code variable, no gym name, no extra wording (WhatsApp rejects gym
    names/wording inside Authentication bodies, and the OTP is rejected in
    Utility) — so the send carries ``params=[code]`` and nothing else. Note
    the deliberate divergence from WATI: WATI's same-name template keeps its
    3-variable body ([code, gym_name, ttl]) — its shape predates the category
    rules and must not be broken for WATI tenants.

    All three Gupshup credentials (key, source number, app name) must be
    configured; anything less would fail on the provider side for every send,
    so the chain skips straight past it.

    Because Gupshup 202-acks EVERY ``/msg`` submit (approved template or
    not — issue #73/#74), a send counts as delivered only when the template
    is verified APPROVED in the tenant's app first
    (:func:`apps.notifications.services.channels.gupshup_template_status`);
    unverifiable or unapproved → :class:`OtpDeliveryError` with reason
    ``template_not_approved`` and the chain propagates to SMS instead of
    silently dropping the login code. A 2xx body outside the accepted-status
    family (``provider_error``) fails the leg the same way.
    """

    name = "gupshup"

    def __init__(
        self,
        tenant,
        *,
        poster: Callable[..., Any] | None = None,
        template_getter: Callable[[Any, str], str] | None = None,
    ) -> None:
        """Bind the sender to one tenant's Gupshup configuration.

        Args:
            tenant: The tenant whose Gupshup credentials are used.
            poster: Injectable HTTP post callable (tests).
            template_getter: Injectable approval-status lookup (tests);
                defaults to the channels-module template-list GET.
        """
        self.tenant = tenant
        self.poster = poster or requests.post
        self.template_getter = template_getter

    @staticmethod
    def is_configured_for(tenant) -> bool:
        """Whether the tenant has Gupshup OTP delivery available.

        Args:
            tenant: The tenant to inspect.

        Returns:
            ``True`` when Gupshup is enabled with key, source and app name.
        """
        return gupshup_ready(tenant)

    def _under_daily_budget(self) -> bool:
        """Per-tenant Gupshup OTP budget (own wallet, same cap value)."""
        return _under_whatsapp_daily_budget(self.tenant.pk, self.name)

    def _count_sent(self) -> None:
        """Increment today's per-tenant Gupshup OTP counter (best-effort)."""
        _count_whatsapp_otp(self.tenant.pk, self.name)

    def _template_is_approved(self) -> bool:
        """Whether ``fitnation_otp`` is verifiably APPROVED for this app.

        A verified APPROVED verdict is cached (``GUPSHUP_TEMPLATE_CHECK_TTL``,
        best-effort) so steady-state sends don't pay a template-list GET;
        non-approved and unverifiable verdicts are never cached — approving
        the template in the console flips delivery on the very next request.

        Returns:
            ``True`` only for a live APPROVED status (possibly cached).
        """
        from django.core.cache import cache

        cache_key = f"gupshup-tpl:{self.tenant.pk}:{GUPSHUP_OTP_TEMPLATE_NAME}"
        try:
            if cache.get(cache_key):
                return True
        except Exception:  # noqa: BLE001 - cache trouble must not block sends
            pass
        if self.template_getter is not None:
            status = self.template_getter(self.tenant, GUPSHUP_OTP_TEMPLATE_NAME)
        else:
            status = gupshup_template_status(self.tenant, GUPSHUP_OTP_TEMPLATE_NAME)
        if str(status).strip().upper() != "APPROVED":
            return False
        with contextlib.suppress(Exception):  # accounting must never block delivery
            cache.set(cache_key, True, timeout=getattr(settings, "GUPSHUP_TEMPLATE_CHECK_TTL", 1800))
        return True

    def send_otp(self, phone: str, code: str, tenant=None) -> None:
        """POST the template message; raise ``OtpDeliveryError`` on any failure.

        Any failure here propagates the chain to the next channel (SMS) —
        including the approved-template gate's ``template_not_approved``.

        Args:
            phone: The member's phone number.
            code: The 6-digit code.
            tenant: Unused (the tenant is bound at construction).
        """
        del tenant
        if not self.is_configured_for(self.tenant):
            raise OtpDeliveryError("Gupshup is not configured for this tenant", reason="not_configured")
        if not self._under_daily_budget():
            raise OtpDeliveryError("Tenant Gupshup OTP daily cap reached", reason="daily_cap_reached")
        if not self._template_is_approved():
            logger.warning(
                "Gupshup OTP template %s is not APPROVED for tenant %s — skipping to the next channel",
                GUPSHUP_OTP_TEMPLATE_NAME,
                getattr(self.tenant, "pk", None),
            )
            raise OtpDeliveryError(
                f"Gupshup template '{GUPSHUP_OTP_TEMPLATE_NAME}' is not approved for this app — "
                "the provider accepts but would never deliver the message",
                reason="template_not_approved",
            )

        to = normalize_msisdn(phone, getattr(settings, "OTP_DEFAULT_COUNTRY_CODE", "91"))
        try:
            response = post_gupshup_template(
                self.tenant,
                GUPSHUP_OTP_TEMPLATE_NAME,
                to,
                [code],  # Authentication-category body: the code is its only variable (#85)
                poster=self.poster,
            )
        except Exception as exc:
            raise OtpDeliveryError(f"Gupshup delivery failed: {exc}", reason=_http_failure_reason(exc)) from exc
        try:
            body = response.json() if hasattr(response, "json") else {}
        except ValueError:  # non-JSON 2xx body — trust the HTTP success
            body = {}
        status_word = str(body.get("status", "")).strip().lower() if isinstance(body, dict) else ""
        if status_word and status_word not in GUPSHUP_ACCEPTED_STATUS:
            raise OtpDeliveryError(
                f"Gupshup did not accept the template message: {body.get('message') or status_word}",
                reason="provider_error",
            )
        self._count_sent()


class Msg91OtpSender(OtpSender):
    """SMS fallback via MSG91's DLT flow API (platform-level account).

    WhatsApp is already per-tenant via WATI; the fallback needs carrier-grade
    SMS with DLT registration for India (FBOS-011 §4.2). Env contract:
    ``SMS_PROVIDER=msg91``, ``MSG91_AUTH_KEY``, ``MSG91_TEMPLATE_ID``
    (``MSG91_SENDER_ID`` is the DLT header baked into the template).

    DLT template text (variables locked to DLT rules):
    ``{#var#} is your GYM FitNation app login code. Valid for 10 minutes. Do not share.``
    with recipient variables ``OTP`` and ``GYM``.
    """

    name = "sms"

    def __init__(self, *, poster=None) -> None:
        """Allow the HTTP transport to be injected (tests).

        Args:
            poster: Injectable HTTP post callable.
        """
        self.poster = poster or requests.post

    @staticmethod
    def is_configured() -> bool:
        """Whether the platform SMS credentials are present.

        Returns:
            ``True`` when ``SMS_PROVIDER=msg91`` with auth key + template id.
        """
        return (
            getattr(settings, "SMS_PROVIDER", "msg91") == "msg91"
            and bool(getattr(settings, "MSG91_AUTH_KEY", ""))
            and bool(getattr(settings, "MSG91_TEMPLATE_ID", ""))
        )

    def send_otp(self, phone: str, code: str, tenant=None) -> None:
        """POST the flow API; raise ``OtpDeliveryError`` on any failure.

        Args:
            phone: The member's phone number.
            code: The 6-digit code.
            tenant: Issuing tenant (gym name for the ``GYM`` variable).
        """
        if not self.is_configured():
            raise OtpDeliveryError("SMS delivery is not configured", reason="not_configured")
        recipient = {
            "mobiles": normalize_msisdn(phone, getattr(settings, "OTP_DEFAULT_COUNTRY_CODE", "91")),
            "OTP": code,
            "GYM": _tenant_gym_name(tenant),
        }
        try:
            response = post_msg91_flow(
                [recipient],
                settings.MSG91_TEMPLATE_ID,
                poster=self.poster,
            )
        except Exception as exc:
            raise OtpDeliveryError(f"SMS delivery failed: {exc}", reason=_http_failure_reason(exc)) from exc
        try:
            body = response.json() if hasattr(response, "json") else {}
        except ValueError:  # non-JSON 2xx body — trust the HTTP success
            body = {}
        if isinstance(body, dict):
            msg_type = str(body.get("type", "")).strip().lower()
            if msg_type and msg_type != "success":
                # e.g. {"type": "error", "title": "Insufficient Balance"} can
                # ride HTTP 2xx — that is a carrier rejection, not delivery.
                raise OtpDeliveryError(
                    f"SMS provider rejected the send: {body.get('title') or body.get('message') or msg_type}",
                    reason="provider_error",
                )


def resolve_otp_senders(tenant) -> list[OtpSender]:
    """Resolve the ordered delivery chain for a tenant (FBOS-011 §4, #66).

    ``OTP_SENDER`` values:

    - ``auto`` (default): DEBUG → console; production → the tenant's real
      chain, WATI (when enabled + keyed) → Gupshup (when fully configured)
      → MSG91 SMS.
    - ``wati`` / ``gupshup`` / ``sms``: force exactly that leg (empty chain
      → loud 503 when unconfigured).
    - ``console``: dev convenience; ignored with a warning in production
      (the real chain resolves instead — codes can never silently drop to
      logs in prod).
    - ``stub``: DEBUG only; raises :class:`ImproperlyConfigured` otherwise
      (returning codes in API responses must be impossible in prod).

    Args:
        tenant: The issuing tenant (selects the WhatsApp legs).

    Returns:
        The ordered sender chain (possibly empty → callers fail loudly).

    Raises:
        ImproperlyConfigured: When ``stub`` is selected with ``DEBUG=False``.
    """
    configured = getattr(settings, "OTP_SENDER", "auto")
    if configured == "stub":
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                'OTP_SENDER="stub" returns OTP codes in API responses and is only allowed when DEBUG=True.'
            )
        return [StubOtpSender()]
    if configured == "console":
        if settings.DEBUG:
            return [ConsoleOtpSender()]
        logger.warning('OTP_SENDER="console" ignored because DEBUG=False — resolving the production chain.')
        configured = "auto"
    if configured == "wati":
        return [WatiOtpSender(tenant)] if WatiOtpSender.is_configured_for(tenant) else []
    if configured == "gupshup":
        return [GupshupOtpSender(tenant)] if GupshupOtpSender.is_configured_for(tenant) else []
    if configured == "sms":
        return [Msg91OtpSender()] if Msg91OtpSender.is_configured() else []
    # auto
    if settings.DEBUG:
        return [ConsoleOtpSender()]
    chain: list[OtpSender] = []
    if WatiOtpSender.is_configured_for(tenant):
        chain.append(WatiOtpSender(tenant))
    if GupshupOtpSender.is_configured_for(tenant):
        chain.append(GupshupOtpSender(tenant))
    if Msg91OtpSender.is_configured():
        chain.append(Msg91OtpSender())
    return chain


def channel_diagnostics(tenant) -> list[dict]:
    """Per-leg configuration status for delivery-failure reporting (no secrets).

    Args:
        tenant: The issuing tenant (selects the WhatsApp legs).

    Returns:
        One ``{"channel", "reason"}`` dict per real leg — ``configured`` or
        ``not_configured`` — in chain order (WATI, Gupshup, then SMS).
    """
    return [
        {
            "channel": "wati",
            "reason": "configured" if WatiOtpSender.is_configured_for(tenant) else "not_configured",
        },
        {
            "channel": "gupshup",
            "reason": "configured" if GupshupOtpSender.is_configured_for(tenant) else "not_configured",
        },
        {
            "channel": "sms",
            "reason": "configured" if Msg91OtpSender.is_configured() else "not_configured",
        },
    ]


def get_otp_sender():
    """Resolve the configured single dev/test sender (console | stub).

    Retained for the DEBUG settings surface; production code resolves the
    chain with :func:`resolve_otp_senders` instead.

    Returns:
        A :class:`ConsoleOtpSender` or :class:`StubOtpSender`.

    Raises:
        ImproperlyConfigured: For ``stub`` outside DEBUG, or any
            production chain value (``auto``/``wati``/``sms``).
    """
    backend = getattr(settings, "OTP_SENDER", "console")
    if backend == "console":
        return ConsoleOtpSender()
    if backend == "stub":
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                'OTP_SENDER="stub" returns OTP codes in API responses and is only allowed when DEBUG=True.'
            )
        return StubOtpSender()
    raise ImproperlyConfigured(f"Unknown OTP_SENDER: {backend} — use resolve_otp_senders() for real delivery chains.")


def _log_otp_delivery(tenant, channel: str, sent: bool, error: str) -> None:
    """Record a real-channel OTP delivery attempt in the audit trail.

    Content NEVER contains the code (FBOS-011 §10.3) — channel metadata only.
    Console/stub attempts are dev-only and are not logged (noise). The row's
    ``channel`` is semantic (whatsapp | sms) and ``provider`` names the BSP
    that carried it (issue #66).

    Args:
        tenant: The issuing tenant (rows are tenant-scoped; skipped if None).
        channel: Sender name that attempted delivery (wati | gupshup | sms).
        sent: Whether delivery succeeded.
        error: Transport error text on failure.
    """
    from apps.notifications.models import NotificationLog

    if tenant is None or channel in {"console", "stub"}:
        return
    semantic_channel, provider = OTP_CHANNEL_BY_SENDER.get(channel, (channel, ""))
    NotificationLog.objects.create(
        tenant=tenant,
        customer=None,
        notification_type=NotificationLog.NotificationType.OTP,
        status=NotificationLog.Status.SENT if sent else NotificationLog.Status.FAILED,
        channel=semantic_channel,
        provider=provider,
        content=f"OTP issued via {channel}",
        error_message=error or "",
    )


def issue_otp(
    phone: str,
    tenant,
    ip: str | None = None,
    sender: OtpSender | list[OtpSender] | None = None,
) -> OtpIssueResult:
    """Generate, store and deliver an OTP for ``phone``.

    Enforces the resend cooldown and the per-phone + per-IP daily caps, then
    walks the delivery chain — the first sender that doesn't raise wins; all
    raising → :class:`OtpDeliveryError` (the view returns a loud 503). Every
    real-channel attempt (failed legs included, issue #74) is audited in
    ``NotificationLog`` so an operator can see the WhatsApp leg's failure
    that pushed a delivery onto SMS.

    Args:
        phone: Phone number used for OTP login.
        tenant: The issuing tenant (anchor-resolved before this call).
        ip: Requesting IP for the per-IP daily cap.
        sender: Explicit sender or chain (tests / dev stub); ``None`` resolves
            :func:`resolve_otp_senders`.

    Returns:
        The :class:`OtpIssueResult` (ttl + the channel that delivered).

    Raises:
        OtpRateLimited: A rate limit was exceeded.
        OtpError: The resend cooldown is active.
        OtpDeliveryError: No channel delivered the code.
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

    if sender is None:
        senders: list[OtpSender] = resolve_otp_senders(tenant)
    elif isinstance(sender, list):
        senders = sender
    else:
        senders = [sender]

    if not senders:
        logger.critical("OTP delivery misconfigured: no channel available for tenant %s", getattr(tenant, "pk", None))
        _log_otp_delivery(tenant, "none", False, "no delivery channel configured")
        raise OtpDeliveryError(
            "No OTP delivery channel is configured.",
            reason="not_configured",
            channels=channel_diagnostics(tenant),
        )

    last_error: Exception | None = None
    failures: list[dict] = []
    for chain_sender in senders:
        try:
            chain_sender.send_otp(phone, code, tenant=tenant)
        except OtpDeliveryError as exc:
            last_error = exc
            failures.append({"channel": chain_sender.name, "reason": exc.reason})
            logger.warning("OTP delivery via %s failed: %s", chain_sender.name, exc)
            # Issue #74: audit EVERY failed leg as it happens — a degraded
            # delivery (WhatsApp leg failed, SMS carried) must show both rows.
            _log_otp_delivery(tenant, chain_sender.name, False, str(exc))
            continue
        _log_otp_delivery(tenant, chain_sender.name, True, "")
        semantic_channel = OTP_CHANNEL_BY_SENDER.get(chain_sender.name, (chain_sender.name, ""))[0]
        return OtpIssueResult(expires_in=ttl, channel=semantic_channel)

    logger.critical(
        "OTP delivery failed for %s via all channels (%s): %s",
        phone,
        [s.name for s in senders],
        last_error,
    )
    raise OtpDeliveryError(
        str(last_error) if last_error else "OTP delivery failed.",
        reason="all_channels_failed",
        channels=failures,
    )


def verify_otp(phone: str, code: str, tenant=None) -> OtpCode:
    """Verify ``code`` for ``phone``.

    Enforces phone↔code binding (optionally scoped to the resolved tenant),
    the 10-minute expiry, the max 5 attempts and single-use consumption.

    Args:
        phone: Phone number used for OTP login.
        code: The candidate 6-digit code.
        tenant: When given, only codes issued for this tenant verify.

    Returns:
        The consumed :class:`~apps.users.models.OtpCode` row.

    Raises:
        OtpError: No active code, expired, exhausted attempts, or mismatch.
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
