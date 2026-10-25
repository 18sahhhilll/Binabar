"""Tests for Song admin bulk actions, import/export, and audit logging."""

import pytest
from django.contrib.auth import get_user_model

from songs.models import AuditLog, Song

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("adminuser", "admin@example.com", "pass1234Secure!")


@pytest.mark.django_db
class TestSongAdminFeatures:
    def test_suggest_accepted_answers(self):
        suggestions = Song.suggest_accepted_answers("Say My Name (feat. Divine) [Remix]")
        assert "Say My Name (feat. Divine) [Remix]" in suggestions
        assert "Say My Name" in suggestions

    def test_audit_log_created_on_save(self, admin_user):
        from songs.admin import log_action

        song = Song.objects.create(
            title="Aafat",
            artist="Naezy",
            producers=["Sez on the Beat"],
            label="Independent",
            year=2015,
            language="Hindi",
            source_type="youtube",
            youtube_id="abcdefghijk",
            start_seconds=10,
            end_seconds=22,
            source_url="https://youtube.com/watch?v=abcdefghijk",
            verified=True,
            status="published",
        )
        log_action(admin_user, "create", song, changes={"title": "Aafat"})

        assert AuditLog.objects.count() == 1
        log = AuditLog.objects.first()
        assert log.user == admin_user
        assert log.action == "create"
        assert log.model_name == "Song"
        assert log.object_repr == str(song)
