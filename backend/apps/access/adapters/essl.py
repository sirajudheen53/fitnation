"""eSSL adapter — thin wrapper over the shared ZKTeco ADMS implementation."""

from __future__ import annotations

from apps.access.adapters.zkteco import ZKTecoADMSAdapter


class EsslAdapter(ZKTecoADMSAdapter):
    """eSSL devices run ZKTeco ADMS firmware — reuse the ADMS adapter."""

    vendor_label = "eSSL"
