"""Django admin configuration for Songs app."""

import csv
import json

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html

from .models import AuditLog, Song


def log_action(user, action, obj, changes=None):
    """Create an audit log entry."""
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=obj.__class__.__name__,
        object_id=str(obj.pk) if obj.pk else "",
        object_repr=str(obj)[:300],
        changes=changes or {},
    )


class SongAdmin(admin.ModelAdmin):
    """Admin for Song model with grouped sections and publish validation."""

    list_display = [
        "title",
        "artist",
        "label",
        "year",
        "status_badge",
        "verified_badge",
        "permission",
        "created_at",
    ]
    list_filter = ["status", "label", "permission", "verified", "language"]
    search_fields = ["title", "artist", "label", "album"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at", "clip_length_display"]
    actions = [
        "action_publish",
        "action_unpublish",
        "action_mark_verified",
        "action_suggest_answers",
        "action_export_json",
        "action_export_csv",
    ]

    fieldsets = (
        (
            "Song Info",
            {
                "fields": (
                    "id",
                    "title",
                    "artist",
                    "artists",
                    "album",
                    "year",
                    "language",
                ),
            },
        ),
        (
            "Credits",
            {
                "fields": (
                    "producers",
                    "label",
                ),
            },
        ),
        (
            "Audio",
            {
                "fields": (
                    "source_type",
                    "audio_file",
                    "youtube_id",
                    "start_seconds",
                    "end_seconds",
                    "clip_length_display",
                ),
                "description": "Choose upload or YouTube. For YouTube, paste a full URL in the YouTube ID field and the ID will be extracted.",
            },
        ),
        (
            "Hints and Accepted Answers",
            {
                "fields": (
                    "hint_artist_initial",
                    "hint_year",
                    "hint_language",
                    "accepted_answers",
                ),
                "description": "Hints auto-fill from the main fields. Override if needed.",
            },
        ),
        (
            "Rights and Status",
            {
                "fields": (
                    "source_url",
                    "permission",
                    "verified",
                    "status",
                    "private_notes",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    class Media:
        css = {"all": ("admin/css/song_admin.css",)}
        js = ("admin/js/song_admin.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "dashboard/",
                self.admin_site.admin_view(self.dashboard_view),
                name="songs_song_dashboard",
            ),
            path(
                "import-json/",
                self.admin_site.admin_view(self.import_json_view),
                name="songs_song_import",
            ),
            path(
                "<str:song_id>/preview/",
                self.admin_site.admin_view(self.preview_view),
                name="songs_song_preview",
            ),
            path(
                "test-mode/",
                self.admin_site.admin_view(self.test_mode_view),
                name="songs_song_testmode",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        # Dashboard counts
        qs = Song.objects.all()
        extra_context["draft_count"] = qs.filter(status="draft").count()
        extra_context["published_count"] = qs.filter(status="published", verified=True).count()
        extra_context["unverified_count"] = qs.filter(verified=False).count()
        extra_context["no_permission_count"] = qs.filter(permission="none").count()
        return super().changelist_view(request, extra_context=extra_context)

    def status_badge(self, obj):
        color = "#22c55e" if obj.status == "published" and obj.verified else "#ef4444"
        label = obj.status
        if obj.status == "published" and not obj.verified:
            label = "published (unverified)"
            color = "#f59e0b"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            label.upper(),
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def verified_badge(self, obj):
        if obj.verified:
            return format_html('<span style="color: #22c55e; font-weight: bold;">YES</span>')
        return format_html('<span style="color: #ef4444;">NO</span>')

    verified_badge.short_description = "Verified"
    verified_badge.admin_order_field = "verified"

    def clip_length_display(self, obj):
        length = obj.clip_length
        if length:
            warning = ""
            if length < 8 or length > 20:
                warning = format_html(
                    ' <span style="color: #ef4444; font-weight: bold;">'
                    "WARNING: Clip length outside 8-20s range!</span>"
                )
            return format_html("{:.1f} seconds{}", length, warning)
        return "Not set"

    clip_length_display.short_description = "Clip Length"

    def save_model(self, request, obj, form, change):
        """Save with validation and audit logging."""
        # Extract YouTube ID from URL if pasted
        if obj.youtube_id and len(obj.youtube_id) > 11:
            extracted = Song.extract_youtube_id(obj.youtube_id)
            if extracted:
                obj.youtube_id = extracted

        # Parse comma-separated JSON fields from form input
        for field_name in ["artists", "producers", "accepted_answers"]:
            value = form.cleaned_data.get(field_name, [])
            if isinstance(value, str):
                # Handle comma-separated string input
                parsed = [v.strip() for v in value.split(",") if v.strip()]
                setattr(obj, field_name, parsed)

        # Auto-fill hints
        if not obj.hint_artist_initial and obj.artist:
            obj.hint_artist_initial = obj.artist[0].upper()
        if not obj.hint_year and obj.year:
            obj.hint_year = obj.year
        if not obj.hint_language and obj.language:
            obj.hint_language = obj.language

        # Check for duplicates
        dupes = Song.objects.filter(title__iexact=obj.title, artist__iexact=obj.artist)
        if obj.pk:
            dupes = dupes.exclude(pk=obj.pk)
        if dupes.exists():
            messages.warning(
                request,
                "Duplicate warning: a song with the same title and artist already exists.",
            )

        if obj.youtube_id:
            yt_dupes = Song.objects.filter(youtube_id=obj.youtube_id)
            if obj.pk:
                yt_dupes = yt_dupes.exclude(pk=obj.pk)
            if yt_dupes.exists():
                messages.warning(
                    request,
                    "Duplicate warning: a song with the same YouTube ID already exists.",
                )

        # Log the action
        action = "update" if change else "create"
        try:
            # Validate before calling parent save
            obj.full_clean()
            super().save_model(request, obj, form, change)
            log_action(request.user, action, obj, changes=form.changed_data if change else {})
        except ValidationError:
            # Re-raise so Django admin handles it
            raise

    def delete_model(self, request, obj):
        """Delete song and its audio file."""
        log_action(request.user, "delete", obj)
        # Delete audio file from storage
        if obj.audio_file:
            try:
                obj.audio_file.delete(save=False)
            except Exception:
                pass
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Bulk delete with audio cleanup."""
        for obj in queryset:
            if obj.audio_file:
                try:
                    obj.audio_file.delete(save=False)
                except Exception:
                    pass
            log_action(request.user, "bulk_delete", obj)
        super().delete_queryset(request, queryset)

    # Bulk actions
    def action_publish(self, request, queryset):
        """Publish selected songs. Blocked if requirements not met."""
        published = 0
        errors = []
        for song in queryset:
            publish_errors = song._check_publish_requirements()
            if publish_errors:
                error_msgs = "; ".join(f"{k}: {v}" for k, v in publish_errors.items())
                errors.append(f"{song.title}: {error_msgs}")
            else:
                song.status = "published"
                song.save()
                log_action(request.user, "bulk_publish", song)
                published += 1

        if published:
            messages.success(request, f"{published} song(s) published.")
        for err in errors:
            messages.error(request, f"Cannot publish: {err}")

    action_publish.short_description = "Publish selected songs"

    def action_unpublish(self, request, queryset):
        """Unpublish selected songs."""
        count = queryset.update(status="draft")
        for song in queryset:
            log_action(request.user, "bulk_unpublish", song)
        messages.success(request, f"{count} song(s) unpublished.")

    action_unpublish.short_description = "Unpublish selected songs"

    def action_mark_verified(self, request, queryset):
        """Mark selected songs as verified."""
        count = queryset.update(verified=True)
        for song in queryset:
            log_action(request.user, "bulk_verify", song)
        messages.success(request, f"{count} song(s) marked as verified.")

    action_mark_verified.short_description = "Mark selected as verified"

    def action_suggest_answers(self, request, queryset):
        """Suggest accepted answers from title for selected songs."""
        updated = 0
        for song in queryset:
            suggestions = Song.suggest_accepted_answers(song.title)
            existing = set(song.accepted_answers or [])
            new_answers = list(existing | set(suggestions))
            if new_answers != song.accepted_answers:
                song.accepted_answers = new_answers
                song.save()
                updated += 1
                log_action(request.user, "suggest_answers", song)
        messages.success(request, f"Updated accepted answers for {updated} song(s).")

    action_suggest_answers.short_description = "Suggest accepted answers from title"

    def action_export_json(self, request, queryset):
        """Export selected songs as JSON."""
        data = []
        for song in queryset:
            data.append(
                {
                    "id": str(song.id),
                    "title": song.title,
                    "artist": song.artist,
                    "artists": song.artists,
                    "producers": song.producers,
                    "label": song.label,
                    "album": song.album,
                    "year": song.year,
                    "language": song.language,
                    "accepted_answers": song.accepted_answers,
                    "source_type": song.source_type,
                    "youtube_id": song.youtube_id,
                    "start_seconds": song.start_seconds,
                    "end_seconds": song.end_seconds,
                    "source_url": song.source_url,
                    "permission": song.permission,
                    "verified": song.verified,
                    "status": song.status,
                    "private_notes": song.private_notes,
                }
            )
        response = HttpResponse(
            json.dumps(data, indent=2, ensure_ascii=False),
            content_type="application/json",
        )
        response["Content-Disposition"] = 'attachment; filename="binabar_songs.json"'
        return response

    action_export_json.short_description = "Export as JSON"

    def action_export_csv(self, request, queryset):
        """Export selected songs as CSV."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="binabar_songs.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "title",
                "artist",
                "artists",
                "producers",
                "label",
                "album",
                "year",
                "language",
                "source_type",
                "youtube_id",
                "start_seconds",
                "end_seconds",
                "source_url",
                "permission",
                "verified",
                "status",
            ]
        )
        for song in queryset:
            writer.writerow(
                [
                    song.title,
                    song.artist,
                    "|".join(song.artists or []),
                    "|".join(song.producers or []),
                    song.label,
                    song.album,
                    song.year,
                    song.language,
                    song.source_type,
                    song.youtube_id,
                    song.start_seconds,
                    song.end_seconds,
                    song.source_url,
                    song.permission,
                    song.verified,
                    song.status,
                ]
            )
        return response

    action_export_csv.short_description = "Export as CSV"

    def dashboard_view(self, request):
        """Dashboard showing song counts."""
        qs = Song.objects.all()
        context = {
            **self.admin_site.each_context(request),
            "title": "Song Dashboard",
            "draft_count": qs.filter(status="draft").count(),
            "published_count": qs.filter(status="published", verified=True).count(),
            "unverified_count": qs.filter(verified=False).count(),
            "no_permission_count": qs.filter(permission="none").count(),
            "total_count": qs.count(),
        }
        return TemplateResponse(request, "admin/songs/dashboard.html", context)

    def preview_view(self, request, song_id):
        """Preview a single song as it would appear in the game."""
        try:
            song = Song.objects.get(id=song_id)
        except Song.DoesNotExist:
            messages.error(request, "Song not found.")
            return HttpResponse(status=404)

        audio_url = song.get_audio_url() if song.source_type == "upload" else None

        context = {
            **self.admin_site.each_context(request),
            "title": f"Preview: {song.title}",
            "song": song,
            "audio_url": audio_url,
        }
        return TemplateResponse(request, "admin/songs/preview.html", context)

    def test_mode_view(self, request):
        """Test mode: play a game with draft songs only. Admin only."""
        drafts = Song.objects.drafts()
        context = {
            **self.admin_site.each_context(request),
            "title": "Test Mode",
            "draft_count": drafts.count(),
            "songs": drafts,
        }
        return TemplateResponse(request, "admin/songs/test_mode.html", context)

    def import_json_view(self, request):
        """Import songs from JSON with validation and dry run."""
        if request.method == "POST":
            json_file = request.FILES.get("json_file")
            dry_run = request.POST.get("dry_run") == "on"

            if not json_file:
                messages.error(request, "No file uploaded.")
                return TemplateResponse(
                    request,
                    "admin/songs/import_json.html",
                    {**self.admin_site.each_context(request), "title": "Import Songs"},
                )

            try:
                data = json.loads(json_file.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                messages.error(request, f"Invalid JSON: {e}")
                return TemplateResponse(
                    request,
                    "admin/songs/import_json.html",
                    {**self.admin_site.each_context(request), "title": "Import Songs"},
                )

            results = []
            success_count = 0
            error_count = 0

            for i, item in enumerate(data):
                row_errors = []

                # Required fields
                for field in ["title", "artist", "producers", "label", "year", "language"]:
                    if not item.get(field):
                        row_errors.append(f"Missing: {field}")

                # Duplicate check
                if item.get("title") and item.get("artist"):
                    if Song.objects.filter(
                        title__iexact=item["title"],
                        artist__iexact=item["artist"],
                    ).exists():
                        row_errors.append("Duplicate: same title and artist exists")

                if item.get("youtube_id"):
                    if Song.objects.filter(youtube_id=item["youtube_id"]).exists():
                        row_errors.append("Duplicate: same YouTube ID exists")

                if row_errors:
                    error_count += 1
                    results.append(
                        {
                            "row": i + 1,
                            "title": item.get("title", "Unknown"),
                            "status": "error",
                            "errors": row_errors,
                        }
                    )
                else:
                    if not dry_run:
                        try:
                            song = Song(
                                title=item["title"],
                                artist=item["artist"],
                                artists=item.get("artists", []),
                                producers=item["producers"],
                                label=item["label"],
                                year=item["year"],
                                language=item["language"],
                                accepted_answers=item.get("accepted_answers", []),
                                source_type=item.get("source_type", "youtube"),
                                youtube_id=item.get("youtube_id", ""),
                                start_seconds=item.get("start_seconds", 0),
                                end_seconds=item.get("end_seconds", 0),
                                source_url=item.get("source_url", ""),
                                permission=item.get("permission", "none"),
                                verified=item.get("verified", False),
                                status=item.get("status", "draft"),
                                private_notes=item.get("private_notes", ""),
                            )
                            song.full_clean()
                            song.save()
                            log_action(request.user, "import", song)
                            success_count += 1
                        except ValidationError as e:
                            error_count += 1
                            results.append(
                                {
                                    "row": i + 1,
                                    "title": item.get("title", "Unknown"),
                                    "status": "error",
                                    "errors": [str(e)],
                                }
                            )
                            continue

                    success_count += 1
                    results.append(
                        {
                            "row": i + 1,
                            "title": item.get("title", "Unknown"),
                            "status": "ok" if not dry_run else "dry_run_ok",
                            "errors": [],
                        }
                    )

            mode_label = "Dry run" if dry_run else "Import"
            messages.info(
                request,
                f"{mode_label} complete: {success_count} success, {error_count} errors.",
            )

            context = {
                **self.admin_site.each_context(request),
                "title": f"{mode_label} Results",
                "results": results,
                "dry_run": dry_run,
                "success_count": success_count,
                "error_count": error_count,
            }
            return TemplateResponse(request, "admin/songs/import_results.html", context)

        context = {
            **self.admin_site.each_context(request),
            "title": "Import Songs from JSON",
        }
        return TemplateResponse(request, "admin/songs/import_json.html", context)


class AuditLogAdmin(admin.ModelAdmin):
    """Read-only admin for audit logs."""

    list_display = ["timestamp", "user", "action", "model_name", "object_repr"]
    list_filter = ["action", "model_name", "user"]
    search_fields = ["object_repr", "action"]
    ordering = ["-timestamp"]
    readonly_fields = [
        "id",
        "user",
        "action",
        "model_name",
        "object_id",
        "object_repr",
        "changes",
        "timestamp",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Customize admin site
admin.site.site_header = "Binabar Admin"
admin.site.site_title = "Binabar"
admin.site.index_title = "Dashboard"

admin.site.register(Song, SongAdmin)
admin.site.register(AuditLog, AuditLogAdmin)
