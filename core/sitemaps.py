"""Sitemaps for public pages."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages. Admin is never included."""

    priority = 0.5
    changefreq = "weekly"

    def items(self):
        return [
            "core:landing",
            "core:play",
            "core:how_it_works",
            "core:credits",
            "core:about",
            "core:privacy",
            "core:terms",
        ]

    def location(self, item):
        return reverse(item)
