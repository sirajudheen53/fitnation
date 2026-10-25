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
# Template-management list API (issue #74, transport fixed in #85): the only
# synchronous place where Gupshup reveals whether a template is APPROVED — its
# /msg send API 202-acks any submit, approved or not, so delivery gates have
# to ask here first. The URL carries an ``{appname}`` placeholder filled with
# the tenant's Gupshup app name. Live-found on 2026-10-25: bare
# ``/sm/api/v1/templates`` 404s, and the per-app list endpoint REJECTS the
# app's own api key (401 "Portal User Not Found With APIKey") — it wants a
# PORTAL account key (``GUPSHUP_PORTAL_API_KEY``); without one the status
# gate falls back to the ``GUPSHUP_APPROVED_TEMPLATES`` env allow-list.
GUPSHUP_TEMPLATE_LIST_URL = "https://api.gupshup.io/sm/api/v1/template/list/{appname}"

# Portal (platform-level) API key for GUPSHUP_TEMPLATE_LIST_URL (issue #85).
GUPSHUP_PORTAL_API_KEY = ""
# Comma-separated template names verifiably APPROVED in Gupshup (issue #85).
# Ops sets this after console approval; consulted when the portal-key live
# check cannot run (no key, or the live endpoint still refuses it).
GUPSHUP_APPROVED_TEMPLATES = ""

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

# Sync /msg bodies that mean Gupshup ACCEPTED the submit (issue #74). An
# accepted-anything response never proves delivery — an unapproved template
# is 202-acked ("submitted") and silently dropped upstream — so senders that
# must guarantee delivery gate on template approval instead of trusting this.
GUPSHUP_ACCEPTED_STATUS = {"submitted", "success", "accepted"}


def parse_gupshup_template_status(payload: Any, template_name: str) -> str:
    """Extract one template's approval status from a template-list payload.

    Pure helper (tests / reuse): tolerant across every list shape Gupshup has
    documented or shipped (issue #85) — the wrapper
    ``{"templates": [{…}, …]}``, a bare list, and entries naming the template
    either ``name`` or ``elementName`` with the state in ``status`` or
    ``templateStatus``. A name may appear once per language revision — any
    APPROVED entry wins; otherwise the first non-empty status is reported.

    Args:
        payload: The parsed JSON body of a Gupshup template-list response.
        template_name: The template slug to look up.

    Returns:
        The normalized status word (e.g. ``APPROVED``, ``PENDING``), or ""
        when the name is absent or the payload is unusable.
    """
    templates = payload.get("templates") if isinstance(payload, dict) else payload
    if not isinstance(templates, list):
        return ""
    first_status = ""
    for entry in templates:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or entry.get("elementName") or "")
        if name != template_name:
            continue
        status = str(entry.get("status") or entry.get("templateStatus") or "").strip().upper()
        if not status:
            continue
        if status == "APPROVED":
            return status
        if not first_status:
            first_status = status
    return first_status


def approved_template_names_from_env() -> frozenset[str]:
    """Template names ops has confirmed APPROVED in Gupshup (issue #85).

    Parsed from the ``GUPSHUP_APPROVED_TEMPLATES`` env (comma-separated;
    whitespace and case tolerated). Used by the delivery gate when the live
    template-list check cannot run — see :func:`gupshup_template_status`.

    Returns:
        The upper-cased allow-list of template slugs (empty when unset).
    """
    raw = str(getattr(settings, "GUPSHUP_APPROVED_TEMPLATES", "") or "")
    return frozenset(part.strip().upper() for part in raw.split(",") if part.strip())


def _live_template_status(
    url: str,
    api_key: str,
    template_name: str,
    getter: Callable[..., Any] | None,
) -> str | None:
    """One live template-list GET against Gupshup (issue #85).

    Contract: ``GET <url>`` with the ``apikey`` header. The parse verdict is
    returned whenever the body carries a usable template list — even when the
    verdict is negative (name absent / PENDING): a working live check is
    authoritative, so the env allow-list must not override it. Transport, HTTP
    or unusable-payload trouble yields ``None`` = "did not get a verdict",
    which callers turn into the next gate in order.

    Args:
        url: The template-list URL (``{appname}`` already substituted).
        api_key: The API key header value (portal key for the list endpoint).
        template_name: The platform template slug to look up.
        getter: Injectable HTTP get callable (tests).

    Returns:
        The normalized status word, or ``None`` when unverifiable.
    """
    get = getter or requests.get
    try:
        response = get(url, headers={"apikey": api_key}, timeout=getattr(settings, "GUPSHUP_TIMEOUT", 10))
        response.raise_for_status()
        payload = response.json()
    except Exception:  # noqa: BLE001 - an unusable status API is "no verdict"
        return None
    templates = payload.get("templates") if isinstance(payload, dict) else payload
    if not isinstance(templates, list):
        return None
    return parse_gupshup_template_status(payload, template_name)


def gupshup_template_status(
    tenant,
    template_name: str,
    *,
    getter: Callable[..., Any] | None = None,
) -> str:
    """The tenant's Gupshup approval status for one template name (#74, #85).

    Gate order (fail closed):

    1. Portal-key live check — the list endpoint only answers a PORTAL
       account key (the app's own api key gets 401 "Portal User Not Found
       With APIKey"), so ``GUPSHUP_PORTAL_API_KEY`` drives a real GET of
       ``GUPSHUP_TEMPLATE_LIST_URL`` with ``{appname}`` filled from the
       tenant's Gupshup app name. A usable response decides outright:
       ``APPROVED`` or the raw non-approved word (PENDING/REJECTED/absent).
    2. Approved-names env — when the live check cannot run (no portal key,
       or the endpoint still refuses/errors), names listed in
       ``GUPSHUP_APPROVED_TEMPLATES`` are treated as APPROVED (ops flips this
       on after console approval).
    3. Fail closed — otherwise "" (callers that must guarantee delivery treat
       "" as "cannot prove approval" and fall through rather than trusting a
       202 ack).

    Cache semantics are untouched and live with the senders: only verified
    APPROVED verdicts get cached, negatives are never cached.

    Args:
        tenant: The tenant whose Gupshup app name scopes the template list.
        template_name: The platform template slug to look up.
        getter: Injectable HTTP get callable (tests).

    Returns:
        The normalized status word for the template, "" when unverifiable.
    """
    base = str(getattr(settings, "GUPSHUP_TEMPLATE_LIST_URL", GUPSHUP_TEMPLATE_LIST_URL)).strip().rstrip("/")
    appname = (getattr(tenant, "gupshup_app_name", "") or "").strip()
    url = base.replace("{appname}", appname)
    portal_key = str(getattr(settings, "GUPSHUP_PORTAL_API_KEY", "") or "").strip()
    if portal_key:
        verdict = _live_template_status(url, portal_key, template_name, getter)
        if verdict is not None:
            return verdict
    if template_name.upper() in approved_template_names_from_env():
        return "APPROVED"
    return ""


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
