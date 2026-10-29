"""Auswertungen des Arbeitsplans Deutsch (SPEC.md §7.5)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

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
