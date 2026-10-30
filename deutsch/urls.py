"""URL-Zuordnung des Arbeitsplans Deutsch."""

from django.urls import path

from deutsch import views

app_name = "deutsch"

urlpatterns = [
    path("<slug:schluessel>/abdeckung", views.abdeckung, name="abdeckung"),
    path("<slug:schluessel>/fahrplan/<int:jahrgang>", views.fahrplan, name="fahrplan"),
    path("<slug:schluessel>/rituale", views.ritualprogression, name="ritualprogression"),
    path("<slug:schluessel>/zeitbudget", views.zeitbudget, name="zeitbudget"),
    path("<slug:schluessel>/leistung", views.leistungsuebersicht, name="leistung"),
    path(
        "<slug:schluessel>/progressionspaare",
        views.progressionspaare,
        name="progressionspaare",
    ),
    path("<slug:schluessel>/pruefliste", views.pruefen, name="pruefliste"),
]
