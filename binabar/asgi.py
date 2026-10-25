"""ASGI config for binabar project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "binabar.settings")

application = get_asgi_application()
