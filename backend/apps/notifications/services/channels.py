"""Shared delivery-channel transport helpers (FBOS-011 §4/§5).

Low-level, injectable HTTP plumbing for the two real channels — WATI
WhatsApp template messages (per-tenant config) and the MSG91 DLT flow API
(platform config). No business logic and no DB access here; senders and the
invite service wrap these so the HTTP contracts live in exactly one place.
"""

from __future__ import annotations

from typing import Any, Callable

from django.conf import settings

import requests

WATI_SESSION_PATH = "/sendSessionMessage"
WATI_TEMPLATE_PATH = "/api/v1/sendTemplateMessage"
DEFAULT_WATI_BASE = "https://api.wati.io"
MSG91_FLOW_URL = "https://control.msg91.com/api/v5/flow/"


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
