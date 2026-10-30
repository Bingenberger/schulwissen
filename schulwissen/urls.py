"""Oberste URL-Zuordnung."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("verwaltung/", admin.site.urls),
    path("suche/", include("suche.urls")),
    path("kompetenzen/", include("fachdaten.urls")),
    path("deutsch/", include("deutsch.urls")),
    path("", include("kern.urls")),
]

if settings.DEBUG:
    # Im Echtbetrieb liefert nginx die Anhänge aus (siehe DEPLOYMENT.md).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
