"""Verwaltungsoberfläche für die Administration (SPEC.md §5)."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group

from kern.models import (
    Anhang,
    Beschluss,
    Dokument,
    Dokumenttyp,
    Eintrag,
    Eintragsversion,
    Gremium,
    Gruppenprofil,
    Kommentar,
    Nutzer,
    PersoenlicherFortschritt,
    Status,
    Verlinkung,
)

admin.site.site_header = "Schulwissen – Verwaltung"
admin.site.site_title = "Schulwissen"
admin.site.index_title = "Verwaltung"


@admin.register(Nutzer)
class NutzerAdmin(UserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    change_password_form = AdminPasswordChangeForm
    ordering = ["anzeigename"]
    list_display = ["email", "anzeigename", "kuerzel", "rollenliste", "is_active"]
    list_filter = ["is_active", "groups"]
    search_fields = ["email", "anzeigename", "kuerzel"]
    filter_horizontal = ["groups", "user_permissions"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Person", {"fields": ("anzeigename", "kuerzel")}),
        (
            "Rollen und Arbeitsgruppen",
            {
                "fields": ("groups", "is_active", "is_staff", "is_superuser"),
                "description": "Rollen und Arbeitsgruppen sind beides Gruppen – "
                "die Liste „Gruppenprofile“ sagt, was was ist.",
            },
        ),
        ("Rechte im Einzelnen", {"classes": ("collapse",), "fields": ("user_permissions",)}),
        ("Zeiten", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "anzeigename", "kuerzel", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="Rollen")
    def rollenliste(self, nutzer: Nutzer) -> str:
        return ", ".join(sorted(nutzer.rollen)) or "–"


class GruppenprofilInline(admin.StackedInline):
    model = Gruppenprofil
    can_delete = False
    extra = 0


# django.contrib.auth registriert Group selbst; wir ersetzen die Ansicht,
# damit Rollen und Arbeitsgruppen unterscheidbar sind.
admin.site.unregister(Group)


@admin.register(Group)
class GruppenAdmin(DjangoGroupAdmin):
    """Rollen und Arbeitsgruppen – unterscheidbar durch das Profil."""

    inlines = [GruppenprofilInline]
    list_display = ["name", "art", "mitglieder"]

    @admin.display(description="Art")
    def art(self, gruppe: Group) -> str:
        profil = getattr(gruppe, "profil", None)
        return profil.get_art_display() if profil else "(ohne Profil)"

    @admin.display(description="Mitglieder")
    def mitglieder(self, gruppe: Group) -> int:
        return gruppe.user_set.count()


@admin.register(Dokumenttyp)
class DokumenttypAdmin(admin.ModelAdmin):
    list_display = ["name", "schluessel", "eintragstypen"]
    readonly_fields = ["eintragstypen"]
    search_fields = ["name", "schluessel"]

    def has_add_permission(self, request) -> bool:
        # Dokumenttypen entstehen im Code, nicht in der Oberfläche (SPEC.md §6).
        return False


@admin.register(Dokument)
class DokumentAdmin(admin.ModelAdmin):
    list_display = ["titel", "schluessel", "dokumenttyp", "fach", "gueltig_ab_schuljahr", "anzahl"]
    list_filter = ["dokumenttyp", "fach"]
    search_fields = ["titel", "schluessel"]
    prepopulated_fields = {"schluessel": ("titel",)}

    @admin.display(description="Einträge")
    def anzahl(self, dokument: Dokument) -> int:
        return dokument.eintraege.count()


class VerlinkungInline(admin.TabularInline):
    model = Verlinkung
    fk_name = "von_eintrag"
    extra = 0
    fields = ["art", "ziel_typ", "ziel_id", "feld", "beschriftung"]


@admin.register(Eintrag)
class EintragAdmin(admin.ModelAdmin):
    list_display = ["kennung", "titel", "dokument", "eintragstyp", "status", "geaendert_am"]
    list_filter = ["dokument", "eintragstyp", "status"]
    search_fields = ["kennung", "titel", "suchtext"]
    readonly_fields = ["suchtext", "erstellt_am", "geaendert_am"]
    inlines = [VerlinkungInline]
    autocomplete_fields = ["eltern"]
    ordering = ["dokument", "position", "kennung"]


class EintragsversionInline(admin.TabularInline):
    model = Eintragsversion
    extra = 0
    fields = ["eintrag", "versionsnummer", "titel", "status", "autor", "zeitpunkt"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj) -> bool:
        return False


@admin.register(Eintragsversion)
class EintragsversionAdmin(admin.ModelAdmin):
    list_display = [
        "eintrag",
        "versionsnummer",
        "titel",
        "status",
        "autor",
        "zeitpunkt",
        "beschluss",
    ]
    list_filter = ["status", "beschluss"]
    search_fields = ["eintrag__kennung", "titel"]
    readonly_fields = ["eintrag", "versionsnummer", "daten", "verlinkungen", "autor", "zeitpunkt"]

    def has_add_permission(self, request) -> bool:
        # Fassungen entstehen beim Speichern eines Eintrags, nicht von Hand.
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.status == Status.BESCHLOSSEN:
            # Beschlossene Fassungen sind unveränderlich (SPEC.md §6).
            return [feld.name for feld in self.model._meta.fields]
        return self.readonly_fields


@admin.register(Gremium)
class GremiumAdmin(admin.ModelAdmin):
    list_display = ["name", "reihenfolge"]
    ordering = ["reihenfolge", "name"]


@admin.register(Beschluss)
class BeschlussAdmin(admin.ModelAdmin):
    list_display = ["datum", "gremium", "titel", "anzahl_fassungen"]
    list_filter = ["gremium", "datum"]
    search_fields = ["titel", "text"]
    date_hierarchy = "datum"
    inlines = [EintragsversionInline]

    @admin.display(description="freigegebene Fassungen")
    def anzahl_fassungen(self, beschluss: Beschluss) -> int:
        return beschluss.beschlossene_versionen.count()


@admin.register(Anhang)
class AnhangAdmin(admin.ModelAdmin):
    list_display = ["dateiname", "eintrag", "mimetype", "groesse", "index_stand"]
    list_filter = ["mimetype"]
    search_fields = ["dateiname", "beschreibung", "extrahierter_text"]
    readonly_fields = ["extrahierter_text", "index_stand"]


@admin.register(Kommentar)
class KommentarAdmin(admin.ModelAdmin):
    list_display = ["eintrag", "autor", "erledigt", "erstellt_am"]
    list_filter = ["erledigt"]
    search_fields = ["text"]


@admin.register(Verlinkung)
class VerlinkungAdmin(admin.ModelAdmin):
    list_display = ["von_eintrag", "art", "ziel_typ", "ziel_id", "beschriftung"]
    list_filter = ["art", "ziel_typ"]
    search_fields = ["ziel_id", "beschriftung"]


@admin.register(PersoenlicherFortschritt)
class FortschrittAdmin(admin.ModelAdmin):
    list_display = ["nutzer", "eintrag", "schuljahr", "klasse", "erledigt"]
    list_filter = ["schuljahr", "erledigt"]
