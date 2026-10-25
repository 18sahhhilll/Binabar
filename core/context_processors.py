"""Template context processors for site-wide variables."""

from django.conf import settings


def site_context(request):
    """Add site-wide variables to template context."""
    return {
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "CURRENT_YEAR": settings.CURRENT_YEAR,
        "SITE_NAME": "Binabar",
    }
