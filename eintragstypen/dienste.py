"""Der gemeinsame Schreibweg für Einträge.

Maske, XLSX-Import und – ab Phase 3 – der generische JSON-Import benutzen
dieselben zwei Funktionen:

``pruefen()``   bewertet einen Datensatz, ohne etwas zu schreiben. Das ist die
                Grundlage der Import-Vorschau (SPEC.md §11).
``speichern()`` schreibt einen geprüften Datensatz, legt die Verlinkungen an,
                baut den Suchtext und schreibt eine neue Fassung fort.

Dadurch gilt überall dieselbe Prüfung, und ein weiterer Importweg ist wenig
zusätzlicher Code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.contrib.postgres.search import SearchVector
from django.db import transaction

from eintragstypen import html
from eintragstypen.registry import Feldtyp, registry
from kern.models import Eintrag, Status, Verlinkung, Zieltyp

FEHLER = "fehler"
WARNUNG = "warnung"
HINWEIS = "hinweis"


@dataclass
class Befund:
    """Eine Beobachtung zu einem Datensatz – für die Vorschau."""

    schwere: str
    text: str
    feld: str = ""

    @property
    def ist_fehler(self) -> bool:
        return self.schwere == FEHLER


@dataclass
class Rohsatz:
    """Ein Datensatz, wie er aus Maske, Arbeitsmappe oder JSON kommt."""

    kennung: str
    eintragstyp: str
    titel: str = ""
    status: str = Status.ENTWURF
    daten: dict = field(default_factory=dict)
    #: Feldschlüssel -> Liste von Ziel-Kennungen, z. B.
    #: ``{"kompetenzen_schwerpunkt": ["SC2.02D"], "bezug_rituale": ["R-01"]}``
    verweise: dict[str, list[str]] = field(default_factory=dict)
    verantwortlich_text: str = ""
    fassung_stand: object = None
    quelle: str = ""
    """Woher der Satz kommt, z. B. „Vorhaben Zeile 2“ – erscheint in der Vorschau."""


@dataclass
class Befundsatz:
    """Das Ergebnis von ``pruefen()``."""

    roh: Rohsatz
    daten: dict = field(default_factory=dict)
    verweise: dict[str, list[str]] = field(default_factory=dict)
    befunde: list[Befund] = field(default_factory=list)
    ist_neu: bool = True
    fehlende_pflichtfelder: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Darf geschrieben werden? Warnungen stehen dem nicht entgegen."""
        return not any(b.ist_fehler for b in self.befunde)

    @property
    def fehler(self) -> list[Befund]:
        return [b for b in self.befunde if b.ist_fehler]

    @property
    def warnungen(self) -> list[Befund]:
        return [b for b in self.befunde if not b.ist_fehler]


# --- Prüfen ----------------------------------------------------------------


