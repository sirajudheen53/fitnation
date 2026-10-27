"""Phone normalization to E.164 (issue #88).

Firebase phone-auth ID tokens carry the verified ``phone_number`` claim in
E.164 (``+918606806956``) and the login lookups match rows EXACTLY — but every
write path so far stored whatever the caller typed, which is how a real member
(a raw ``8606806956`` row) got a generic 400 at login (issue #88: 8 of 9 prod
phone rows had no leading ``+``).

Two rules, deliberately dependency-free and India-default (the platform's only
market, matching ``OTP_DEFAULT_COUNTRY_CODE``):

* :func:`normalize_e164` — the STORAGE rule for write paths: an unambiguous
  Indian number becomes ``+91XXXXXXXXXX``; anything ambiguous is left
  untouched rather than guessed (the resolver ladder still finds it).
* :func:`phone_lookup_candidates` — the LOOKUP rule: every storage format the
  candidate could be sitting under, E.164 first, so raw and normalized rows
  both resolve while the data migration (users 0008) is rolling out.
"""

from __future__ import annotations

import re

DEFAULT_COUNTRY_CODE = "91"

# A bare Indian subscriber number per the issue-#88 migration rule: 10 digits
# not starting with 0/1 (mobiles start 6-9; the 2-9 floor also keeps landlines
# normalizeable without guessing area codes).
_NATIONAL_RE = re.compile(r"[2-9]\d{9}\Z")

# Separators phone fields collect from copy-paste and human entry; stripped
# before the digit-shape checks (never used to reject a value).
_SEPARATORS_RE = re.compile(r"[\s().\-]")

# Trunk/country prefixes a bare Indian number is commonly typed with.
_PREFIXES = ("0", "91", "091")


def _national_number(digits: str) -> str | None:
    """The 10-digit Indian national number inside ``digits``, else ``None``.

    Accepts the bare national form and the ``0``/``91``/``091``-prefixed
    forms; anything else (too short, other country codes, non-numeric junk)
    is ambiguous and returns ``None``.
    """
    if _NATIONAL_RE.fullmatch(digits):
        return digits
    for prefix in _PREFIXES:
        if digits.startswith(prefix) and _NATIONAL_RE.fullmatch(digits[len(prefix) :]):
            return digits[len(prefix) :]
    return None


def normalize_e164(raw: str | None) -> str:
    """Normalize ``raw`` for storage: E.164 for unambiguous Indian numbers.

    Rules:

    * blank → blank;
    * ``+``-prefixed values are international — ``+91`` + a valid national
      number is canonicalized to ``+91XXXXXXXXXX`` (separators dropped), any
      other ``+`` number passes through with separators dropped (Firebase
      hands over E.164 and we never rewrite another country's numbers);
    * a bare value whose digits read as an Indian national number (optionally
      ``0``/``91``/``091``-prefixed) becomes ``+91`` + the national number;
    * anything ambiguous (``12345``, a 10-digit number starting with 0/1,
      non-numeric junk) is returned UNTOUCHED — guessing country codes is how
      login rows stop matching (issue #88).

    Idempotent: normalizing an E.164 value is a no-op.

    Args:
        raw: The entered or stored phone value (may be ``None``).

    Returns:
        The canonical E.164 form when unambiguous, else the input as given.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    cleaned = _SEPARATORS_RE.sub("", text)
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if not digits:
            return text
        rest = digits[len(DEFAULT_COUNTRY_CODE) :] if digits.startswith(DEFAULT_COUNTRY_CODE) else ""
        national = _national_number(rest) if rest else None
        if national is not None:
            return f"+{DEFAULT_COUNTRY_CODE}{national}"
        return cleaned
    national = _national_number("".join(ch for ch in cleaned if ch.isdigit()))
    if national is not None:
        return f"+{DEFAULT_COUNTRY_CODE}{national}"
    return text


def phone_lookup_candidates(raw: str | None) -> list[str]:
    """Every storage format ``raw`` could be sitting under, E.164 first.

    Feeds ``phone__in=`` so the exact-match login ladders resolve both
    normalized rows and legacy raw ones (``8606806956``, ``091…``, ``91…``
    without ``+``, or the caller's literal separators) during the issue-#88
    transition. Deduplicated; empty input yields no candidates (a blank phone
    must never match blank rows in a login lookup).

    Args:
        raw: The verified/entered phone candidate.

    Returns:
        Ordered lookup variants, canonical E.164 first, raw input last.
    """
    text = str(raw or "").strip()
    if not text:
        return []
    candidates: list[str] = []

    def add(value: str) -> None:
        if value and value not in candidates:
            candidates.append(value)

    add(normalize_e164(text))
    digits = "".join(ch for ch in text if ch.isdigit())
    national = _national_number(digits)
    if national is not None:
        add(f"+{DEFAULT_COUNTRY_CODE}{national}")
        add(national)  # legacy bare national rows (the prod #88 shape)
        add(f"0{national}")  # trunk-prefixed rows
        add(f"{DEFAULT_COUNTRY_CODE}{national}")  # country code without +
    add(text)  # the caller's literal form (separator-stored legacy rows)
    add(digits)
    return candidates
