"""URL-Zuordnung der Fachdaten."""

from django.urls import path

from fachdaten import austausch_views, views

app_name = "fachdaten"

urlpatterns = [
    path("", views.kompetenz_uebersicht, name="uebersicht"),
    path("suche", views.kompetenz_suche, name="suche"),
    path("import", austausch_views.kompetenzimport, name="import"),
    path("export.<str:format>", austausch_views.export, name="export"),
]
