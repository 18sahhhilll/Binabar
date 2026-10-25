"""Binabar URL Configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from two_factor.urls import urlpatterns as tf_urls

from core.sitemaps import StaticViewSitemap
from core.views import robots_txt

sitemaps = {
    "static": StaticViewSitemap,
}

urlpatterns = [
    # Two-factor auth
    path("", include((tf_urls[0], "two_factor"))),
    # Admin at custom path
    path(settings.ADMIN_URL, admin.site.urls),
    # Game API
    path("api/", include("game.urls")),
    # Core pages
    path("", include("core.urls")),
    # Sitemaps
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    # Robots
    path("robots.txt", robots_txt, name="robots_txt"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
