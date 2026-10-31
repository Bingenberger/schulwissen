"""Backend-Formulare und atomarer Wechsel schulischer Funktionsbesetzungen."""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import AutocompleteSelect
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from kern import funktionen, rechte
from kern.admin_zugang import AdministrationsMixin
from kern.models import Funktionsbereich, Funktionsbesetzung, Funktionsstand, Nutzer, Schulfunktion


class FunktionsFormular(forms.ModelForm):
    ausgangsrevision = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Schulfunktion
        fields = [
            "name",
            "schluessel",
            "aufgabe",
            "besetzungsmodus",
            "archiviert",
            "dienst_email",
            "dienst_telefon",
            "kontakt_hinweis",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["ausgangsrevision"].required = True
            self.initial["ausgangsrevision"] = self.instance.revision

    def clean(self):
        daten = super().clean()
        if self.instance.pk and daten.get("ausgangsrevision") != self.instance.revision:
            self.add_error(
                None,
                "Dieser Stand wurde inzwischen geändert. Deine Eingaben bleiben erhalten. "
                "Bitte öffne die aktuelle Fassung in einem neuen Tab, vergleiche die "
                "Angaben und übertrage sie bewusst.",
            )
        return daten


class BesetzungsFormular(FunktionsFormular):
    class Meta(FunktionsFormular.Meta):
        model = Funktionsbesetzung
        fields = [
            "funktion",
            "person",
            "bereich",
            "art",
            "gueltig_ab",
            "gueltig_bis",
            "vertretung_aktiv",
            "storniert",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "person" in self.fields:
            self.fields["person"].queryset = Nutzer.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.person_id)
            )


