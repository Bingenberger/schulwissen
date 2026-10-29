"""Kompetenzauswahl: Suche mit Autovervollständigung (SPEC.md §7.4)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models import Q, Value
from django.db.models.functions import Greatest
from django.shortcuts import render

from fachdaten.models import STUFEN_JE_JAHRGANG, Bereich, Kompetenzerwartung, Stufe

#: Ab so vielen Zeichen wird gesucht (SPEC.md §9).
MINDESTLAENGE = 2
HOECHSTZAHL = 40


@login_required
def kompetenz_suche(request):
    """Liefert Treffer als HTML-Schnipsel für HTMX.

    Gesucht wird über Kennung und Klartext. Für Tippfehlertoleranz sorgt
    ``pg_trgm``; eine Suche nach „SC2.02“ oder „Märchen“ findet beides.
    """
    begriff = (request.GET.get("q") or "").strip()
    bereich = (request.GET.get("bereich") or "").strip()
    stufe = (request.GET.get("stufe") or "").strip()
    jahrgang = (request.GET.get("jahrgang") or "").strip()
    bereits = {
        teil.strip()
        for teil in (request.GET.get("gewaehlt") or "").replace(";", ",").split(",")
        if teil.strip()
    }

    treffer = Kompetenzerwartung.objects.filter(fach=request.GET.get("fach") or "deutsch")
    if bereich:
        treffer = treffer.filter(bereich=bereich)
    if stufe:
        treffer = treffer.filter(stufe=stufe)

    vorgeschlagene_stufen: tuple[str, ...] = ()
    if jahrgang.isdigit():
        vorgeschlagene_stufen = STUFEN_JE_JAHRGANG.get(int(jahrgang), ())

    if len(begriff) >= MINDESTLAENGE:
        treffer = (
            treffer.annotate(
                naehe=Greatest(
                    TrigramWordSimilarity(begriff, "id"),
                    TrigramWordSimilarity(begriff, "suchtext"),
                )
            )
            .filter(Q(id__icontains=begriff) | Q(suchtext__icontains=begriff) | Q(naehe__gte=0.4))
            .order_by("-naehe", "bereich", "schwerpunkt_nr", "id")
        )
    elif vorgeschlagene_stufen:
        # Ohne Suchbegriff: die zum Jahrgang passenden Stufen vorschlagen –
        # ein Vorschlag, keine Einschränkung (SPEC.md §7.4).
        treffer = treffer.filter(stufe__in=vorgeschlagene_stufen).annotate(naehe=Value(0.0))
    else:
        treffer = treffer.annotate(naehe=Value(0.0))

    return render(
        request,
        "fachdaten/_treffer.html",
        {
            "treffer": treffer[:HOECHSTZAHL],
            "begriff": begriff,
            "zu_kurz": 0 < len(begriff) < MINDESTLAENGE,
            "bereits": bereits,
            "vorgeschlagene_stufen": vorgeschlagene_stufen,
        },
    )


@login_required
def kompetenz_uebersicht(request):
    """Nachschlagewerk: alle Kompetenzerwartungen mit Filtern."""
    bereich = (request.GET.get("bereich") or "").strip()
    stufe = (request.GET.get("stufe") or "").strip()
    begriff = (request.GET.get("q") or "").strip()

    erwartungen = Kompetenzerwartung.objects.select_related("progressionspartner")
    if bereich:
        erwartungen = erwartungen.filter(bereich=bereich)
    if stufe:
        erwartungen = erwartungen.filter(stufe=stufe)
    if begriff:
        erwartungen = erwartungen.filter(Q(id__icontains=begriff) | Q(suchtext__icontains=begriff))

    return render(
        request,
        "fachdaten/uebersicht.html",
        {
            "erwartungen": erwartungen,
            "bereiche": Bereich.choices,
            "stufen": Stufe.choices,
            "bereich": bereich,
            "stufe": stufe,
            "begriff": begriff,
            "anzahl": erwartungen.count(),
        },
    )
