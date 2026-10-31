"""Aufgabenbezogenes Schulhandbuch und Formularverzeichnis aus gültigen Fassungen."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import reverse

from kern import dateifassungen, funktionen, prozessdaten, rechte, wissenspflege
from kern.models import (
    AUFGABENBEREICHE,
    Eintrag,
    Funktionsbereich,
    Schulfunktion,
    Status,
)
from kern.staende import gueltige_versionen, lesemenge


def kanonisch():
    """Auch bei geänderter Inhaltsart im Entwurf bleibt die alte Formularquelle maßgeblich."""
    return Eintrag.objects.filter(
        Q(dokument__dokumenttyp__schluessel="schulhandbuch")
        | Q(
            pk__in=gueltige_versionen()
            .filter(Q(inhaltsart="formular") | ~Q(aufgabe=""))
            .values("eintrag_id")
        )
    )


def menge(nutzer, nur_formulare=False):
    ergebnis = lesemenge(nutzer, kanonisch(), nur_beschlossene=True).select_related("dokument")
    return ergebnis.filter(lese_inhaltsart="formular") if nur_formulare else ergebnis


def suchen(menge, begriff):
    from kern.prozesse import suchen as prozesse_suchen

    if not begriff:
        return menge
    gefunden = prozesse_suchen(menge, begriff)
    rollen = Schulfunktion.objects.filter(name__icontains=begriff).values("pk")
    pflegeversionen = gueltige_versionen().filter(pflege_funktion__in=rollen).values("pk")
    return menge.filter(Q(pk__in=gefunden.values("pk")) | Q(_leseversion__in=pflegeversionen))


def leselink(e):
    version = e.beschlossene_version()
    return reverse("kern:version", args=[e.dokument.schluessel, e.kennung, version.versionsnummer])


def kontakte(version):
    """Pflegefunktion und Handlungsschritte auseinanderhalten; keine Bereichsersatzbesetzung."""
    ergebnis = []
    if version.pflege_funktion:
        ergebnis.append(
            {"art": "Pflegeverantwortung", **wissenspflege.kontakt(version.pflege_funktion)}
        )
    if version.eintrag.eintragstyp != "prozess":
        return ergebnis
    try:
        graph = prozessdaten.normalisieren(version.daten.get("ablauf"))
    except ValidationError:
        return ergebnis
    keys = {(k["funktion"], k.get("bereich", "")) for k in graph["knoten"] if k.get("funktion")}
    rollen = {
        f.schluessel: f for f in Schulfunktion.objects.filter(schluessel__in={k[0] for k in keys})
    }
    bereiche = {
        b.schluessel: b
        for b in Funktionsbereich.objects.filter(schluessel__in={k[1] for k in keys if k[1]})
    }
    for key, bereich in sorted(keys):
        f = rollen.get(key)
        if not f:
            continue
        if bereich and bereich not in bereiche:
            ergebnis.append(
                {
                    "art": "Im Ablauf zuständig",
                    "name": f.name,
                    "status": "Zuständigkeitsbereich nicht verfügbar",
                    "personen": [],
                }
            )
            continue
        a = funktionen.aufloesen(f, bereich=bereiche.get(bereich))
        ergebnis.append(
            {
                "art": "Im Ablauf zuständig",
                "name": f.name + (f" · {bereiche[bereich].name}" if bereich else ""),
                "status": a.status_text,
                "personen": [
                    b.person.anzeigename or b.person.kuerzel or "Kontoname ergänzen"
                    for b in a.zustaendige
                ],
            }
        )
    return ergebnis


def formulare_zu_prozess(nutzer, version):
    ids = {v.get("ziel_id") for v in version.verlinkungen or [] if v.get("ziel_typ") == "eintrag"}
    return [
        {"titel": e.lese_titel, "url": leselink(e)}
        for e in menge(nutzer, True)
        .filter(pk__in=[int(pk) for pk in ids if str(pk).isdigit()])
        .order_by("lese_titel")
    ]


def prozessbezuege(nutzer, e):
    ziele = Q(verlinkungen__contains=[{"ziel_typ": "eintrag", "ziel_id": str(e.pk)}])
    versionen = (
        gueltige_versionen()
        .filter(
            eintrag__in=rechte.sichtbare_eintraege(
                nutzer,
                Eintrag.objects.filter(eintragstyp="prozess").exclude(status=Status.ARCHIVIERT),
            )
        )
        .filter(ziele)
        .select_related("eintrag__dokument")
        .order_by("titel", "eintrag_id")
    )
    return [
        {
            "titel": v.titel,
            "url": reverse(
                "kern:version",
                args=[v.eintrag.dokument.schluessel, v.eintrag.kennung, v.versionsnummer],
            ),
        }
        for v in versionen
    ]


def karte(nutzer, e):
    v = e.beschlossene_version()
    kopien = list(
        v.dateifassungen.select_related("original__dokument", "original__eintrag__dokument").defer(
            "inhalt"
        )
    )
    anlagen = []
    for k in kopien:
        info = dateifassungen.karte(k, nutzer)
        # A hidden source exposes neither its file name nor its type.
        if info["url"]:
            info["pdf"] = k.mimetype == "application/pdf" or k.dateiname.lower().endswith(".pdf")
            info["fassung"] = k.dateiversion
        anlagen.append(info)
    return {
        "titel": v.titel,
        "kennung": e.kennung,
        "dokument": e.dokument.titel,
        "kurzantwort": v.kurzantwort,
        "aufgabe": v.get_aufgabe_display() if v.aufgabe else "Noch nicht zugeordnet",
        "url": leselink(e),
        "version": v.versionsnummer,
        "freigegeben_am": v.freigegeben_am,
        "wirksam_ab": v.wirksam_ab,
        "wirksam_bis": v.wirksam_bis,
        "formular": v.inhaltsart == "formular",
        "prozess": e.eintragstyp == "prozess",
        "kontakte": kontakte(v),
        "anlagen": anlagen,
        "bezug": prozessbezuege(nutzer, e)
        if v.inhaltsart == "formular"
        else formulare_zu_prozess(nutzer, v)
        if e.eintragstyp == "prozess"
        else [],
    }


def formular_pruefen(version):
    if version.inhaltsart != "formular":
        return
    if not version.kurzantwort.strip():
        raise ValidationError("Für ein Formular fehlt der Verwendungszweck in der Kurzantwort.")
    if not dateifassungen.anhaenge(version).filter(verwendung="verbindlich").exists():
        raise ValidationError("Ein Formular benötigt mindestens eine verbindliche Dateifassung.")


@login_required
def verzeichnis(request, nur_formulare=False):
    begriff = (request.GET.get("q") or "").strip()[:200]
    aufgabe = request.GET.get("aufgabe", "")
    if aufgabe not in {k for k, _ in AUFGABENBEREICHE} | {"ohne"}:
        aufgabe = ""
    basis = menge(request.user, nur_formulare)
    anzahl = {
        row["lese_aufgabe"]: row["n"]
        for row in basis.values("lese_aufgabe").annotate(n=Count("pk"))
    }
    bereiche = [
        {"key": key, "name": name, "anzahl": anzahl.get(key, 0)} for key, name in AUFGABENBEREICHE
    ]
    if anzahl.get("", 0):
        bereiche.append({"key": "ohne", "name": "Noch nicht zugeordnet", "anzahl": anzahl[""]})
    treffer = suchen(basis, begriff)
    if aufgabe:
        treffer = treffer.filter(lese_aufgabe="" if aufgabe == "ohne" else aufgabe)
    seite = Paginator(treffer.order_by("lese_titel", "pk"), 12).get_page(request.GET.get("seite"))
    dokumente = (
        rechte.sichtbare_dokumente(request.user)
        .filter(dokumenttyp__schluessel="schulhandbuch")
        .order_by("titel")
        if rechte.darf_anlegen(request.user)
        else []
    )
    return render(
        request,
        "kern/handbuch.html",
        {
            "formulare": nur_formulare,
            "karten": [karte(request.user, e) for e in seite],
            "seite": seite,
            "begriff": begriff,
            "aufgabe": aufgabe,
            "bereiche": bereiche,
            "handbuecher": dokumente,
        },
    )


@login_required
def formulare(request):
    return verzeichnis(request, nur_formulare=True)
