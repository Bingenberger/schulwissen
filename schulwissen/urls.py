"""Oberste URL-Zuordnung."""

from django.contrib import admin
from django.urls import include, path
from kern import health

urlpatterns = [
    path("health/live", health.live),
    path("health/ready", health.ready),
    path("verwaltung/", admin.site.urls),
    path("suche/", include("suche.urls")),
    path("kompetenzen/", include("fachdaten.urls")),
    path("deutsch/", include("deutsch.urls")),
    path("", include("kern.urls")),
]
