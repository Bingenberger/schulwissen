"""Kompetenzerwartungen aus der App heraus exportieren und importieren.

Der Export nimmt genau die Auswahl, die in der Übersicht gerade zu sehen ist –
also auch Fach, Bereich, Stufe und Suchbegriff. Wer eine Tabelle für die
Fachkonferenz Mathematik braucht, filtert und lädt herunter.

Der Import geht in zwei Schritten: hochladen und prüfen, dann übernehmen.
Geschrieben wird erst beim zweiten Schritt, und auch dann wird die Datei noch
einmal vollständig geprüft. Bei einem Fehler wird nichts geschrieben.
"""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.text import slugify

from fachdaten import exporte, importe
from fachdaten.models import Fach
from fachdaten.suche import kompetenzen_finden
from kern import rechte

#: Mehr als das ist keine Kompetenzdatei mehr.
HOECHSTGROESSE = 5 * 1024 * 1024
ENDUNGEN = (".json", ".xlsx", ".csv")


def _auswahl(request):
    """Dieselbe Auswahl wie in der Übersicht."""
    fach = (request.GET.get("fach") or "deutsch").strip()
    return (
        kompetenzen_finden(
            (request.GET.get("q") or "").strip(),
            bereich=(request.GET.get("bereich") or "").strip(),
            stufe=(request.GET.get("stufe") or "").strip(),
            fach=fach,
        ),
        fach,
    )


@login_required
def export(request, format):
    if format not in exporte.FORMATE:
        raise Http404("Dieses Format gibt es nicht.")
    bauen, mimetype, endung = exporte.FORMATE[format]
    erwartungen, fach = _auswahl(request)
    name = slugify(fach) or "kompetenzerwartungen"
    antwort = HttpResponse(bauen(erwartungen), content_type=mimetype)
    antwort["Content-Disposition"] = f'attachment; filename="kompetenzerwartungen-{name}.{endung}"'
    return antwort


class KompetenzimportFormular(forms.Form):
    fach = forms.ChoiceField(label="Fach", choices=())
    modus = forms.ChoiceField(
        label="Was soll geschrieben werden?",
        choices=importe.MODI,
        initial=importe.MODUS_FESTLEGUNGEN,
        widget=forms.RadioSelect,
        help_text="„Lehrplandaten“ lässt die schulischen Festlegungen unberührt, "
        "„nur schulische Festlegungen“ lässt die Lehrplanangaben unberührt.",
    )
    datei = forms.FileField(
        label="Datei",
        required=False,
        help_text="JSON, XLSX oder CSV – am einfachsten eine hier exportierte Datei.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fach"].choices = [
            (f.schluessel, f.name) for f in Fach.objects.order_by("name")
        ]

    def clean_datei(self):
        datei = self.cleaned_data.get("datei")
        if datei is None:
            return None
        if datei.size > HOECHSTGROESSE:
            raise forms.ValidationError("Die Datei darf höchstens 5 MB groß sein.")
        if not datei.name.lower().endswith(ENDUNGEN):
            raise forms.ValidationError("Bitte eine Datei mit Endung .json, .xlsx oder .csv.")
        return datei


#: Wo die geprüfte Datei zwischen „prüfen“ und „übernehmen“ liegt. Nicht im
#: Formular: eine XLSX-Datei gehört nicht als verstecktes Feld in die Seite.
SITZUNGSSCHLUESSEL = "kompetenzimport"

#: So viele Zeilen hat keine Kompetenzdatei – darüber wird nicht gepuffert.
HOECHSTZAHL_ZEILEN = 5000


@login_required
def kompetenzimport(request):
    if not rechte.darf_importieren(request.user):
        raise PermissionDenied("Kompetenzdaten importiert die Administration.")
    gepuffert = request.session.get(SITZUNGSSCHLUESSEL) or {}
    formular = KompetenzimportFormular(
        request.POST or None,
        request.FILES or None,
        initial={
            "fach": gepuffert.get("fach", "deutsch"),
            "modus": gepuffert.get("modus", importe.MODUS_FESTLEGUNGEN),
        },
    )
    bericht = None
    if request.method == "POST" and formular.is_valid():
        datei = formular.cleaned_data["datei"]
        fach = formular.cleaned_data["fach"]
        modus = formular.cleaned_data["modus"]
        uebernehmen = request.POST.get("aktion") == "uebernehmen"
        saetze = None
        if datei is not None:
            # Eine neue Datei löst die vorige Prüfung ab – sonst stünde der
            # Knopf „Übernehmen“ für eine Datei, die nicht mehr gemeint ist.
            request.session.pop(SITZUNGSSCHLUESSEL, None)
            try:
                saetze = importe.saetze_aus_daten(datei.name, datei.read())
            except (ValueError, OSError, KeyError, TypeError) as fehler:
                formular.add_error("datei", f"Die Datei ist nicht lesbar: {fehler}")
            else:
                if len(saetze) > HOECHSTZAHL_ZEILEN:
                    formular.add_error(
                        "datei", f"Mehr als {HOECHSTZAHL_ZEILEN} Zeilen sind zu viele."
                    )
                    saetze = None
                else:
                    # Eine neue Datei geht zuerst in die Prüfung.
                    uebernehmen = False
        elif uebernehmen and gepuffert.get("saetze") is not None:
            saetze, fach, modus = (
                gepuffert["saetze"],
                gepuffert["fach"],
                gepuffert["modus"],
            )
        else:
            formular.add_error("datei", "Bitte eine Datei auswählen.")

        if saetze is not None:
            bericht = importe.importieren(
                saetze, fach=fach, nur_pruefen=not uebernehmen, modus=modus
            )
            if uebernehmen and bericht.ok:
                request.session.pop(SITZUNGSSCHLUESSEL, None)
                messages.success(request, _rueckmeldung(bericht))
                ziel = reverse("fachdaten:uebersicht")
                return redirect(f"{ziel}?{urlencode({'fach': fach})}")
            if bericht.ok:
                request.session[SITZUNGSSCHLUESSEL] = {
                    "saetze": saetze,
                    "fach": fach,
                    "modus": modus,
                    "dateiname": datei.name if datei else gepuffert.get("dateiname", ""),
                }
            else:
                request.session.pop(SITZUNGSSCHLUESSEL, None)
    return render(
        request,
        "fachdaten/import.html",
        {
            "formular": formular,
            "bericht": bericht,
            "modus_festlegungen": importe.MODUS_FESTLEGUNGEN,
            "geprueft": (request.session.get(SITZUNGSSCHLUESSEL) or {}).get("dateiname"),
        },
    )


def _rueckmeldung(bericht) -> str:
    if bericht.modus == importe.MODUS_FESTLEGUNGEN:
        return (
            f"{bericht.festlegungen} schulische Festlegung"
            f"{'en' if bericht.festlegungen != 1 else ''} übernommen."
        )
    return (
        f"{bericht.angelegt} Kompetenzerwartungen neu, {bericht.aktualisiert} aktualisiert, "
        f"{bericht.unveraendert} unverändert."
    )
