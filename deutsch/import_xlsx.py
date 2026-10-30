"""Import der Rituale und Vorhaben aus ``Datenmodell_Arbeitsplan_Deutsch.xlsx``.

Ablauf laut SPEC.md §11: erst **Vorschau mit Validierung**, dann Übernahme. Die
Vorschau schreibt nichts und zeigt unbekannte Kompetenz-Kennungen, fehlende
Pflichtfelder, ungültige Wertelisten-Werte und doppelte Kennungen.

Die Spaltenüberschriften der Arbeitsmappe sind deutsche Klartext-Labels, nicht
die Datenschlüssel. Die Zuordnung steht in den Feldschemata
(``deutsch/eintragstypen.py``, Attribut ``xlsx_spalten``), nicht hier.

Besonderheiten der Arbeitsmappe:

* Die beiden Blätter benennen manche Felder unterschiedlich.
* ``Verantwortlich (Gruppe/Person)`` und ``Fassung / Stand`` sind Kernfelder.
* Beispielzeilen sind am Zusatz „(Beispiel)“ im Titel erkennbar. SPEC.md §11
  will sie überspringen, §13 will sie importieren können – darum der Schalter
  ``mit_beispielen``.
* Rituale werden vor den Vorhaben verarbeitet, damit „Bezug zu Ritualen“
  aufgelöst werden kann.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from deutsch import gliederung
from eintragstypen.dienste import FEHLER, Befund, Befundsatz, Rohsatz, pruefen, speichern
from eintragstypen.registry import Feldtyp, registry
from kern.models import Status

#: Reihenfolge ist wichtig: Rituale zuerst, sonst zeigen die Vorhaben auf nichts.
BLAETTER = ("ritual", "vorhaben")

#: Statuswerte des Blattes „Wertelisten“ auf die Status des Kerns.
STATUS_AUS_MAPPE = {
    "idee": Status.IDEE,
    "entwurf": Status.ENTWURF,
    "abgestimmt in gruppe": Status.ABGESTIMMT,
    "abgestimmt": Status.ABGESTIMMT,
    "beschlossen": Status.BESCHLOSSEN,
    "archiviert": Status.ARCHIVIERT,
}

#: Spalten, die nicht in ``daten`` gehören, sondern in den Kern.
KERNSPALTEN = {
    "id": "kennung",
    "titel": "titel",
    "status": "status",
    "verantwortlich gruppe person": "verantwortlich_text",
    "verantwortlich": "verantwortlich_text",
    "fassung stand": "fassung_stand",
}

BEISPIEL_MARKIERUNG = "(beispiel)"


@dataclass
class Mappenbericht:
    """Ergebnis von Vorschau oder Übernahme."""

    saetze: list[Befundsatz] = field(default_factory=list)
    uebersprungen: list[str] = field(default_factory=list)
    allgemein: list[Befund] = field(default_factory=list)
    geschrieben: int = 0
    neu: int = 0

    @property
    def ok(self) -> bool:
        return not any(b.ist_fehler for b in self.allgemein) and all(s.ok for s in self.saetze)

    @property
    def anzahl_fehler(self) -> int:
        return len([b for b in self.allgemein if b.ist_fehler]) + sum(
            len(s.fehler) for s in self.saetze
        )

    @property
    def anzahl_warnungen(self) -> int:
        return sum(len(s.warnungen) for s in self.saetze)

    def als_text(self) -> str:
        zeilen: list[str] = []
        for befund in self.allgemein:
            zeilen.append(f"[{befund.schwere}] {befund.text}")
        for satz in self.saetze:
            kopf = f"{satz.roh.kennung or '(ohne Kennung)'} – {satz.roh.titel or '(ohne Titel)'}"
            marke = "neu" if satz.ist_neu else "Aktualisierung"
            zeilen.append(f"\n{kopf}  [{satz.roh.quelle}, {marke}]")
            if not satz.befunde:
                zeilen.append("    in Ordnung")
            for befund in satz.befunde:
                zeilen.append(f"    [{befund.schwere}] {befund.text}")
        if self.uebersprungen:
            zeilen.append("\nÜbersprungen (Beispielzeilen):")
            zeilen.extend(f"    {k}" for k in self.uebersprungen)
        zeilen.append(
            f"\n{len(self.saetze)} Datensätze, {self.anzahl_fehler} Fehler, "
            f"{self.anzahl_warnungen} Warnungen."
        )
        if self.geschrieben:
            zeilen.append(
                f"{self.geschrieben} geschrieben ({self.neu} neu, "
                f"{self.geschrieben - self.neu} aktualisiert)."
            )
        return "\n".join(zeilen)


# --- Arbeitsmappe lesen ----------------------------------------------------


def _zelle(wert: object) -> object:
    if isinstance(wert, str):
        geputzt = wert.strip()
        # Die Arbeitsmappe enthält Platzhalter wie „[z. B. Einstieg – Lesephase]“
        # und „[…]“. Die sind Ausfüllhilfe, kein Inhalt.
        if geputzt in {"[…]", "[...]", "-", "–"}:
            return None
        return geputzt or None
    return wert


def blatt_lesen(pfad: Path, blattname: str) -> list[dict]:
    """Liest ein Blatt als Liste von ``{Überschrift: Wert}`` samt Zeilennummer."""
    from openpyxl import load_workbook

    mappe = load_workbook(pfad, data_only=True, read_only=True)
    try:
        if blattname not in mappe.sheetnames:
            raise ValueError(
                f"Die Arbeitsmappe hat kein Blatt „{blattname}“. "
                f"Vorhanden: {', '.join(mappe.sheetnames)}."
            )
        blatt = mappe[blattname]
        zeilen = blatt.iter_rows(values_only=True)
        try:
            ueberschriften = [str(z).strip() if z is not None else "" for z in next(zeilen)]
        except StopIteration:
            return []

        saetze = []
        for nummer, zeile in enumerate(zeilen, start=2):
            werte = {
                ueberschrift: _zelle(wert)
                for ueberschrift, wert in zip(ueberschriften, zeile, strict=False)
                if ueberschrift
            }
            if not any(w is not None for w in werte.values()):
                continue
            werte["__zeile__"] = nummer
            saetze.append(werte)
        return saetze
    finally:
        mappe.close()


def _ids_trennen(wert: object) -> list[str]:
    """``"SC2.02D; LE3.05D"`` → ``["SC2.02D", "LE3.05D"]``."""
    if wert in (None, ""):
        return []
    text = str(wert).replace("\n", ";").replace(",", ";")
    return [teil.strip() for teil in text.split(";") if teil.strip()]


def _datum(wert: object) -> dt.date | None:
    if wert in (None, ""):
        return None
    if isinstance(wert, dt.datetime):
        return wert.date()
    if isinstance(wert, dt.date):
        return wert
    for muster in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return dt.datetime.strptime(str(wert).strip(), muster).date()
        except ValueError:
            continue
    return None


def zeile_zu_rohsatz(zeile: dict, typschluessel: str) -> tuple[Rohsatz, list[Befund]]:
    """Bildet eine Zeile der Arbeitsmappe auf einen Rohsatz ab."""
    from eintragstypen.registry import spalte_normalisieren

    typ = registry.holen(typschluessel)
    nummer = zeile.get("__zeile__", "?")
    befunde: list[Befund] = []

    roh = Rohsatz(
        kennung="",
        eintragstyp=typschluessel,
        quelle=f"{typ.xlsx_blatt} Zeile {nummer}",
    )

    for ueberschrift, wert in zeile.items():
        if ueberschrift == "__zeile__":
            continue
        normal = spalte_normalisieren(ueberschrift)

        if normal in KERNSPALTEN:
            ziel = KERNSPALTEN[normal]
            if ziel == "status":
                if wert is not None:
                    gefunden = STATUS_AUS_MAPPE.get(str(wert).strip().lower())
                    if gefunden is None:
                        befunde.append(
                            Befund(
                                FEHLER,
                                f"Status „{wert}“ steht nicht in der Werteliste "
                                f"(erlaubt: Idee, Entwurf, abgestimmt in Gruppe, beschlossen).",
                                "status",
                            )
                        )
                    else:
                        roh.status = gefunden
            elif ziel == "fassung_stand":
                roh.fassung_stand = _datum(wert)
            else:
                setattr(roh, ziel, str(wert).strip() if wert is not None else "")
            continue

        feld = typ.feld_fuer_spalte(ueberschrift)
        if feld is None:
            if wert is not None:
                befunde.append(
                    Befund(
                        "warnung",
                        f"Die Spalte „{ueberschrift}“ gehört zu keinem Feld von "
                        f"„{typ.name}“ und wird übergangen.",
                    )
                )
            continue

        if feld.ist_verlinkung:
            roh.verweise[feld.schluessel] = _ids_trennen(wert)
        elif feld.ist_berechnet:
            # „Minuten pro Woche“ rechnet die App selbst aus.
            continue
        elif wert is not None:
            if feld.typ == Feldtyp.RICHTEXT:
                roh.daten[feld.schluessel] = _text_zu_html(str(wert))
            else:
                roh.daten[feld.schluessel] = wert

    return roh, befunde


def _text_zu_html(text: str) -> str:
    """Zeilenumbrüche aus einer Zelle in Absätze verwandeln."""
    # Der Export bewahrt Rich Text als HTML; herkömmliche Zellen bleiben Klartext.
    import re

    if re.search(r"</?(?:p|h[2-4]|ul|ol|table|strong|em|blockquote)(?:>|\s)", text):
        from eintragstypen.html import saeubern

        return saeubern(text)
    absaetze = [t.strip() for t in str(text).split("\n") if t.strip()]
    if not absaetze:
        return ""
    from django.utils.html import escape

    return "".join(f"<p>{escape(absatz)}</p>" for absatz in absaetze)


def ist_beispielzeile(roh: Rohsatz) -> bool:
    return BEISPIEL_MARKIERUNG in (roh.titel or "").lower()


def titel_ohne_beispiel(titel: str) -> str:
    gekuerzt = titel
    for variante in ("(Beispiel)", "(beispiel)", "(BEISPIEL)"):
        gekuerzt = gekuerzt.replace(variante, "")
    return " ".join(gekuerzt.split())


# --- Vorschau und Übernahme ------------------------------------------------


def pruefen_mappe(
    pfad: Path, dokument, mit_beispielen: bool = False, blaetter=BLAETTER
) -> Mappenbericht:
    """Liest die Arbeitsmappe und bewertet jede Zeile, ohne zu schreiben."""
    bericht = Mappenbericht()
    gesehene_kennungen: dict[str, str] = {}
    # Kennungen, die im Laufe dieses Imports entstehen – damit „Bezug zu
    # Ritualen“ auch auf ein Ritual zeigen darf, das erst jetzt importiert wird.
    entstehende: set[str] = set()

    for typschluessel in blaetter:
        typ = registry.holen(typschluessel)
        try:
            zeilen = blatt_lesen(pfad, typ.xlsx_blatt)
        except ValueError as fehler:
            bericht.allgemein.append(Befund(FEHLER, str(fehler)))
            continue

        for zeile in zeilen:
            roh, befunde = zeile_zu_rohsatz(zeile, typschluessel)

            if ist_beispielzeile(roh):
                if not mit_beispielen:
                    bericht.uebersprungen.append(f"{roh.kennung} {roh.titel} ({roh.quelle})")
                    continue
                roh.titel = titel_ohne_beispiel(roh.titel)

            if roh.kennung and roh.kennung in gesehene_kennungen:
                befunde.append(
                    Befund(
                        FEHLER,
                        f"Die Kennung „{roh.kennung}“ kommt in der Arbeitsmappe mehrfach vor "
                        f"(zuerst in {gesehene_kennungen[roh.kennung]}).",
                        "kennung",
                    )
                )
            elif roh.kennung:
                gesehene_kennungen[roh.kennung] = roh.quelle

            satz = pruefen(dokument, roh, entstehende_kennungen=entstehende)
            satz.befunde = befunde + satz.befunde

            if roh.kennung:
                entstehende.add(roh.kennung)
            bericht.saetze.append(satz)

    return bericht


@transaction.atomic
def uebernehmen(
    pfad: Path, dokument, mit_beispielen: bool = False, nutzer=None, blaetter=BLAETTER
) -> Mappenbericht:
    """Prüft und schreibt. Bei einem Fehler wird nichts übernommen."""
    bericht = pruefen_mappe(pfad, dokument, mit_beispielen=mit_beispielen, blaetter=blaetter)
    if not bericht.ok:
        transaction.set_rollback(True)
        return bericht

    eltern = gliederung.sammelkapitel(dokument)
    for satz in bericht.saetze:
        # Nach dem Schreiben eines Rituals existiert es – der zweite Durchgang
        # über die Vorhaben kann es also auflösen. Darum hier erneut prüfen.
        frisch = pruefen(dokument, satz.roh)
        if not frisch.ok:
            satz.befunde = frisch.befunde
            transaction.set_rollback(True)
            return bericht
        eintrag = speichern(dokument, frisch, nutzer=nutzer, eltern=eltern)
        bericht.geschrieben += 1
        if satz.ist_neu:
            bericht.neu += 1
        satz.roh.kennung = eintrag.kennung

    return bericht
