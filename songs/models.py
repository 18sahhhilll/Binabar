"""Song model and AuditLog for Binabar."""

import re
import uuid
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone


def audio_upload_path(instance, filename):
    """Generate a random UUID filename for audio uploads. Never use song title."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp3"
    return f"audio/{uuid.uuid4().hex}.{ext}"


class SongQuerySet(models.QuerySet):
    """Custom queryset for Song model."""

    def published(self):
        """Only songs with status 'published' AND verified=True."""
        return self.filter(status="published", verified=True)

    def drafts(self):
        """Draft songs only."""
        return self.filter(status="draft")


class SongManager(models.Manager):
    """Custom manager using SongQuerySet."""

    def get_queryset(self):
        return SongQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def drafts(self):
        return self.get_queryset().drafts()


class Song(models.Model):
    """A DHH track in the Binabar game."""

    SOURCE_TYPES = [
        ("upload", "Upload"),
        ("youtube", "YouTube"),
    ]

    PERMISSION_CHOICES = [
        ("none", "None"),
        ("requested", "Requested"),
        ("granted", "Granted"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
    ]

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    artist = models.CharField(
        max_length=300,
        help_text="Main artist display name",
    )
    artists = models.JSONField(
        default=list,
        blank=True,
        help_text="List of all artists. Enter comma-separated values.",
    )
    producers = models.JSONField(
        default=list,
        help_text="List of producers. REQUIRED. Enter comma-separated values.",
    )
    label = models.CharField(
        max_length=300,
        help_text="Record label. REQUIRED.",
    )
    album = models.CharField(max_length=300, blank=True, default="")
    year = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1990),
            MaxValueValidator(datetime.now().year),
        ],
    )
    language = models.CharField(
        max_length=100,
        help_text="Primary language of the track",
    )

    # Accepted answers
    accepted_answers = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional accepted answer strings. Enter comma-separated values.",
    )

    # Audio source
    source_type = models.CharField(
        max_length=10,
        choices=SOURCE_TYPES,
        default="upload",
    )
    audio_file = models.FileField(
        upload_to=audio_upload_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["mp3", "m4a", "wav"])],
        help_text="Upload MP3, M4A, or WAV. Max 15 MB.",
    )
    youtube_id = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="YouTube video ID (extracted automatically from URL)",
    )
    start_seconds = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Clip start time in seconds",
    )
    end_seconds = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Clip end time in seconds",
    )

    # Hints
    hint_artist_initial = models.CharField(
        max_length=5,
        blank=True,
        default="",
        help_text="Auto-filled from artist name. Can override.",
    )
    hint_year = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Auto-filled from year. Can override.",
    )
    hint_language = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Auto-filled from language. Can override.",
    )

    # Rights
    source_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Official link to the song (HTTPS only)",
    )
    permission = models.CharField(
        max_length=20,
        choices=PERMISSION_CHOICES,
        default="none",
    )
    verified = models.BooleanField(
        default=False,
        help_text="Credits have been verified as accurate",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    private_notes = models.TextField(
        blank=True,
        default="",
        help_text="Internal notes. Never shown publicly.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SongManager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(year__gte=1990),
                name="song_year_min",
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.artist}"

    def clean(self):
        """Model-level validation."""
        errors = {}

        # Producers must not be empty
        if not self.producers or (isinstance(self.producers, list) and len(self.producers) == 0):
            errors["producers"] = "At least one producer is required."

        # Label must not be empty
        if not self.label or not self.label.strip():
            errors["label"] = "Label is required."

        # Validate clip length
        if self.source_type == "youtube":
            if self.end_seconds and self.start_seconds is not None:
                clip_length = self.end_seconds - self.start_seconds
                if clip_length < 8 or clip_length > 20:
                    errors["end_seconds"] = (
                        f"Clip length must be 8-20 seconds. Current: {clip_length:.1f}s"
                    )
            if not self.youtube_id:
                errors["youtube_id"] = "YouTube ID is required for YouTube source."

        # Source URL must be HTTPS
        if self.source_url and not self.source_url.startswith("https://"):
            errors["source_url"] = "Source URL must use HTTPS."

        # Validate year upper bound dynamically
        current_year = datetime.now().year
        if self.year and self.year > current_year:
            errors["year"] = f"Year cannot be in the future (max: {current_year})."

        # Publishing checks
        if self.status == "published":
            publish_errors = self._check_publish_requirements()
            errors.update(publish_errors)

        # Audio file validation
        if self.audio_file:
            self._validate_audio_file(errors)

        if errors:
            raise ValidationError(errors)

    def _check_publish_requirements(self):
        """Check all requirements for publishing. Return dict of errors."""
        errors = {}
        if not self.producers or (isinstance(self.producers, list) and len(self.producers) == 0):
            errors["producers"] = "Producers are required to publish."
        if not self.label or not self.label.strip():
            errors["label"] = "Label is required to publish."
        if not self.source_url:
            errors["source_url"] = "Source URL is required to publish."
        if not self.verified:
            errors["verified"] = "Song must be verified to publish."
        if self.source_type == "upload" and not self.audio_file:
            errors["audio_file"] = "Audio file is required to publish."
        if self.source_type == "youtube" and not self.youtube_id:
            errors["youtube_id"] = "YouTube ID is required to publish."
        return errors

    def _validate_audio_file(self, errors):
        """Validate audio file by content type and size."""
        if hasattr(self.audio_file, "size"):
            # Max 15 MB
            max_size = 15 * 1024 * 1024
            if self.audio_file.size > max_size:
                errors["audio_file"] = (
                    f"Audio file too large: {self.audio_file.size / 1024 / 1024:.1f} MB. "
                    f"Max: 15 MB."
                )

            # Validate content type
            if hasattr(self.audio_file, "content_type"):
                allowed_types = [
                    "audio/mpeg",
                    "audio/mp3",
                    "audio/mp4",
                    "audio/x-m4a",
                    "audio/m4a",
                    "audio/wav",
                    "audio/x-wav",
                    "audio/wave",
                ]
                if self.audio_file.content_type not in allowed_types:
                    # Also check by extension as a fallback
                    name = self.audio_file.name or ""
                    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                    if ext not in ("mp3", "m4a", "wav"):
                        errors["audio_file"] = (
                            f"Invalid audio format: {self.audio_file.content_type}. "
                            f"Allowed: MP3, M4A, WAV."
                        )

    def save(self, *args, **kwargs):
        """Auto-fill hints before saving."""
        # Auto-fill hints if not manually set
        if not self.hint_artist_initial and self.artist:
            self.hint_artist_initial = self.artist[0].upper()
        if not self.hint_year and self.year:
            self.hint_year = self.year
        if not self.hint_language and self.language:
            self.hint_language = self.language

        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete song and its audio file from storage."""
        if self.audio_file:
            try:
                self.audio_file.delete(save=False)
            except Exception:
                pass
        super().delete(*args, **kwargs)

    @property
    def clip_length(self):
        """Calculate clip length in seconds."""
        if self.end_seconds and self.start_seconds is not None:
            return self.end_seconds - self.start_seconds
        return 0

    def get_audio_url(self):
        """Get the audio URL. In production, this generates a signed URL."""
        if self.source_type == "upload" and self.audio_file:
            return self.audio_file.url
        return None

    @staticmethod
    def extract_youtube_id(url):
        """Extract YouTube video ID from various URL formats."""
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
            r"^([a-zA-Z0-9_-]{11})$",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def suggest_accepted_answers(title):
        """Generate accepted answer suggestions from a title."""
        answers = set()
        answers.add(title)

        # Remove content in brackets/parentheses
        cleaned = re.sub(r"\s*[\(\[\{].*?[\)\]\}]\s*", " ", title).strip()
        if cleaned and cleaned != title:
            answers.add(cleaned)

        # Remove "feat." / "ft." and everything after
        feat_removed = re.split(r"\s+(?:feat\.?|ft\.?)\s+", title, flags=re.IGNORECASE)[0].strip()
        if feat_removed and feat_removed != title:
            answers.add(feat_removed)

        # Remove all punctuation
        no_punct = re.sub(r"[^\w\s]", "", title).strip()
        if no_punct and no_punct != title:
            answers.add(no_punct)

        # Combine: remove brackets then punctuation
        combined = re.sub(r"[^\w\s]", "", cleaned).strip()
        if combined and combined not in answers:
            answers.add(combined)

        return sorted(answers)


class AuditLog(models.Model):
    """Track who changed what and when. Visible only in admin."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True, default="")
    object_repr = models.CharField(max_length=300, blank=True, default="")
    changes = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {self.user} | {self.action} | {self.object_repr}"
