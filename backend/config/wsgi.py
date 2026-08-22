"""WSGI config for FBOS backend."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
