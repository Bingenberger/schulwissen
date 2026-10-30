"""Auswertungen des Arbeitsplans Deutsch (SPEC.md §7.5)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from deutsch import auswertungen
from deutsch.auswertungen import abdeckungsmatrix, pruefliste
from kern.models import Dokument


@login_required
def abdeckung(request, schluessel: str):
    """Auswertung 7.5.1: Abdeckungsmatrix."""
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    nur_beschlossene = request.GET.get("stand") == "beschlossen"
    matrix = abdeckungsmatrix(dokument, nur_beschlossene=nur_beschlossene)

    return render(
        request,
        "deutsch/abdeckung.html",
        {
            "dokument": dokument,
            "matrix": matrix,
            "nur_beschlossene": nur_beschlossene,
        },
    )


@login_required
def pruefen(request, schluessel: str):
    """Auswertung 7.5.7: Prüfliste."""
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    listen = pruefliste(fach=dokument.fach or "deutsch")

    return render(
        request,
        "deutsch/pruefliste.html",
        {
            "dokument": dokument,
            "stufe_pruefen": listen["stufe_pruefen"],
            "festlegung_fehlt": listen["festlegung_fehlt"],
        },
    )


@login_required
def fahrplan(request, schluessel: str, jahrgang: int):
    """Auswertung 7.5.2: Fahrplan je Jahrgang."""
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    nur_beschlossene = request.GET.get("stand") == "beschlossen"

    return render(
        request,
        "deutsch/fahrplan.html",
        {
            "dokument": dokument,
            "jahrgang": jahrgang,
            "plan": auswertungen.fahrplan(dokument, jahrgang, nur_beschlossene),
            "nur_beschlossene": nur_beschlossene,
        },
    )


@login_required
def ritualprogression(request, schluessel: str):
    """Auswertung 7.5.3: ein Ritual mit Jahrgang 1 bis 4 nebeneinander."""
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    nur_beschlossene = request.GET.get("stand") == "beschlossen"

    return render(
        request,
        "deutsch/ritualprogression.html",
        {
            "dokument": dokument,
            "progressionen": auswertungen.ritualprogressionen(dokument, nur_beschlossene),
            "nur_beschlossene": nur_beschlossene,
        },
    )


@login_required
def zeitbudget(request, schluessel: str):
    """Auswertung 7.5.4: Zeitbudget der Rituale."""
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    nur_beschlossene = request.GET.get("stand") == "beschlossen"

    return render(
        request,
        "deutsch/zeitbudget.html",
        {
            "dokument": dokument,
            "budget": auswertungen.zeitbudget(dokument, nur_beschlossene),
            "nur_beschlossene": nur_beschlossene,
            "stunde_minuten": auswertungen.STUNDE_MINUTEN,
        },
    )


@login_required
def leistungsuebersicht(request, schluessel: str):
    """Auswertung 7.5.5: die Sicht „Leistungskonzept“."""
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    nur_beschlossene = request.GET.get("stand") == "beschlossen"

    return render(
        request,
        "deutsch/leistung.html",
        {
            "dokument": dokument,
            "uebersicht": auswertungen.leistungsuebersicht(dokument, nur_beschlossene),
            "nur_beschlossene": nur_beschlossene,
        },
    )


@login_required
def progressionspaare(request, schluessel: str):
    """Auswertung 7.5.6: S- und K-Erwartung nebeneinander."""
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    nur_beschlossene = request.GET.get("stand") == "beschlossen"
    paare = auswertungen.progressionspaare(dokument, nur_beschlossene)

    return render(
        request,
        "deutsch/progressionspaare.html",
        {
            "dokument": dokument,
            "paare": paare,
            "mit_luecke": [p for p in paare if not p.beide_abgedeckt],
            "nur_beschlossene": nur_beschlossene,
        },
    )