def pruefen(dokument, roh: Rohsatz, entstehende_kennungen: set[str] | None = None) -> Befundsatz:
    """Bewertet einen Datensatz, ohne zu schreiben.

    ``entstehende_kennungen`` sind Kennungen, die im selben Importlauf erst noch
    angelegt werden. Ein Verweis darauf ist kein Fehler – sonst müsste jede
    Arbeitsmappe schon vollständig in der Datenbank stehen, um geprüft werden
    zu können.
    """
    ergebnis = Befundsatz(roh=roh)

    if not registry.bekannt(roh.eintragstyp):
        ergebnis.befunde.append(
            Befund(FEHLER, f"Unbekannter Eintragstyp „{roh.eintragstyp}“.", "eintragstyp")
        )
        return ergebnis
    typ = registry.holen(roh.eintragstyp)

    erlaubt = dokument.dokumenttyp.eintragstypen or []
    if erlaubt and roh.eintragstyp not in erlaubt:
        ergebnis.befunde.append(
            Befund(
                FEHLER,
                f"Der Eintragstyp „{typ.name}“ ist im Dokumenttyp "
                f"„{dokument.dokumenttyp.name}“ nicht vorgesehen.",
                "eintragstyp",
            )
        )

    if not roh.kennung:
        ergebnis.befunde.append(Befund(FEHLER, "Die Kennung fehlt.", "kennung"))
    if not roh.titel:
        ergebnis.befunde.append(Befund(FEHLER, "Der Titel fehlt.", "titel"))

    vorhanden = dokument.eintraege.filter(kennung=roh.kennung).first()
    ergebnis.ist_neu = vorhanden is None
    if vorhanden is not None:
        ergebnis.befunde.append(
            Befund(
                HINWEIS,
                f"„{roh.kennung}“ gibt es schon („{vorhanden.titel}“) und wird aktualisiert.",
                "kennung",
            )
        )
        if vorhanden.eintragstyp != roh.eintragstyp:
            ergebnis.befunde.append(
                Befund(
                    FEHLER,
                    f"„{roh.kennung}“ ist bereits ein anderer Eintragstyp "
                    f"({vorhanden.eintragstyp}). Kennungen werden nie neu vergeben.",
                    "kennung",
                )
            )

    if roh.status not in Status.values:
        ergebnis.befunde.append(Befund(FEHLER, f"Unbekannter Status „{roh.status}“.", "status"))
    elif roh.status in (Status.BESCHLOSSEN, Status.ARCHIVIERT):
        ergebnis.befunde.append(
            Befund(
                WARNUNG,
                "„beschlossen“ entsteht nur über einen Beschluss. Der Satz wird als "
                "„abgestimmt in Gruppe“ übernommen.",
                "status",
            )
        )

    daten, feldfehler = typ.daten_pruefen(roh.daten)
    ergebnis.daten = daten
    for schluessel, meldung in feldfehler.items():
        feld = typ.feld(schluessel)
        ergebnis.befunde.append(
            Befund(FEHLER, f"{feld.label if feld else schluessel}: {meldung}", schluessel)
        )

    ergebnis.verweise = _verweise_pruefen(
        dokument, typ, roh, ergebnis, entstehende_kennungen or set()
    )

    gefuellte_verweise = {s for s, ziele in ergebnis.verweise.items() if ziele}
    if vorhanden is not None:
        # Felder, die dieser Datensatz nicht nennt, behalten ihre Verweise –
        # also zählen sie weiter als gefüllt.
        unberuehrt = {f.schluessel for f in typ.verlinkungsfelder} - set(ergebnis.verweise)
        gefuellte_verweise |= {
            feld
            for feld in vorhanden.verlinkungen.filter(feld__in=unberuehrt)
            .values_list("feld", flat=True)
            .distinct()
        }

    ergebnis.fehlende_pflichtfelder = typ.fehlende_pflichtfelder(daten, gefuellte_verweise)
    if ergebnis.fehlende_pflichtfelder:
        namen = ", ".join(f.label for f in ergebnis.fehlende_pflichtfelder)
        # Kein Fehler: als Entwurf speichern muss immer gehen (SPEC.md §7.4).
        ergebnis.befunde.append(Befund(WARNUNG, f"Noch offene Pflichtfelder: {namen}.", ""))

    return ergebnis


def _verweise_pruefen(
    dokument, typ, roh: Rohsatz, ergebnis: Befundsatz, entstehende: set[str]
) -> dict:
    """Löst Ziel-Kennungen auf und meldet, was es nicht gibt."""
    from fachdaten.models import Kompetenzerwartung

    aufgeloest: dict[str, list[str]] = {}
    unbekannte_felder = set(roh.verweise) - {f.schluessel for f in typ.verlinkungsfelder}
    for schluessel in sorted(unbekannte_felder):
        ergebnis.befunde.append(
            Befund(FEHLER, f"Das Verweisfeld „{schluessel}“ gibt es in „{typ.name}“ nicht.")
        )

    for feld in typ.verlinkungsfelder:
        if feld.schluessel not in roh.verweise:
            # Ein Feld, das der Datensatz gar nicht nennt, bleibt unberührt.
            # Nur so kann ein Teil-Datensatz gespeichert werden, ohne die
            # übrigen Verweise zu löschen.
            continue
        ziele = [
            str(z).strip() for z in (roh.verweise.get(feld.schluessel) or []) if str(z).strip()
        ]
        if not ziele:
            aufgeloest[feld.schluessel] = []
            continue

        gesehen: list[str] = []
        for ziel in ziele:
            if ziel in gesehen:
                ergebnis.befunde.append(
                    Befund(WARNUNG, f"{feld.label}: „{ziel}“ steht doppelt.", feld.schluessel)
                )
                continue
            gesehen.append(ziel)

        if feld.zieltyp == Zieltyp.KOMPETENZ:
            bekannt = set(
                Kompetenzerwartung.objects.filter(
                    pk__in=gesehen, **({"fach": dokument.fach} if dokument.fach else {})
                ).values_list("pk", flat=True)
            )
            for ziel in gesehen:
                if ziel not in bekannt:
                    ergebnis.befunde.append(
                        Befund(
                            FEHLER,
                            f"{feld.label}: Die Kompetenz-Kennung „{ziel}“ gibt es nicht. "
                            "Sind die Stammdaten importiert?",
                            feld.schluessel,
                        )
                    )
            aufgeloest[feld.schluessel] = [z for z in gesehen if z in bekannt]

        elif feld.zieltyp == Zieltyp.EINTRAG:
            treffer = set(
                dokument.eintraege.filter(kennung__in=gesehen).values_list("kennung", flat=True)
            )
            gueltig = treffer | entstehende
            for ziel in gesehen:
                if ziel not in gueltig:
                    ergebnis.befunde.append(
                        Befund(
                            FEHLER,
                            f"{feld.label}: „{ziel}“ gibt es in diesem Dokument nicht.",
                            feld.schluessel,
                        )
                    )
            aufgeloest[feld.schluessel] = [z for z in gesehen if z in gueltig]

        else:
            aufgeloest[feld.schluessel] = gesehen

    return aufgeloest


