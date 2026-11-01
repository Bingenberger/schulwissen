"""Kompetenzauswahl und Nachschlagewerk (SPEC.md §7.4)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils.http import urlencode

from fachdaten.faecher import bereiche_fuer
from fachdaten.models import STUFEN_JE_JAHRGANG, Fach, Kompetenzerwartung, Stufe
from fachdaten.suche import kompetenzen_finden
from kern import rechte

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


def _gruppieren(erwartungen, bereiche):
    """Nach Bereich und Schwerpunkt gliedern – wie im Lehrplan gedruckt.

    Eine Liste aus 136 Zeilen ist keine Hilfe. Der Lehrplan selbst ordnet nach
    Bereich und Schwerpunkt; danach sucht eine Lehrkraft auch. Die Reihenfolge
    der Bereiche ist die des Lehrplans (so stehen sie im Fach hinterlegt),
    nicht die alphabetische ihrer Kürzel.
    """
    reihenfolge = {kuerzel: nummer for nummer, (kuerzel, _) in enumerate(bereiche)}
    sortiert = sorted(
        erwartungen,
        key=lambda e: (reihenfolge.get(e.bereich, 99), e.schwerpunkt_nr, e.pk),
    )
    gruppen: list[dict] = []
    for erwartung in sortiert:
        schluessel = (erwartung.bereich, erwartung.schwerpunkt_nr)
        if not gruppen or gruppen[-1]["schluessel"] != schluessel:
            voriger = gruppen[-1]["bereich"] if gruppen else None
            gruppen.append(
                {
                    "schluessel": schluessel,
                    "anker": f"{erwartung.bereich}-{erwartung.schwerpunkt_nr}",
                    "bereich": erwartung.bereich,
                    "bereich_name": erwartung.bereich_name,
                    # Nur beim Wechsel – sonst stünde der Bereichsname über
                    # jedem einzelnen Schwerpunkt noch einmal.
                    "neuer_bereich": erwartung.bereich != voriger,
                    "schwerpunkt": erwartung.schwerpunkt,
                    # Kunst und Musik haben keine Schwerpunkte unter den
                    # Bereichen; dort wäre die zweite Überschrift eine Doppelung.
                    "eigener_schwerpunkt": erwartung.schwerpunkt != erwartung.bereich_name,
                    "zeilen": [],
                }
            )
        gruppen[-1]["zeilen"].append(erwartung)
    return gruppen


@login_required
def kompetenz_uebersicht(request):
    """Nachschlagewerk: alle Kompetenzerwartungen mit Filtern."""
    bereich = (request.GET.get("bereich") or "").strip()
    stufe = (request.GET.get("stufe") or "").strip()
    begriff = (request.GET.get("q") or "").strip()

    faecher = list(Fach.objects.order_by("name"))
    bekannt = {f.schluessel for f in faecher}
    fach = request.GET.get("fach", "deutsch")
    if fach not in bekannt:
        fach = "deutsch" if "deutsch" in bekannt or not faecher else faecher[0].schluessel

    # Im Nachschlagewerk zählt die Gliederung des Lehrplans, nicht die
    # Treffergüte: sonst zerfiele die Gruppierung in viele Einzelzeilen.
    bereichsliste = bereiche_fuer(fach)
    erwartungen = list(
        kompetenzen_finden(begriff, bereich=bereich, stufe=stufe, fach=fach).select_related(
            "progressionspartner"
        )
    )
    gruppen = _gruppieren(erwartungen, bereichsliste)
    je_fach = {
        zeile["fach"]: zeile["anzahl"]
        for zeile in Kompetenzerwartung.objects.values("fach").annotate(anzahl=Count("pk"))
    }
    for eintrag in faecher:
        eintrag.anzahl = je_fach.get(eintrag.schluessel, 0)

    gefiltert = bool(begriff or bereich or stufe)
    return render(
        request,
        "fachdaten/uebersicht.html",
        {
            "erwartungen": erwartungen,
            "gruppen": gruppen,
            "bereiche": bereichsliste,
            "faecher": faecher,
            "fach": fach,
            "fachname": next((f.name for f in faecher if f.schluessel == fach), "alle Fächer"),
            "fachquelle": next((f.quelle for f in faecher if f.schluessel == fach), ""),
            "stufen": Stufe.choices,
            "bereich": bereich,
            "stufe": stufe,
            "begriff": begriff,
            "gefiltert": gefiltert,
            "anzahl": len(erwartungen),
            "anzahl_fach": je_fach.get(fach, 0),
            "gesamt": sum(je_fach.values()),
            "offene_festlegungen": sum(1 for e in erwartungen if e.festlegung_fehlt),
            "exportparameter": urlencode(
                {
                    k: v
                    for k, v in (
                        ("fach", fach),
                        ("q", begriff),
                        ("bereich", bereich),
                        ("stufe", stufe),
                    )
                    if v
                }
            ),
            "darf_importieren": rechte.darf_importieren(request.user),
        },
    )
