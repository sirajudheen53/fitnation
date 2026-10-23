"""Shared delivery-channel transport helpers (FBOS-011 §4/§5).

Low-level, injectable HTTP plumbing for the real channels — WATI and Gupshup
WhatsApp template/session messages (per-tenant config) and the MSG91 DLT flow
API (platform config). No business logic and no DB access here; senders, the
invite service and the channel router wrap these so the HTTP contracts live
in exactly one place.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from django.conf import settings

import requests

WATI_SESSION_PATH = "/sendSessionMessage"
WATI_TEMPLATE_PATH = "/api/v1/sendTemplateMessage"
DEFAULT_WATI_BASE = "https://api.wati.io"
MSG91_FLOW_URL = "https://control.msg91.com/api/v5/flow/"
GUPSHUP_MSG_URL = "https://api.gupshup.io/wa/api/v1/msg"

# Semantic channels (NotificationLog.channel) and the providers
# (NotificationLog.provider) that carry them (issue #66). Live here so the
# transport module, the policy router and the send services share one source
# without import cycles.
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_SMS = "sms"
CHANNEL_EMAIL = "email"

PROVIDER_WATI = "wati"
PROVIDER_GUPSHUP = "gupshup"
PROVIDER_MSG91 = "msg91"
PROVIDER_SENDGRID = "sendgrid"

# OTP audit rows used the provider name as ``channel`` before provider existed
# (FBOS-011); this map keeps those rows' channel semantic while naming the BSP.
OTP_CHANNEL_BY_SENDER: dict[str, tuple[str, str]] = {
    PROVIDER_WATI: (CHANNEL_WHATSAPP, PROVIDER_WATI),
    PROVIDER_GUPSHUP: (CHANNEL_WHATSAPP, PROVIDER_GUPSHUP),
    "sms": (CHANNEL_SMS, PROVIDER_MSG91),
}


def normalize_msisdn(phone: str, country_code: str = "91") -> str:
    """Normalize a stored phone to the ``<country_code><number>`` form.

    India-facing carriers (WATI ``whatsappNumber``, MSG91 ``mobiles``) want no
    leading ``+`` and an explicit country code. A bare 10-digit number gets
    the default country code prefixed; anything else is passed through with
    formatting stripped.

    Args:
        phone: The stored phone number (may be ``+91…`` or bare).
        country_code: Default country code for bare numbers.

    Returns:
        Digits only, country code included.
    """
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits.startswith(country_code) and len(digits) == 10:
        digits = f"{country_code}{digits}"
    return digits


def wati_template_endpoint(stored_endpoint: str, to_msisdn: str, template_name: str) -> str:
    """Derive the WATI template-message URL from the tenant's stored endpoint.

    Tenants store a full session-message URL (``…/api/v1/sendSessionMessage``,
    the pre-existing config shape) or a bare account base; business-initiated
    messages must use the template path instead (FBOS-011 correction #10).
    Strips a trailing ``/sendSessionMessage`` and any ``/api/v1`` prefix it
    exposes (the template path re-appends it), then appends
    ``/api/v1/sendTemplateMessage/{template}?whatsappNumber={to}`` — so both
    ``https://api.wati.io/api/v1/sendSessionMessage`` and
    ``https://api.wati.io`` normalize to the same template URL.

    Args:
        stored_endpoint: The tenant's configured WATI URL (either form).
        to_msisdn: Recipient in ``<country_code><number>`` form.
        template_name: The WATI-approved template slug.

    Returns:
        The full template-message URL.
    """
    base = (stored_endpoint or f"{DEFAULT_WATI_BASE}{WATI_SESSION_PATH}").strip().rstrip("/")
    if base.lower().endswith(WATI_SESSION_PATH.lower()):
        base = base[: -len(WATI_SESSION_PATH)].rstrip("/")
    if base.lower().endswith("/api/v1"):
        base = base[: -len("/api/v1")].rstrip("/")
    return f"{base}{WATI_TEMPLATE_PATH}/{template_name}?whatsappNumber={to_msisdn}"


def post_wati_template(
    tenant,
    template_name: str,
    to_msisdn: str,
    template_params: list[str],
    *,
    poster: Callable[..., Any] | None = None,
) -> requests.Response:
    """POST an approved WATI template message with the tenant's credentials.

    Args:
        tenant: The tenant whose WATI endpoint + API key are used.
        template_name: The WATI-approved template slug.
        to_msisdn: Recipient in ``<country_code><number>`` form.
        template_params: Positional ``{{1}}…{{n}}`` variables for the template.
        poster: Injectable HTTP post callable (tests).

    Returns:
        The HTTP response (2xx on success; raise_for_status enforced here).

    Raises:
        requests.RequestException: On any transport/HTTP failure.
    """
    url = wati_template_endpoint(tenant.wati_endpoint, to_msisdn, template_name)
    post = poster or requests.post
    response = post(
        url,
        json={"templateParams": template_params},
        headers={"Authorization": tenant.wati_api_key},
        timeout=getattr(settings, "WATI_TIMEOUT", 10),
    )
    response.raise_for_status()
    return response


def post_msg91_flow(
    recipients: list[dict[str, Any]],
    template_id: str,
    *,
    auth_key: str | None = None,
    poster: Callable[..., Any] | None = None,
) -> requests.Response:
    """POST an MSG91 DLT flow (template) message.

    Contract (FBOS-011 §4.2): ``POST https://control.msg91.com/api/v5/flow/``
    with the ``authkey`` header, ``{"template_id", "short_url": "0",
    "recipients": [{...variable map per recipient}]}``.

    Args:
        recipients: One variable-map dict per recipient (must include
            ``mobiles``).
        template_id: The DLT-registered flow template id.
        auth_key: Platform MSG91 auth key (defaults to the settings value).
        poster: Injectable HTTP post callable (tests).

    Returns:
        The HTTP response (2xx on success; raise_for_status enforced here).

    Raises:
        requests.RequestException: On any transport/HTTP failure.
    """
    post = poster or requests.post
    response = post(
        MSG91_FLOW_URL,
        json={
            "template_id": template_id,
            "short_url": "0",
            "recipients": recipients,
        },
        headers={"authkey": auth_key if auth_key is not None else getattr(settings, "MSG91_AUTH_KEY", "")},
        timeout=getattr(settings, "MSG91_TIMEOUT", 10),
    )
    response.raise_for_status()
    return response


def post_gupshup_message(
    tenant,
    to_msisdn: str,
    message: dict[str, Any],
    *,
    poster: Callable[..., Any] | None = None,
) -> requests.Response:
    """POST one WhatsApp message to the tenant's Gupshup app (issue #66).

    Contract: ``POST https://api.gupshup.io/wa/api/v1/msg`` with the
    ``apikey`` header and a form-encoded body — ``channel=whatsapp``,
    ``source`` (the gym's WhatsApp number), ``src.name`` (the Gupshup app),
    ``destination`` (normalized msisdn) and ``message`` (a JSON string; the
    template form is ``{"type": "template", "name": …, "params": […]}``,
    session-window text is ``{"type": "text", "text": …}``).

    Args:
        tenant: The tenant whose Gupshup key/source/app name are used.
        to_msisdn: Recipient in ``<country_code><number>`` form.
        message: The Gupshup ``message`` payload (encoded as a JSON string).
        poster: Injectable HTTP post callable (tests).

    Returns:
        The HTTP response (2xx on success; raise_for_status enforced here).

    Raises:
        requests.RequestException: On any transport/HTTP failure.
    """
    post = poster or requests.post
    response = post(
        GUPSHUP_MSG_URL,
        data={
            "channel": "whatsapp",
            "source": tenant.gupshup_source,
            "src.name": tenant.gupshup_app_name,
            "destination": to_msisdn,
            "message": json.dumps(message, separators=(",", ":")),
        },
        headers={"apikey": tenant.gupshup_api_key},
        timeout=getattr(settings, "GUPSHUP_TIMEOUT", 10),
    )
    response.raise_for_status()
    return response


def post_gupshup_template(
    tenant,
    template_name: str,
    to_msisdn: str,
    template_params: list[str],
    *,
    poster: Callable[..., Any] | None = None,
) -> requests.Response:
    """POST an approved Gupshup WhatsApp template message.

    Thin shape wrapper over :func:`post_gupshup_message` — the template slug
    is the same platform-wide name approved per tenant (mirrors the WATI
    convention, so ``fitnation_app_invite``/``fitnation_otp`` work in both
    consoles).

    Args:
        tenant: The tenant whose Gupshup credentials are used.
        template_name: The Gupshup-approved template slug.
        to_msisdn: Recipient in ``<country_code><number>`` form.
        template_params: Positional ``{{1}}…{{n}}`` variables for the template.
        poster: Injectable HTTP post callable (tests).

    Returns:
        The HTTP response (2xx on success; raise_for_status enforced here).

    Raises:
        requests.RequestException: On any transport/HTTP failure.
    """
    return post_gupshup_message(
        tenant,
        to_msisdn,
        {"type": "template", "name": template_name, "params": template_params},
        poster=poster,
    )


def post_gupshup_text(
    tenant,
    to_msisdn: str,
    text: str,
    *,
    poster: Callable[..., Any] | None = None,
) -> requests.Response:
    """POST a session-window WhatsApp text message via Gupshup.

    The Gupshup equivalent of the WATI ``sendSessionMessage`` freeform send
    used by :func:`apps.notifications.services.wati_service.send_notification`
    for its notification types — outside the 24h customer-service window the
    provider rejects it, exactly like WATI would.

    Args:
        tenant: The tenant whose Gupshup credentials are used.
        to_msisdn: Recipient in ``<country_code><number>`` form.
        text: The rendered message text.
        poster: Injectable HTTP post callable (tests).

    Returns:
        The HTTP response (2xx on success; raise_for_status enforced here).

    Raises:
        requests.RequestException: On any transport/HTTP failure.
    """
    return post_gupshup_message(tenant, to_msisdn, {"type": "text", "text": text}, poster=poster)