# --- Schreiben -------------------------------------------------------------


@transaction.atomic
def speichern(dokument, befundsatz: Befundsatz, nutzer=None, eltern=None) -> Eintrag:
    """Schreibt einen geprüften Datensatz und legt eine neue Fassung an."""
    if not befundsatz.ok:
        meldungen = "; ".join(b.text for b in befundsatz.fehler)
        raise ValueError(f"Datensatz hat Fehler und wird nicht geschrieben: {meldungen}")

    roh = befundsatz.roh
    typ = registry.holen(roh.eintragstyp)

    status = roh.status
    if status in (Status.BESCHLOSSEN, Status.ARCHIVIERT):
        # Gültigkeit entsteht ausschließlich über einen Beschluss (SPEC.md §8).
        status = Status.ABGESTIMMT

    eintrag = dokument.eintraege.filter(kennung=roh.kennung).first()
    if eintrag is None:
        eintrag = Eintrag(dokument=dokument, kennung=roh.kennung, erstellt_von=nutzer)
    elif eintrag.ist_beschlossen:
        # Die beschlossene Fassung bleibt als Version erhalten; der Arbeitsstand
        # wird wieder ein Entwurf (SPEC.md §6 „Eintragsversion“).
        status = Status.ENTWURF

    eintrag.eintragstyp = roh.eintragstyp
    eintrag.titel = roh.titel
    eintrag.status = status
    eintrag.daten = befundsatz.daten
    if roh.verantwortlich_text:
        eintrag.verantwortlich_text = roh.verantwortlich_text
    if eintrag.verantwortlich_gruppe_id is None:
        gruppe = _arbeitsgruppe_erraten(eintrag, roh, befundsatz.daten)
        if gruppe is not None:
            eintrag.verantwortlich_gruppe = gruppe
    if roh.fassung_stand:
        eintrag.fassung_stand = roh.fassung_stand
    if eltern is not None and eintrag.eltern_id is None:
        eintrag.eltern = eltern
    if not eintrag.position:
        eintrag.position = _naechste_position(dokument, eintrag.eltern)
    eintrag.save()

    _verlinkungen_setzen(eintrag, typ, befundsatz.verweise)
    suchtext_aktualisieren(eintrag)
    eintrag.version_anlegen(autor=nutzer)
    return eintrag


def _arbeitsgruppe_erraten(eintrag, roh: Rohsatz, daten: dict):
    """Welche Arbeitsgruppe ist für diesen Eintrag verantwortlich?

    Ohne Zuordnung dürfte niemand aus dem Kollegium einen importierten Eintrag
    bearbeiten – nur die Redaktion. Darum zwei Versuche:

    1. Steht in der Spalte „Verantwortlich" der Name einer Arbeitsgruppe,
       wird diese genommen.
    2. Hat ein Vorhaben einen Jahrgang, übernimmt die Arbeitsgruppe
       „Jahrgang N", sofern es sie gibt. So arbeitet die Schule auch.

    Findet sich nichts, bleibt das Feld leer und die Redaktion ordnet zu.
    """
    from django.contrib.auth.models import Group

    from kern.models import Gruppenart

    arbeitsgruppen = Group.objects.filter(profil__art=Gruppenart.ARBEITSGRUPPE)

    name = (roh.verantwortlich_text or "").strip()
    if name:
        treffer = arbeitsgruppen.filter(name__iexact=name).first()
        if treffer is not None:
            return treffer

    jahrgang = daten.get("jahrgang")
    if jahrgang:
        return arbeitsgruppen.filter(name__iexact=f"Jahrgang {jahrgang}").first()

    return None


def _naechste_position(dokument, eltern) -> int:
    from django.db.models import Max

    hoechste = dokument.eintraege.filter(eltern=eltern).aggregate(m=Max("position")).get("m") or 0
    return hoechste + 10


