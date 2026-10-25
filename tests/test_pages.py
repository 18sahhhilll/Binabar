"""Tests for public pages, robots.txt, sitemaps, credits, and security headers."""

import pytest
from django.conf import settings
from django.urls import reverse

from songs.models import Song


@pytest.fixture
def sample_songs(db):
    songs = []
    for i in range(2):
        s = Song.objects.create(
            title=f"Sample Track {i + 1}",
            artist="Divine",
            producers=["Phenom"],
            label="Gully Gang",
            year=2020,
            language="Hindi",
            source_type="youtube",
            youtube_id=f"yt_{i + 1}",
            start_seconds=10,
            end_seconds=22,
            source_url="https://youtube.com/watch?v=sample",
            verified=True,
            status="published",
        )
        songs.append(s)
    # Draft song
    Song.objects.create(
        title="Draft Track",
        artist="Naezy",
        producers=["Sez"],
        label="Independent",
        year=2021,
        language="Hindi",
        source_type="youtube",
        youtube_id="yt_draft",
        start_seconds=10,
        end_seconds=22,
        source_url="https://youtube.com/watch?v=draft",
        verified=False,
        status="draft",
    )
    return songs


@pytest.mark.django_db
class TestPublicPages:
    def test_landing_page(self, client):
        res = client.get(reverse("core:landing"))
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert "Hear the beat." in content
        assert "Name the track." in content
        # Hard bans
        assert "unleash" not in content.lower()
        assert "revolutionary" not in content.lower()

    def test_play_page(self, client):
        res = client.get(reverse("core:play"))
        assert res.status_code == 200

    def test_how_it_works_page(self, client):
        res = client.get(reverse("core:how_it_works"))
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert "10 rounds" in content

    def test_about_page(self, client):
        res = client.get(reverse("core:about"))
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert "[ABOUT TEXT" in content

    def test_privacy_page(self, client):
        res = client.get(reverse("core:privacy"))
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert "localStorage" in content
        assert "session cookie" in content.lower()

    def test_terms_page(self, client):
        res = client.get(reverse("core:terms"))
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert "Acceptable use" in content
        assert "Rights holders" in content or "removal" in content.lower()

    def test_credits_page_shows_only_published(self, client, sample_songs):
        res = client.get(reverse("core:credits"))
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert "Sample Track 1" in content
        assert "Sample Track 2" in content
        # Draft song must NOT appear on credits page
        assert "Draft Track" not in content
        # Source link rel="noopener noreferrer"
        assert 'rel="noopener noreferrer"' in content
        assert 'target="_blank"' in content

    def test_credits_page_filter(self, client, sample_songs):
        res = client.get(reverse("core:credits") + "?artist=Divine")
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert "Sample Track 1" in content


@pytest.mark.django_db
class TestAdminSecurityAndSecrecy:
    def test_robots_txt_does_not_contain_admin_url(self, client):
        res = client.get("/robots.txt")
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        admin_path = settings.ADMIN_URL.strip("/")
        assert admin_path not in content
        assert "admin" not in content.lower()

    def test_sitemap_does_not_contain_admin_url(self, client):
        res = client.get("/sitemap.xml")
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        admin_path = settings.ADMIN_URL.strip("/")
        assert admin_path not in content
        assert "admin" not in content.lower()

    def test_admin_path_has_noindex_header(self, client):
        admin_url = "/" + settings.ADMIN_URL
        res = client.get(admin_url)
        # Should redirect to login or show login, but header must be present
        assert res.get("X-Robots-Tag") == "noindex, nofollow"

    def test_default_admin_path_returns_404(self, client):
        if settings.ADMIN_URL != "admin/":
            res = client.get("/admin/")
            assert res.status_code == 404
