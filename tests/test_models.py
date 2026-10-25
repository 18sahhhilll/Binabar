"""Tests for Song model validations, publishing rules, and constraints."""

from datetime import datetime

import pytest
from django.core.exceptions import ValidationError

from songs.models import Song


@pytest.mark.django_db
class TestSongModelValidations:
    def test_producers_required(self):
        song = Song(
            title="Aafat",
            artist="Naezy",
            producers=[],
            label="Gully Gang",
            year=2015,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=22,
            source_url="https://example.com/track",
            status="draft",
        )
        with pytest.raises(ValidationError) as exc:
            song.clean()
        assert "producers" in exc.value.error_dict

    def test_label_required(self):
        song = Song(
            title="Aafat",
            artist="Naezy",
            producers=["Sez on the Beat"],
            label="",
            year=2015,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=22,
            source_url="https://example.com/track",
            status="draft",
        )
        with pytest.raises(ValidationError) as exc:
            song.clean()
        assert "label" in exc.value.error_dict

    def test_clip_length_range(self):
        # Too short (< 8s)
        song_short = Song(
            title="Track 1",
            artist="Artist",
            producers=["Producer"],
            label="Label",
            year=2020,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=15,  # 5s
            source_url="https://example.com",
            status="draft",
        )
        with pytest.raises(ValidationError) as exc:
            song_short.clean()
        assert "end_seconds" in exc.value.error_dict

        # Too long (> 20s)
        song_long = Song(
            title="Track 2",
            artist="Artist",
            producers=["Producer"],
            label="Label",
            year=2020,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=35,  # 25s
            source_url="https://example.com",
            status="draft",
        )
        with pytest.raises(ValidationError) as exc:
            song_long.clean()
        assert "end_seconds" in exc.value.error_dict

    def test_year_validation(self):
        # Year in future
        future_year = datetime.now().year + 2
        song = Song(
            title="Future Track",
            artist="Artist",
            producers=["Producer"],
            label="Label",
            year=future_year,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=22,
            source_url="https://example.com",
            status="draft",
        )
        with pytest.raises(ValidationError) as exc:
            song.clean()
        assert "year" in exc.value.error_dict

    def test_source_url_must_be_https(self):
        song = Song(
            title="Insecure Track",
            artist="Artist",
            producers=["Producer"],
            label="Label",
            year=2021,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=22,
            source_url="http://insecure.com",
            status="draft",
        )
        with pytest.raises(ValidationError) as exc:
            song.clean()
        assert "source_url" in exc.value.error_dict


@pytest.mark.django_db
class TestSongPublishBlocking:
    def test_publish_blocked_if_unverified(self):
        song = Song(
            title="Unverified Track",
            artist="Artist",
            producers=["Producer"],
            label="Label",
            year=2021,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=22,
            source_url="https://example.com",
            verified=False,
            status="published",
        )
        with pytest.raises(ValidationError) as exc:
            song.clean()
        assert "verified" in exc.value.error_dict

    def test_publish_blocked_if_missing_audio(self):
        song = Song(
            title="No Audio Track",
            artist="Artist",
            producers=["Producer"],
            label="Label",
            year=2021,
            language="Hindi",
            source_type="upload",
            audio_file=None,
            source_url="https://example.com",
            verified=True,
            status="published",
        )
        with pytest.raises(ValidationError) as exc:
            song.clean()
        assert "audio_file" in exc.value.error_dict

    def test_publish_blocked_if_missing_source_url(self):
        song = Song(
            title="No URL Track",
            artist="Artist",
            producers=["Producer"],
            label="Label",
            year=2021,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=22,
            source_url="",
            verified=True,
            status="published",
        )
        with pytest.raises(ValidationError) as exc:
            song.clean()
        assert "source_url" in exc.value.error_dict

    def test_publish_success_when_all_requirements_met(self):
        song = Song.objects.create(
            title="Kohinoor",
            artist="DIVINE",
            producers=["Phenom"],
            label="Gully Gang",
            year=2019,
            language="Hindi",
            source_type="youtube",
            youtube_id="abc12345678",
            start_seconds=10,
            end_seconds=22,
            source_url="https://youtube.com/watch?v=abc12345678",
            verified=True,
            status="published",
        )
        assert song.status == "published"
        assert song.verified is True
        assert Song.objects.published().count() == 1
        assert Song.objects.drafts().count() == 0
