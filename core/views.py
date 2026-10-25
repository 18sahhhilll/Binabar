"""Views for core static pages."""

from django.http import HttpResponse
from django.shortcuts import render

from songs.models import Song


def landing(request):
    """Landing page."""
    return render(request, "core/landing.html")


def play(request):
    """Game play page."""
    song_count = Song.objects.published().count()
    return render(request, "core/play.html", {"song_count": song_count})


def how_it_works(request):
    """How it works page."""
    return render(request, "core/how_it_works.html")


def credits(request):
    """Credits page showing all published songs."""
    songs = Song.objects.published().order_by("title")
    artist_filter = request.GET.get("artist", "")
    label_filter = request.GET.get("label", "")

    if artist_filter:
        songs = songs.filter(artist__icontains=artist_filter)
    if label_filter:
        songs = songs.filter(label__icontains=label_filter)

    # Get unique artists and labels for filter dropdowns
    all_songs = Song.objects.published()
    artists = sorted(all_songs.values_list("artist", flat=True).distinct())
    labels = sorted(all_songs.values_list("label", flat=True).distinct())

    return render(
        request,
        "core/credits.html",
        {
            "songs": songs,
            "artists": artists,
            "labels": labels,
            "artist_filter": artist_filter,
            "label_filter": label_filter,
        },
    )


def about(request):
    """About page."""
    return render(request, "core/about.html")


def privacy(request):
    """Privacy policy page."""
    return render(request, "core/privacy.html")


def terms(request):
    """Terms and conditions page."""
    return render(request, "core/terms.html")


def robots_txt(request):
    """Generate robots.txt, never reference the admin URL."""
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
