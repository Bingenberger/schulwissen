"""Suchseite und Autovervollständigung."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from fachdaten.models import Fach
from kern import rechte
from kern.models import Status
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
            "dokumente": rechte.sichtbare_dokumente(request.user).order_by("titel"),
            "statuswerte": Status.choices,
            "faecher": Fach.objects.all(),
            "filter": filter_werte,
            "hat_filter": any(filter_werte.values()),
        },
    )


@login_required
def vorschlaege(request):
    """Autovervollständigung – liefert ein HTML-Schnipsel für HTMX."""
    begriff = (request.GET.get("q") or "").strip()
    gefunden = dienste.vorschlaege(request.user, begriff)
    gruppen = []
    for zusatz, name in (
        ("", "Arbeitspläne & Konzepte"),
        ("Beschluss", "Beschlüsse"),
        ("Kompetenz", "Kompetenzen"),
    ):
        treffer = [t for t in gefunden if t.zusatz == zusatz]
        if treffer:
            gruppen.append({"name": name, "treffer": treffer})
    if len(begriff) >= dienste.MINDESTLAENGE and len(gefunden) < 8:
        dateien = dienste.suchen(request.user, begriff, gruppe="dateien").gefuellte_gruppen
        if dateien:
            treffer = dateien[0].treffer[: 8 - len(gefunden)]
            gruppen.append({"name": "Dateien", "treffer": treffer})
            gefunden.extend(treffer)
    return render(
        request,
        "suche/_vorschlaege.html",
        {
            "begriff": begriff,
            "vorschlaege": gefunden,
            "vorschlagsgruppen": gruppen,
            "zu_kurz": 0 < len(begriff) < dienste.MINDESTLAENGE,
        },
    )
