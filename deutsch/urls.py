"""URL-Zuordnung des Arbeitsplans Deutsch."""

from django.urls import path

from deutsch import views

app_name = "deutsch"

urlpatterns = [
    path("<slug:schluessel>/abdeckung", views.abdeckung, name="abdeckung"),
    path("<slug:schluessel>/pruefliste", views.pruefen, name="pruefliste"),
]
