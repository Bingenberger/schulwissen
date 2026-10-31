"""Verwaltungsoberfläche für die Administration (SPEC.md §5)."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.html import format_html

from eintragstypen import dienste
from kern import rechte
from kern.admin_formulare import EintragAdminFormular
from kern.admin_zugang import AdministrationsMixin
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
    OIDCIdentitaet,
    Verlinkung,
    Wissensbereich,
    Zugangsregel,
)

admin.site.site_header = "Schulwissen – Verwaltung"
admin.site.site_title = "Schulwissen"
admin.site.index_title = "Verwaltung"


@admin.register(Nutzer)
class NutzerAdmin(AdministrationsMixin, UserAdmin):
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
class GruppenAdmin(AdministrationsMixin, DjangoGroupAdmin):
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
class DokumenttypAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["name", "schluessel", "eintragstypen"]
    readonly_fields = ["eintragstypen"]
    search_fields = ["name", "schluessel"]

    def has_add_permission(self, request) -> bool:
        # Dokumenttypen entstehen im Code, nicht in der Oberfläche (SPEC.md §6).
        return False


class ZugangsregelInline(admin.StackedInline):
    model = Zugangsregel
    extra = 0
    fields = ["nutzer", "gruppe", "lesen", "bearbeiten", "freigeben"]
    autocomplete_fields = ["nutzer", "gruppe"]


@admin.register(Wissensbereich)
class WissensbereichAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["name", "schluessel", "kollegiumsweit"]
    search_fields = ["name", "schluessel"]
    inlines = [ZugangsregelInline]


@admin.register(Zugangsregel)
class ZugangsregelAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["dokument", "bereich", "nutzer", "gruppe", "lesen", "bearbeiten", "freigeben"]
    list_filter = ["lesen", "bearbeiten", "freigeben", "bereich", "dokument"]
    autocomplete_fields = ["dokument", "bereich", "nutzer", "gruppe"]
    search_fields = ["dokument__titel", "bereich__name", "nutzer__anzeigename", "gruppe__name"]


@admin.register(Dokument)
class DokumentAdmin(AdministrationsMixin, admin.ModelAdmin):
    inlines = [ZugangsregelInline]
    autocomplete_fields = ["bereich"]
    list_display = ["titel", "schluessel", "dokumenttyp", "fach", "gueltig_ab_schuljahr", "anzahl"]
    list_filter = ["dokumenttyp", "fach", "bereich", "kollegiumsweit"]
    search_fields = ["titel", "schluessel"]
    prepopulated_fields = {"schluessel": ("titel",)}

    def has_delete_permission(self, request, obj=None):
        # Historie und dauerhafte Beschlusszugänge dürfen nicht durch Kaskaden verschwinden.
        return False

    @admin.display(description="Einträge")
    def anzahl(self, dokument: Dokument) -> int:
        return dokument.eintraege.count()


class InterneInhalteAdmin(AdministrationsMixin, admin.ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return rechte.darf_arbeitsstand_lesen(request.user) and super().has_view_permission(
            request, obj
        )

    def get_queryset(self, request):
        menge = super().get_queryset(request)
        return menge if rechte.darf_arbeitsstand_lesen(request.user) else menge.none()


class VerlinkungInline(admin.TabularInline):
    model = Verlinkung
    fk_name = "von_eintrag"
    extra = 0
    fields = ["art", "ziel_typ", "ziel_id", "feld", "beschriftung"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Eintrag)
class EintragAdmin(InterneInhalteAdmin):
    form = EintragAdminFormular
    list_display = ["kennung", "titel", "dokument", "typ_spalte", "status", "geaendert_am"]
    list_filter = ["dokument", "eintragstyp", "status"]
    search_fields = ["kennung", "titel", "suchtext"]
    readonly_fields = ["suchtext", "erstellt_am", "geaendert_am", "erstellt_von", "eingabemaske"]
    inlines = [VerlinkungInline]
    autocomplete_fields = ["eltern"]
    ordering = ["dokument", "position", "kennung"]

    def get_readonly_fields(self, request, obj=None):
        return [*self.readonly_fields, *(["kennung", "dokument", "eintragstyp"] if obj else [])]

    def get_form(self, request, obj=None, **kwargs):
        basis = super().get_form(request, obj, **kwargs)

        class Formular(basis):
            def __init__(self, *args, **optionen):
                super().__init__(*args, nutzer=request.user, **optionen)

        return Formular

    def has_add_permission(self, request):
        return rechte.darf_anlegen(request.user) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        erlaubt = (
            rechte.darf_bearbeiten(request.user, obj) if obj else rechte.ist_lehrkraft(request.user)
        )
        return erlaubt and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        gespeichert = dienste.speichern(
            obj.dokument,
            form.befundsatz,
            nutzer=request.user,
            metadaten={
                name: getattr(obj, name)
                for name in (
                    "eltern",
                    "position",
                    "verantwortlich_gruppe",
                    "verantwortlich_person",
                    "verantwortlich_text",
                    "fassung_stand",
                )
            },
        )
        obj.__dict__.update(gespeichert.__dict__)

    @admin.display(description="Eingabemaske")
    def eingabemaske(self, obj):
        if not obj or not obj.pk:
            return (
                "Kompetenzen und Verweise lassen sich nach dem Anlegen "
                "in der Eingabemaske bearbeiten."
            )
        return format_html(
            '<a href="{}">Eintrag mit Kompetenzen und Verweisen bearbeiten</a>',
            reverse("kern:eintrag_bearbeiten", args=[obj.dokument.schluessel, obj.kennung]),
        )

    @admin.display(description="Eintragstyp", ordering="eintragstyp")
    def typ_spalte(self, eintrag: Eintrag) -> str:
        """Macht einen unbekannten Typ in der Liste sofort sichtbar."""
        if eintrag.typ_bekannt:
            return eintrag.typ.name
        return f"⚠ unbekannt: {eintrag.eintragstyp}"


class EintragsversionInline(admin.TabularInline):
    model = Eintragsversion
    extra = 0
    fields = ["eintrag", "versionsnummer", "titel", "status", "autor", "zeitpunkt"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj) -> bool:
        return False


@admin.register(Eintragsversion)
class EintragsversionAdmin(InterneInhalteAdmin):
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
        return [feld.name for feld in self.model._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Gremium)
class GremiumAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["name", "reihenfolge"]
    ordering = ["reihenfolge", "name"]


@admin.register(Beschluss)
class BeschlussAdmin(InterneInhalteAdmin):
    list_display = ["datum", "gremium", "titel", "anzahl_fassungen"]
    list_filter = ["gremium", "datum"]
    search_fields = ["titel", "text"]
    date_hierarchy = "datum"
    inlines = [EintragsversionInline]

    change_list_template = "kern/admin_beschluesse.html"

    def get_readonly_fields(self, request, obj=None):
        return [feld.name for feld in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="freigegebene Fassungen")
    def anzahl_fassungen(self, beschluss: Beschluss) -> int:
        return beschluss.beschlossene_versionen.count()


@admin.register(Anhang)
class AnhangAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["dateiname", "eintrag", "mimetype", "groesse", "index_stand"]
    list_filter = ["mimetype"]
    search_fields = ["dateiname", "beschreibung", "extrahierter_text"]
    readonly_fields = ["extrahierter_text", "index_stand"]


@admin.register(Kommentar)
class KommentarAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["eintrag", "autor", "erledigt", "erstellt_am"]
    list_filter = ["erledigt"]
    search_fields = ["text"]


@admin.register(Verlinkung)
class VerlinkungAdmin(InterneInhalteAdmin):
    list_display = ["von_eintrag", "art", "ziel_typ", "ziel_id", "beschriftung"]
    list_filter = ["art", "ziel_typ"]
    search_fields = ["ziel_id", "beschriftung"]

    def get_readonly_fields(self, request, obj=None):
        return [feld.name for feld in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OIDCIdentitaet)
class OIDCIdentitaetAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["nutzer", "issuer", "subject"]
    search_fields = ["nutzer__email", "subject"]
    autocomplete_fields = ["nutzer"]
