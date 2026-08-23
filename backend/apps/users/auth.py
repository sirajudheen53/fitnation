"""Custom DB-backed token model with tenant context.

The AuthToken model now lives in ``apps.users.models`` so Django's migration
system can discover it automatically. This module re-exports it for backward
compatibility with existing imports.
"""

from apps.users.models import AuthToken

__all__ = ["AuthToken"]