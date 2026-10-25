"""Core URL patterns for static pages."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("play/", views.play, name="play"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("credits/", views.credits, name="credits"),
    path("about/", views.about, name="about"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
]
