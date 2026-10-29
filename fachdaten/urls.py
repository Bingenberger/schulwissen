"""URL-Zuordnung der Fachdaten."""

from django.urls import path

from fachdaten import views

app_name = "fachdaten"

urlpatterns = [
    path("", views.kompetenz_uebersicht, name="uebersicht"),
    path("suche", views.kompetenz_suche, name="suche"),
]