class RevisionAdmin(AdministrationsMixin, admin.ModelAdmin):
    readonly_fields = ["erstellt_am", "geaendert_am", "erstellt_von", "revision", "historie"]

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method != "POST" or not rechte.ist_administration(request.user):
            return super().changeform_view(request, object_id, form_url, extra_context)
        with transaction.atomic():
            if self.model == Schulfunktion:
                funktion_id = object_id
            elif object_id and object_id.isdecimal():
                funktion_id = (
                    Funktionsbesetzung.objects.filter(pk=object_id)
                    .values_list("funktion_id", flat=True)
                    .first()
                )
            else:
                funktion_id = request.POST.get("funktion")
            if funktion_id and str(funktion_id).isdecimal():
                Schulfunktion.objects.select_for_update(of=("self",)).filter(pk=funktion_id).first()
            return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        obj.save(autor=request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Nachvollziehbare Stände")
    def historie(self, obj):
        if not obj or not obj.pk:
            return "Nach dem ersten Speichern verfügbar."
        feld = "funktion__id__exact" if isinstance(obj, Schulfunktion) else "besetzung__id__exact"
        return format_html(
            '<a href="{}?{}={}">Gespeicherte Stände anzeigen</a>',
            reverse("admin:kern_funktionsstand_changelist"),
            feld,
            obj.pk,
        )


@admin.register(Schulfunktion)
class SchulfunktionAdmin(RevisionAdmin):
    form = FunktionsFormular
    list_display = ["name", "schluessel", "besetzungsmodus", "archiviert"]
    list_filter = ["archiviert", "besetzungsmodus"]
    search_fields = ["name", "schluessel", "aufgabe"]
    prepopulated_fields = {"schluessel": ("name",)}

    def get_readonly_fields(self, request, obj=None):
        return [
            *self.readonly_fields,
            *(["schluessel"] if obj else []),
            *(["besetzungsmodus"] if obj and obj.besetzungen.exists() else []),
            "besetzungen_anzeigen",
        ]

    def get_prepopulated_fields(self, request, obj=None):
        return {} if obj else self.prepopulated_fields

    @admin.display(description="Besetzungen verwalten")
    def besetzungen_anzeigen(self, obj):
        if not obj or not obj.pk:
            return "Speichere die Funktion, um Personen aus dem Nutzerstamm zuzuordnen."
        return format_html(
            '<a href="{}?funktion__id__exact={}">Besetzungen anzeigen</a> · '
            '<a href="{}?funktion={}">Besetzung hinzufügen</a>',
            reverse("admin:kern_funktionsbesetzung_changelist"),
            obj.pk,
            reverse("admin:kern_funktionsbesetzung_add"),
            obj.pk,
        )


@admin.register(Funktionsbereich)
class FunktionsbereichAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["name", "schluessel"]
    search_fields = ["name", "schluessel"]
    prepopulated_fields = {"schluessel": ("name",)}

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return ["schluessel", *(["name"] if obj.besetzungen.exists() else [])] if obj else []

    def get_prepopulated_fields(self, request, obj=None):
        return {} if obj else self.prepopulated_fields


class WechselFormular(forms.Form):
    neue_person = forms.ModelChoiceField(
        queryset=Nutzer.objects.filter(is_active=True), label="Neue Person aus dem Nutzerstamm"
    )
    wechsel_ab = forms.DateField(
        label="Wechsel ab (einschließlich)",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    ausgangsrevision = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, admin_site, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["neue_person"].widget = AutocompleteSelect(
            Funktionsbesetzung._meta.get_field("person"), admin_site
        )
        self.fields["neue_person"].widget.choices = self.fields["neue_person"].choices


@admin.register(Funktionsbesetzung)
class FunktionsbesetzungAdmin(RevisionAdmin):
    form = BesetzungsFormular
    list_display = [
        "funktion",
        "person",
        "bereich",
        "art",
        "gueltig_ab",
        "gueltig_bis",
        "vertretung_aktiv",
        "storniert",
    ]
    list_filter = ["funktion", "bereich", "art", "storniert", "vertretung_aktiv"]
    search_fields = ["funktion__name", "person__anzeigename", "person__kuerzel", "bereich__name"]
    autocomplete_fields = ["funktion", "person", "bereich"]

    def get_readonly_fields(self, request, obj=None):
        return [
            *self.readonly_fields,
            "wechsel_link",
            *(["funktion", "person", "bereich", "art", "vertretung_aktiv"] if obj else []),
        ]

    def get_urls(self):
        return [
            path(
                "<int:object_id>/wechseln/",
                self.admin_site.admin_view(self.wechseln),
                name="kern_funktionsbesetzung_wechseln",
            ),
            *super().get_urls(),
        ]

    @admin.display(description="Personalwechsel")
    def wechsel_link(self, obj):
        if not obj or not obj.pk or obj.storniert:
            return "Erst besetzen; Korrekturen bleiben in der Historie erhalten."
        return format_html(
            '<a href="{}">Besetzung wechseln …</a>',
            reverse("admin:kern_funktionsbesetzung_wechseln", args=[obj.pk]),
        )

    def wechseln(self, request, object_id):
        if not rechte.ist_administration(request.user):
            raise PermissionDenied("Besetzungen verwaltet die Administration.")
        obj = self.get_object(request, str(object_id))
        if obj is None:
            raise Http404("Diese Besetzung gibt es nicht.")
        if not self.has_change_permission(request, obj):
            raise PermissionDenied("Die Verwaltungsberechtigung fehlt.")
        formular = WechselFormular(
            request.POST if request.method == "POST" else None,
            admin_site=self.admin_site,
            initial={"ausgangsrevision": obj.revision},
        )
        if request.method == "POST" and formular.is_valid():
            try:
                neu = funktionen.wechseln(
                    obj,
                    formular.cleaned_data["neue_person"],
                    formular.cleaned_data["wechsel_ab"],
                    autor=request.user,
                    erwartete_revision=formular.cleaned_data["ausgangsrevision"],
                )
            except ValidationError as fehler:
                formular.add_error(None, " ".join(fehler.messages))
            else:
                self.log_change(
                    request, obj, "Besetzung durch Personalwechsel beendet oder korrigiert."
                )
                self.log_addition(request, neu, "Nachfolgebesetzung angelegt.")
                messages.success(
                    request, "Die Besetzung wurde gewechselt. Der bisherige Stand bleibt erhalten."
                )
                return redirect("admin:kern_funktionsbesetzung_change", neu.pk)
        return TemplateResponse(
            request,
            "admin/kern/funktionswechsel.html",
            {
                **self.admin_site.each_context(request),
                "title": "Besetzung wechseln",
                "opts": self.model._meta,
                "original": obj,
                "formular": formular,
                "media": formular.media,
            },
        )


@admin.register(Funktionsstand)
class FunktionsstandAdmin(AdministrationsMixin, admin.ModelAdmin):
    list_display = ["funktion", "besetzung", "revision", "zeitpunkt", "autor"]
    list_filter = ["funktion"]
    readonly_fields = [f.name for f in Funktionsstand._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
