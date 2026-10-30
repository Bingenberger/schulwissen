"""Verwaltung der Kompetenz-Stammdaten.

Die Lehrplandaten sind amtliche Vorgabe und werden importiert. Bearbeiten lässt
sich nur ``schulische_festlegung`` – das ist die Spalte, die der Schule gehört
(SPEC.md §7.3).
"""

from __future__ import annotations

from django.contrib import admin

from fachdaten.models import Fach, Kompetenzerwartung
from kern import rechte


@admin.register(Kompetenzerwartung)
class KompetenzerwartungAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "kurztext",
        "bereich",
        "schwerpunkt_voll",
        "stufe",
        "ua_weiterer_inhalt",
        "schulische_festlegung",
        "stufe_pruefen",
    ]
    list_filter = ["fach", "bereich", "stufe", "ua_weiterer_inhalt", "stufe_pruefen"]
    search_fields = ["id", "text", "klammer", "schwerpunkt", "schulische_festlegung"]
    list_editable = ["schulische_festlegung"]
    list_per_page = 50
    ordering = ["bereich", "schwerpunkt_nr", "id"]

    fieldsets = (
        (
            "Lehrplan (amtlich, nur lesen)",
            {
                "fields": (
                    "id",
                    "fach",
                    "bereich",
                    "bereich_name",
                    "schwerpunkt_nr",
                    "schwerpunkt",
                    "stufe",
                    "text",
                    "klammer",
                    "ua_weiterer_inhalt",
                    "progressionspartner",
                    "stufe_pruefen",
                )
            },
        ),
        (
            "Schulische Festlegung",
            {
                "fields": ("schulische_festlegung",),
                "description": "Pflicht, wenn der Lehrplan „u. a.“ sagt: Welcher "
                "weitere Inhalt ist an der GGS Niederkassel verbindlich?",
            },
        ),
    )

    #: Alles außer der schulischen Festlegung ist unveränderlich.
    NUR_LESEN = (
        "id",
        "fach",
        "bereich",
        "bereich_name",
        "schwerpunkt_nr",
        "schwerpunkt",
        "stufe",
        "text",
        "klammer",
        "ua_weiterer_inhalt",
        "progressionspartner",
        "stufe_pruefen",
    )

    @admin.display(description="Kompetenzerwartung")
    def kurztext(self, erwartung: Kompetenzerwartung) -> str:
        return erwartung.text if len(erwartung.text) <= 90 else erwartung.text[:88] + " …"

    def get_readonly_fields(self, request, obj=None):
        if rechte.darf_schulische_festlegung_bearbeiten(request.user):
            return self.NUR_LESEN
        return (*self.NUR_LESEN, "schulische_festlegung")

    def has_add_permission(self, request) -> bool:
        # Nur über „manage.py kompetenzen_importieren“ (SPEC.md §11).
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Fach)
class FachAdmin(admin.ModelAdmin):
    list_display = ["name", "schluessel", "quelle"]
    prepopulated_fields = {"schluessel": ("name",)}
    search_fields = ["name"]

    def has_delete_permission(self, request, obj=None):
        return False
