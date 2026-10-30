"""Kompetenzauswahl: Suche mit Autovervollständigung (SPEC.md §7.4)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from fachdaten.faecher import bereiche_fuer
from fachdaten.models import STUFEN_JE_JAHRGANG, Fach, Stufe
from fachdaten.suche import kompetenzen_finden

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

    treffer = kompetenzen_finden(
        begriff if len(begriff) >= MINDESTLAENGE else "",
        bereich=bereich,
        stufe=stufe,
        fach=request.GET.get("fach") or "deutsch",
    )

    vorgeschlagene_stufen: tuple[str, ...] = ()
    if jahrgang.isdigit():
        vorgeschlagene_stufen = STUFEN_JE_JAHRGANG.get(int(jahrgang), ())

    if len(begriff) < MINDESTLAENGE and vorgeschlagene_stufen and not stufe:
        # Ohne Suchbegriff: die zum Jahrgang passenden Stufen vorschlagen –
        # ein Vorschlag, keine Einschränkung (SPEC.md §7.4).
        treffer = treffer.filter(stufe__in=vorgeschlagene_stufen)

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

    fach = request.GET.get("fach", "deutsch")
    erwartungen = kompetenzen_finden(
        begriff, bereich=bereich, stufe=stufe, fach=fach
    ).select_related("progressionspartner")

    return render(
        request,
        "fachdaten/uebersicht.html",
        {
            "erwartungen": erwartungen,
            "bereiche": bereiche_fuer(fach),
            "faecher": Fach.objects.all(),
            "fach": fach,
            "fachname": Fach.objects.filter(schluessel=fach).values_list("name", flat=True).first()
            or "alle Fächer",
            "stufen": Stufe.choices,
            "bereich": bereich,
            "stufe": stufe,
            "begriff": begriff,
            "anzahl": erwartungen.count(),
        },
    )
