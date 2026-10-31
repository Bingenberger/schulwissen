"""Verwaltung der Kompetenz-Stammdaten.

Die Lehrplandaten sind amtliche Vorgabe und werden importiert. Bearbeiten lässt
sich nur ``schulische_festlegung`` – das ist die Spalte, die der Schule gehört
(SPEC.md §7.3).
"""

from __future__ import annotations

from django.contrib import admin

from fachdaten.models import Fach, Kompetenzerwartung
from kern import rechte
from kern.admin_zugang import AdministrationsMixin


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
        if rechte.darf_schulische_festlegung_bearbeiten(request.user, obj.fach if obj else None):
            return self.NUR_LESEN
        return (*self.NUR_LESEN, "schulische_festlegung")

    def get_queryset(self, request):
        menge = super().get_queryset(request)
        if rechte.ist_administration(request.user):
            return menge
        faecher = rechte.berechtigte_dokumente(request.user, "bearbeiten").values("fach")
        return menge.filter(fach__in=faecher)

    def has_change_permission(self, request, obj=None):
        return rechte.darf_schulische_festlegung_bearbeiten(
            request.user, obj.fach if obj else None
        ) and super().has_change_permission(request, obj)

    def get_list_filter(self, request):
        # Die Fachauswahl darf keine fremden redaktionellen Bereiche anbieten.
        return self.list_filter if rechte.ist_administration(request.user) else []

    def has_add_permission(self, request) -> bool:
        # Nur über „manage.py kompetenzen_importieren“ (SPEC.md §11).
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Fach)
class FachAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["name", "schluessel", "quelle"]
    prepopulated_fields = {"schluessel": ("name",)}
    search_fields = ["name"]

    def has_delete_permission(self, request, obj=None):
        return False
