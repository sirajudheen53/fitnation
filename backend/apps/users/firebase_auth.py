"""Firebase ID-token verification for the customer-app phone login (FBOS-011 §3).

The Flutter app signs members in with Firebase phone OTP inside the mobile
app's own Firebase project (``yougetfitwithus``) and exchanges the resulting
ID token for an FBOS session at ``POST /api/v1/auth/firebase/``. This module
is the only Firebase-aware piece: config is env-driven and fails LOUD (the
OTP codebase's ImproperlyConfigured style — a half-wired verifier must fail
closed, never silently degrade), and every token verdict maps to exactly one
HTTP class at the view layer:

* :class:`FirebaseTokenError` — the token is invalid/expired/unverifiable
  (bad signature, wrong audience/project, no ``phone_number`` claim) → 401.
* :class:`FirebaseVerifierUnavailableError` — the verifier broke at runtime
  (transport/backend errors while fetching public certs, backend errors) → 503.
* :class:`django.core.exceptions.ImproperlyConfigured` — credentials or
  project id absent/unusable → the view fails closed with a loud 503 that
  names the misconfiguration after CRITICAL logging (ops action).
* :class:`FirebaseRateLimited` — the per-IP cap on FAILED verifications → 429.

``firebase-admin`` is imported lazily inside :func:`_initialize_app` /
:func:`firebase_verify_phone` so a botched deploy without the package cannot
sink every other endpoint at import time — only Firebase logins would 503.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# Module-level cache of the ONE Admin SDK app the SDK lets us register (the
# SDK itself is global); reset_firebase_app() re-arms it for tests/settings.
_firebase_app: Any = None


class FirebaseTokenError(Exception):
    """The presented Firebase ID token is invalid/expired/unverifiable (→ 401)."""


class FirebaseVerifierUnavailableError(Exception):
    """The verifier failed at runtime (transport/backend problem) → 503."""


class FirebaseRateLimited(Exception):
    """The per-IP cap on failed verifications was exceeded (→ 429)."""


def _resolve_credential(fb_credentials):
    """Build the Admin-SDK credential from the env contract — or fail loud.

    Precedence: ``FIREBASE_CREDENTIALS`` (either a PATH to the service-account
    JSON or the JSON CONTENT itself — the latter is the Secret-Manager-style
    env injection used for DATABASE_URL/SENDGRID_API_KEY on Cloud Run), then
    ``GOOGLE_APPLICATION_CREDENTIALS`` (ADC file path). Deliberately NO
    metadata-server ADC guesswork: a half-wired deploy must fail closed, not
    happily pass the WRONG project's tokens through.

    Returns:
        A Firebase Admin credential object.

    Raises:
        ImproperlyConfigured: When no credential source is usable (missing
            file, invalid JSON, or nothing configured at all).
    """
    configured = str(getattr(settings, "FIREBASE_CREDENTIALS", "") or "").strip()
    if configured:
        if configured.startswith("{"):
            # Inline service-account JSON (Cloud Run secret injection).
            try:
                info = json.loads(configured)
            except (ValueError, TypeError) as exc:
                raise ImproperlyConfigured(
                    "FIREBASE_CREDENTIALS holds neither a service-account file path nor valid JSON."
                ) from exc
            try:
                return fb_credentials.Certificate(info)
            except (ValueError, TypeError) as exc:
                raise ImproperlyConfigured(f"FIREBASE_CREDENTIALS JSON is not a valid service account: {exc}") from exc
        path = Path(configured)
        if not path.is_file():
            raise ImproperlyConfigured(f"FIREBASE_CREDENTIALS points to a missing service-account file: {configured}")
        return fb_credentials.Certificate(str(path))

    adc_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if adc_path:
        path = Path(adc_path)
        if not path.is_file():
            raise ImproperlyConfigured(
                f"GOOGLE_APPLICATION_CREDENTIALS points to a missing credential file: {adc_path}"
            )
        return fb_credentials.ApplicationDefault()

    raise ImproperlyConfigured(
        "No Firebase credentials configured — set FIREBASE_CREDENTIALS (service-account JSON path or JSON content) "
        "or GOOGLE_APPLICATION_CREDENTIALS (ADC file path); the phone-auth endpoint fails closed otherwise."
    )


def _initialize_app():
    """Register the (single) Firebase Admin app from settings.

    Returns:
        The initialized ``firebase_admin.App``.

    Raises:
        ImproperlyConfigured: For an empty project id or unusable credentials.
    """
    import firebase_admin
    from firebase_admin import credentials as fb_credentials

    project_id = str(getattr(settings, "FIREBASE_PROJECT_ID", "") or "").strip()
    if not project_id:
        raise ImproperlyConfigured(
            "FIREBASE_PROJECT_ID is empty — set it to the mobile app's Firebase project; "
            "ID-token audience checks use it."
        )
    # Named app: an unrelated firebase_admin default-app elsewhere can never
    # collide; project id is forced explicitly (ADC-on-Cloud-Run picks up the
    # HOST project, not the mobile app's Firebase project).
    return firebase_admin.initialize_app(
        _resolve_credential(fb_credentials),
        {"projectId": project_id},
        name="fbos-firebase-auth",
    )


def get_firebase_app():
    """The cached Admin SDK app, initialized on first use (fail loud).

    Raises:
        ImproperlyConfigured: When credentials/project are missing or unusable.
    """
    global _firebase_app
    if _firebase_app is None:
        _firebase_app = _initialize_app()
    return _firebase_app


def reset_firebase_app() -> None:
    """Drop the cached Admin SDK app (tests re-arm settings between cases)."""
    global _firebase_app
    _firebase_app = None
    import contextlib

    with contextlib.suppress(Exception):  # best-effort: nothing registered yet → keep going
        import firebase_admin

        firebase_admin.delete_app(firebase_admin.get_app(name="fbos-firebase-auth"))


def firebase_verify_phone(id_token: str) -> str:
    """Verify a Firebase ID token and return its E.164 phone number.

    Firebase's ``phone_number`` claim is already canonical E.164 (``+cc…``) —
    the exact format the OTP identity convergence keys on — so it is trusted
    as-is (no re-formatting, no country-code guesses).

    Args:
        id_token: The mobile app's Firebase ID token.

    Returns:
        The verified phone number in E.164 (e.g. ``+919876543210``).

    Raises:
        FirebaseTokenError: The token is invalid/expired/unverifiable, or
            carries no ``phone_number`` claim (only phone-auth logins converge
            an FBOS customer identity).
        FirebaseVerifierUnavailableError: The verifier broke at runtime
            (cert-fetch transport errors, Firebase backend errors).
        ImproperlyConfigured: Credentials/project missing or unusable.
    """
    from firebase_admin import auth as fb_auth
    from firebase_admin import exceptions as fb_exceptions

    # Init OUTSIDE the token mapping: config mistakes are ImproperlyConfigured
    # (503 at the view), never misread as a rejected token (401).
    app = get_firebase_app()
    try:
        decoded = fb_auth.verify_id_token(id_token, app=app, check_revoked=False)
    except (fb_exceptions.InvalidArgumentError, ValueError) as exc:
        # Includes InvalidIdTokenError/ExpiredIdTokenError/RevokedIdTokenError
        # (all InvalidArgumentError subclasses) and signature/audience checks.
        raise FirebaseTokenError(str(exc)) from exc
    except fb_exceptions.FirebaseError as exc:
        raise FirebaseVerifierUnavailableError(f"Firebase verification backend error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — cert-fetch transport problems: server-side 503, loud
        raise FirebaseVerifierUnavailableError(f"Firebase verification failed: {exc}") from exc

    phone = str(decoded.get("phone_number") or "").strip()
    if not phone:
        raise FirebaseTokenError(
            "Firebase ID token carries no phone_number claim — only phone-auth logins are accepted."
        )
    return phone


def throttle_failed_verification(ip: str | None) -> None:
    """Count one failed verification per IP; raise past the daily cap.

    The new route has no OTP code row to burn attempts on, so the flood guard
    mirrors the repo's other cache counters (OTP per-IP daily cap, anchor
    throttle): best-effort, fail-OPEN on cache loss (logins must never block
    on cache trouble). Successes never count — a shared gym NAT IP cannot be
    locked out by legitimate members.

    Args:
        ip: The requesting client IP (``None`` skips the throttle).

    Raises:
        FirebaseRateLimited: When today's failure count for this IP exceeds
            ``FIREBASE_VERIFY_DAILY_LIMIT_PER_IP``.
    """
    from django.core.cache import cache

    if not ip:
        return
    cap = int(getattr(settings, "FIREBASE_VERIFY_DAILY_LIMIT_PER_IP", 50))
    key = f"firebase-auth-fail:{ip}:{date.today().isoformat()}"  # noqa: DTZ011 — local-date counters, like the OTP caps
    try:
        count = (cache.get(key) or 0) + 1
        cache.set(key, count, timeout=172800)
        if count > cap:
            raise FirebaseRateLimited()
    except FirebaseRateLimited:
        raise
    except Exception:  # noqa: BLE001 — throttle is best-effort; cache loss must not block logins
        logger.warning("Firebase auth throttle skipped (cache unavailable)")
