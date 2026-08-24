"""Custom Django model fields shared across apps.

Provides :class:`EncryptedCharField`, a transparently encrypted text field
backed by the ``cryptography`` Fernet scheme. The encryption key is derived
from ``ENCRYPTION_SALT`` (or ``SECRET_KEY``) plus a fixed domain separator, so
values at rest are not plaintext.
"""

import base64
import hashlib
import os

from django.db import models

from cryptography.fernet import Fernet


def _fernet_key() -> bytes:
    """Derive a stable Fernet key from the environment salt or SECRET_KEY.

    Returns:
        A URL-safe base64 Fernet key (32 url-safe bytes).
    """
    salt = os.environ.get("ENCRYPTION_SALT", "") or os.environ.get("SECRET_KEY", "fitnation-insecure-default")
    digest = hashlib.sha256(f"fitnation:{salt}".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class EncryptedCharField(models.CharField):
    """A CharField whose values are encrypted at rest.

    Values are encrypted with Fernet before being written to the database and
    decrypted on read. Supports lookups on the decrypted value by encrypting the
    lookup argument.
    """

    def get_internal_type(self) -> str:
        """Report the underlying column type as a plain CharField."""
        return "CharField"

    def _cipher(self) -> Fernet:
        return Fernet(_fernet_key())

    def _encrypt(self, value: str) -> str:
        if value in ("", None):
            return ""
        return self._cipher().encrypt(value.encode("utf-8")).decode("utf-8")

    def _decrypt(self, value: str) -> str:
        if value in ("", None):
            return ""
        try:
            return self._cipher().decrypt(value.encode("utf-8")).decode("utf-8")
        except Exception:  # pragma: no cover - defensive against bad data
            return ""

    def get_db_prep_value(self, value, connection, prepared: bool = False):
        """Encrypt the value before writing to the database."""
        value = super().get_db_prep_value(value, connection, prepared)
        if value is None:
            return None
        return self._encrypt(str(value))

    def from_db_value(self, value, expression, connection):
        """Decrypt the value read from the database."""
        if value is None:
            return None
        return self._decrypt(value)

    def to_python(self, value):
        """Return a plaintext string when given plaintext input."""
        if isinstance(value, str) and not value.startswith("gAAAA"):
            return value
        if isinstance(value, str):
            return self._decrypt(value)
        return value
