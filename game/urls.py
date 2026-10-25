"""Game API URL patterns."""

from django.urls import path

from . import views

app_name = "game"

urlpatterns = [
    path("start/", views.start_game, name="start"),
    path("round/", views.get_round, name="round"),
    path("guess/", views.submit_guess, name="guess"),
    path("hint/", views.get_hint, name="hint"),
    path("skip/", views.skip_round, name="skip"),
    path("search/", views.search_songs, name="search"),
]
