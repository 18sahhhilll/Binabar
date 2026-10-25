"""Custom middleware for Binabar."""

from django.conf import settings


class AdminNoIndexMiddleware:
    """Add noindex headers to all admin pages."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = f"/{settings.ADMIN_URL}"

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self.admin_prefix):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
