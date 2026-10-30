"""Suchseite und Autovervollständigung."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from kern.models import Dokument, Status
from suche import dienste


@login_required
def suchen(request):
    """Ergebnisseite mit gruppierten Treffern (SPEC.md §9)."""
    begriff = (request.GET.get("q") or "").strip()
    filter_werte = {
        "dokument": (request.GET.get("dokument") or "").strip(),
        "status": (request.GET.get("status") or "").strip(),
        "jahrgang": (request.GET.get("jahrgang") or "").strip(),
        "fach": (request.GET.get("fach") or "").strip(),
        "gruppe": (request.GET.get("gruppe") or "").strip(),
    }

    ergebnis = dienste.suchen(request.user, begriff, **filter_werte)

    return render(
        request,
        "suche/ergebnisse.html",
        {
            "begriff": begriff,
            "ergebnis": ergebnis,
            "zu_kurz": 0 < len(begriff) < dienste.MINDESTLAENGE,
            "dokumente": Dokument.objects.order_by("titel"),
            "statuswerte": Status.choices,
            "filter": filter_werte,
            "hat_filter": any(filter_werte.values()),
        },
    )


@login_required
def vorschlaege(request):
    """Autovervollständigung – liefert ein HTML-Schnipsel für HTMX."""
    begriff = (request.GET.get("q") or "").strip()
    return render(
        request,
        "suche/_vorschlaege.html",
        {
            "begriff": begriff,
            "vorschlaege": dienste.vorschlaege(request.user, begriff),
            "zu_kurz": 0 < len(begriff) < dienste.MINDESTLAENGE,
        },
    )