def _verlinkungen_setzen(eintrag: Eintrag, typ, verweise: dict) -> None:
    """Bringt die Verlinkungen der Verweisfelder auf den übergebenen Stand.

    Nur die Felder, die wirklich übergeben wurden, werden angefasst – so kann
    eine Maske einzelne Blöcke speichern, ohne andere Verweise zu verlieren.
    """
    from fachdaten.models import Kompetenzerwartung

    for feld in typ.verlinkungsfelder:
        if feld.schluessel not in verweise:
            continue
        ziele = verweise[feld.schluessel]

        beschriftungen: dict[str, str] = {}
        ziel_ids: list[str] = []

        if feld.zieltyp == Zieltyp.KOMPETENZ:
            ziel_ids = list(ziele)
            beschriftungen = dict(
                Kompetenzerwartung.objects.filter(pk__in=ziele).values_list("pk", "text")
            )
        elif feld.zieltyp == Zieltyp.EINTRAG:
            # Als Ziel wird der Primärschlüssel gespeichert, die Kennung als
            # Beschriftung: so bleibt der Verweis auch dann eindeutig, wenn ein
            # Eintrag später umbenannt wird.
            for andere in eintrag.dokument.eintraege.filter(kennung__in=ziele):
                ziel_ids.append(str(andere.pk))
                beschriftungen[str(andere.pk)] = f"{andere.kennung} {andere.titel}".strip()
        else:
            ziel_ids = list(ziele)

        eintrag.verlinkungen.filter(art=feld.verlinkungsart, feld=feld.schluessel).exclude(
            ziel_id__in=ziel_ids
        ).delete()
        for ziel_id in ziel_ids:
            Verlinkung.objects.update_or_create(
                von_eintrag=eintrag,
                ziel_typ=feld.zieltyp,
                ziel_id=ziel_id,
                art=feld.verlinkungsart,
                defaults={
                    "feld": feld.schluessel,
                    "beschriftung": (beschriftungen.get(ziel_id) or "")[:250],
                },
            )


def suchtext_bauen(eintrag: Eintrag) -> str:
    """Alles, was zu diesem Eintrag durchsuchbar sein soll, als Klartext."""
    typ = registry.holen(eintrag.eintragstyp)
    teile: list[str] = [eintrag.kennung, eintrag.titel]

    for feld in typ.datenfelder:
        wert = eintrag.daten.get(feld.schluessel)
        if wert in (None, "", []):
            continue
        if feld.typ == Feldtyp.RICHTEXT:
            teile.append(html.als_text(str(wert)))
        elif feld.typ in (Feldtyp.TEXT, Feldtyp.LANGTEXT, Feldtyp.AUSWAHL):
            teile.append(feld.anzeige(wert))

    # Kompetenzkennungen und ihre Klartexte mit aufnehmen: so findet die Suche
    # nach „SC2.02D“ ebenso wie die nach einem Wort aus der Erwartung.
    for verlinkung in eintrag.verlinkungen.all():
        teile.append(verlinkung.ziel_id if verlinkung.ziel_typ == Zieltyp.KOMPETENZ else "")
        teile.append(verlinkung.beschriftung)

    for anhang in eintrag.anhaenge.all():
        teile.append(anhang.dateiname)
        teile.append(anhang.beschreibung)
        teile.append(anhang.extrahierter_text)

    # Wird an einem beschlossenen Eintrag weitergearbeitet, zeigt die App
    # Lesenden weiter die beschlossene Fassung. Dann muss diese auch auffindbar
    # sein – sonst findet man nicht, was man sieht.
    beschlossen = eintrag.beschlossene_version()
    if beschlossen is not None and beschlossen.daten != eintrag.daten:
        teile.append(beschlossen.titel)
        for feld in typ.datenfelder:
            wert = (beschlossen.daten or {}).get(feld.schluessel)
            if wert in (None, "", []):
                continue
            if feld.typ == Feldtyp.RICHTEXT:
                teile.append(html.als_text(str(wert)))
            elif feld.typ in (Feldtyp.TEXT, Feldtyp.LANGTEXT, Feldtyp.AUSWAHL):
                teile.append(feld.anzeige(wert))

    return " ".join(t for t in teile if t).strip()


def suchtext_aktualisieren(eintrag: Eintrag) -> None:
    """Schreibt Suchtext und Suchvektor fort (deutsche Stammformen)."""
    text = suchtext_bauen(eintrag)
    Eintrag.objects.filter(pk=eintrag.pk).update(suchtext=text)
    Eintrag.objects.filter(pk=eintrag.pk).update(
        suchvektor=(
            SearchVector("kennung", weight="A", config="german")
            + SearchVector("titel", weight="A", config="german")
            + SearchVector("suchtext", weight="B", config="german")
        )
    )
    eintrag.suchtext = text
