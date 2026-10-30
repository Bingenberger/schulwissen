"""URL-Zuordnung der Suche."""

from django.urls import path

from suche import views

app_name = "suche"

urlpatterns = [
    path("", views.suchen, name="suchen"),
    path("vorschlaege", views.vorschlaege, name="vorschlaege"),
]
