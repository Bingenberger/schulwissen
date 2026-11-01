"""Import der Kompetenzerwartungen aus ``lehrplan/kompetenzerwartungen_*.json``.

Der Import ist **idempotent**: ein erneuter Lauf aktualisiert die Lehrplandaten
und legt nichts doppelt an. ``schulische_festlegung`` wird dabei nie
überschrieben – das ist die einzige Spalte, die der Schule gehört und nicht dem
Lehrplan (SPEC.md §7.3, §11).

Es gibt zwei Betriebsarten:

``lehrplan``
    Die amtlichen Angaben werden geschrieben, die schulischen Festlegungen
    bleiben unberührt. So kommen neue oder berichtigte Lehrplandaten herein.

``festlegungen``
    Nur ``schulische_festlegung`` wird geschrieben, die Lehrplanangaben bleiben
    unberührt. So spielt die Schule eine in der Tabelle gepflegte Spalte
    zurück. Kennungen, die es nicht gibt, sind hier ein Fehler – sonst fiele
    ein Tippfehler in der Kennung nicht auf.

Gelesen werden JSON, XLSX und CSV. Die Spalten sind in ``fachdaten.felder``
beschrieben und für Import und Export dieselben.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from fachdaten.faecher import bereiche_fuer
from fachdaten.felder import FESTLEGUNG, UEBERSCHRIFT_ZU_SCHLUESSEL
from fachdaten.models import Fach, Kompetenzerwartung, Stufe

MODUS_LEHRPLAN = "lehrplan"
MODUS_FESTLEGUNGEN = "festlegungen"
MODI = (
    (MODUS_LEHRPLAN, "Lehrplandaten (amtlich)"),
    (MODUS_FESTLEGUNGEN, "nur schulische Festlegungen"),
)

#: Schlüssel der JSON-Datei (SPEC.md §11) auf Modellfelder – ohne „fach“ und
#: ohne die schulische Festlegung, die beide gesondert behandelt werden.
JSON_FELDER = {
    "id": "id",
    "bereich": "bereich",
    "bereichName": "bereich_name",
    "schwerpunktNr": "schwerpunkt_nr",
    "schwerpunkt": "schwerpunkt",
    "stufe": "stufe",
    "text": "text",
    "klammer": "klammer",
    "uaWeitererInhalt": "ua_weiterer_inhalt",
    "stufePruefen": "stufe_pruefen",
}

#: Höchstlänge der schulischen Festlegung. Ein Textfeld ohne Grenze lädt dazu
#: ein, ganze Konzepte hineinzuschreiben; dafür gibt es Einträge.
FESTLEGUNG_MAXLAENGE = 2000

WAHR = {"ja", "wahr", "true", "1", "x", "j"}
FALSCH = {"", "nein", "falsch", "false", "0", "n", "-"}


@dataclass
class Importbericht:
    angelegt: int = 0
    aktualisiert: int = 0
    unveraendert: int = 0
    partner_gesetzt: int = 0
    festlegungen: int = 0
    modus: str = MODUS_LEHRPLAN
    fach: str = "deutsch"
    saetze: list[dict] = field(default_factory=list)
    fehler: list[str] = field(default_factory=list)

    @property
    def gesamt(self) -> int:
        return self.angelegt + self.aktualisiert + self.unveraendert

    @property
    def ok(self) -> bool:
        return not self.fehler

    def als_text(self) -> str:
        if self.modus == MODUS_FESTLEGUNGEN:
            zeilen = [
                f"{len(self.saetze)} Zeilen gelesen:",
                f"  Festlegungen geändert: {self.festlegungen}",
                f"  unverändert:           {self.unveraendert}",
            ]
        else:
            zeilen = [
                f"{self.gesamt} Kompetenzerwartungen verarbeitet:",
                f"  neu angelegt:  {self.angelegt}",
                f"  aktualisiert:  {self.aktualisiert}",
                f"  unverändert:   {self.unveraendert}",
                f"  Progressionspartner verknüpft: {self.partner_gesetzt}",
            ]
        if self.fehler:
            zeilen.append(f"  Fehler: {len(self.fehler)}")
            zeilen.extend(f"    - {f}" for f in self.fehler)
        return "\n".join(zeilen)


# --- Dateien lesen ---------------------------------------------------------


def _json_lesen(rohtext: str) -> list[dict]:
    rohdaten = json.loads(rohtext)
    if isinstance(rohdaten, dict):
        # Erlaubt sowohl eine nackte Liste als auch ein umhüllendes Objekt.
        for schluessel in ("kompetenzerwartungen", "daten", "eintraege"):
            if isinstance(rohdaten.get(schluessel), list):
                return rohdaten[schluessel]
        raise ValueError("In der JSON-Datei ist keine Liste von Kompetenzerwartungen zu finden.")
    if not isinstance(rohdaten, list):
        raise ValueError("Die JSON-Datei muss eine Liste von Kompetenzerwartungen enthalten.")
    return rohdaten


def _wert_wandeln(schluessel: str, wert) -> object:
    """Einen Tabellenwert in die Form bringen, die der JSON-Satz hat."""
    if wert is None:
        wert = ""
    text = str(wert).strip()
    if schluessel in ("uaWeitererInhalt", "stufePruefen"):
        if text.lower() in WAHR:
            return True
        if text.lower() in FALSCH:
            return False
        return text
    if schluessel == "schwerpunktNr":
        try:
            return int(float(text))
        except ValueError:
            return text
    if schluessel == "progressionspartner":
        return text or None
    return text


def _tabelle_wandeln(zeilen: list[list]) -> list[dict]:
    if not zeilen:
        raise ValueError("Die Tabelle ist leer.")
    kopf = [str(z or "").strip().lower() for z in zeilen[0]]
    zuordnung = {
        nummer: UEBERSCHRIFT_ZU_SCHLUESSEL[name]
        for nummer, name in enumerate(kopf)
        if name in UEBERSCHRIFT_ZU_SCHLUESSEL
    }
    if "id" not in zuordnung.values():
        raise ValueError(
            "Die erste Zeile muss die Spaltenüberschriften enthalten, "
            "darunter „Kennung“. Am einfachsten geht das mit einer "
            "exportierten Datei."
        )
    saetze = []
    for zeile in zeilen[1:]:
        if not any(str(z or "").strip() for z in zeile):
            continue
        satz = {}
        for nummer, schluessel in zuordnung.items():
            wert = zeile[nummer] if nummer < len(zeile) else ""
            satz[schluessel] = _wert_wandeln(schluessel, wert)
        saetze.append(satz)
    return saetze


def _csv_lesen(rohdaten: bytes) -> list[dict]:
    text = rohdaten.decode("utf-8-sig")
    probe = text[:2000]
    trenner = ";" if probe.count(";") >= probe.count(",") else ","
    return _tabelle_wandeln(list(csv.reader(io.StringIO(text), delimiter=trenner)))


def _xlsx_lesen(rohdaten: bytes) -> list[dict]:
    from openpyxl import load_workbook

    mappe = load_workbook(io.BytesIO(rohdaten), read_only=True, data_only=True)
    blatt = mappe.active
    return _tabelle_wandeln([list(zeile) for zeile in blatt.iter_rows(values_only=True)])


def saetze_aus_daten(dateiname: str, rohdaten: bytes) -> list[dict]:
    """Sätze aus einer hochgeladenen Datei – JSON, XLSX oder CSV."""
    endung = Path(dateiname or "").suffix.lower()
    if endung == ".xlsx":
        return _xlsx_lesen(rohdaten)
    if endung == ".csv":
        return _csv_lesen(rohdaten)
    try:
        return _json_lesen(rohdaten.decode("utf-8"))
    except UnicodeDecodeError as fehler:
        raise ValueError("Bitte eine UTF-8-Datei verwenden.") from fehler


def saetze_lesen(pfad: Path) -> list[dict]:
    pfad = Path(pfad)
    return saetze_aus_daten(pfad.name, pfad.read_bytes())


# --- Prüfen ----------------------------------------------------------------


def _festlegung_pruefen(satz: dict, kennung: str) -> list[str]:
    wert = satz.get(FESTLEGUNG)
    if wert is None:
        return []
    if not isinstance(wert, str):
        return [f"{kennung}: „Schulische Festlegung“ muss Text sein."]
    if len(wert) > FESTLEGUNG_MAXLAENGE:
        return [
            f"{kennung}: Die schulische Festlegung ist länger als {FESTLEGUNG_MAXLAENGE} Zeichen."
        ]
    return []


def _satz_pruefen(satz: dict, nummer: int, bereiche, modus: str, fach: str = "") -> list[str]:
    fehler = []
    if not isinstance(satz, dict):
        return [f"Satz {nummer}: ein JSON-Objekt wird erwartet."]
    kennung = satz.get("id")
    if not isinstance(kennung, str) or not kennung.strip() or len(kennung) > 20:
        fehler.append(f"Satz {nummer}: ohne „id“.")
        return fehler
    fehler.extend(_festlegung_pruefen(satz, kennung))
    if modus == MODUS_FESTLEGUNGEN:
        # Die Lehrplanspalten dürfen dabeistehen, werden aber nicht geprüft:
        # geschrieben wird nur die Festlegung.
        return fehler
    if fach and satz.get("fach") and satz["fach"] != fach:
        # Die Datei nennt ihr Fach. Eine Sportdatei unter „Musik“ einzulesen
        # wäre ein Griff daneben, der sich schlecht rückgängig machen lässt.
        fehler.append(
            f"{kennung}: Die Datei gehört zum Fach „{satz['fach']}“, "
            f"importiert werden soll „{fach}“."
        )
    if not isinstance(satz.get("bereich"), str) or satz.get("bereich") not in bereiche:
        fehler.append(
            f"{kennung}: unbekannter Bereich „{satz.get('bereich')}“ "
            f"(erlaubt: {', '.join(bereiche)})."
        )
    if satz.get("stufe") not in Stufe.values:
        fehler.append(
            f"{kennung}: unbekannte Stufe „{satz.get('stufe')}“ "
            f"(erlaubt: {', '.join(Stufe.values)})."
        )
    for feld, grenze in (("bereichName", 80), ("schwerpunkt", 120), ("text", None)):
        wert = satz.get(feld)
        if not isinstance(wert, str) or not wert.strip() or (grenze and len(wert) > grenze):
            fehler.append(f"{kennung}: „{feld}“ fehlt oder ist ungültig.")
    for feld in ("uaWeitererInhalt", "stufePruefen"):
        if feld in satz and not isinstance(satz[feld], bool):
            fehler.append(f"{kennung}: „{feld}“ muss true oder false sein.")
    if satz.get("progressionspartner") is not None and not isinstance(
        satz["progressionspartner"], str
    ):
        fehler.append(f"{kennung}: ungültige Progressionspartner-Kennung.")
    if satz.get("klammer") is not None and not isinstance(satz["klammer"], str):
        fehler.append(f"{kennung}: ungültiger Klammerzusatz.")
    try:
        nummer_wert = satz.get("schwerpunktNr")
        if (
            isinstance(nummer_wert, bool)
            or str(int(nummer_wert)) != str(nummer_wert)
            or not 0 <= int(nummer_wert) <= 32767
        ):
            raise ValueError

    except (TypeError, ValueError):
        fehler.append(f"{kennung}: „schwerpunktNr“ ist keine Zahl.")
    return fehler


# --- Schreiben -------------------------------------------------------------


def _festlegungen_schreiben(saetze, fach: str, bericht: Importbericht) -> None:
    vorhanden = {
        e.pk: e
        for e in Kompetenzerwartung.objects.filter(
            fach=fach, pk__in=[s["id"] for s in saetze if isinstance(s.get("id"), str)]
        )
    }
    for satz in saetze:
        kennung = satz["id"]
        erwartung = vorhanden.get(kennung)
        if erwartung is None:
            bericht.fehler.append(
                f"{kennung}: Diese Kennung gibt es im Fach nicht. "
                "Bitte zuerst die Lehrplandaten importieren."
            )
            continue
        if FESTLEGUNG not in satz:
            bericht.unveraendert += 1
            continue
        neu = (satz[FESTLEGUNG] or "").strip()
        if neu == erwartung.schulische_festlegung:
            bericht.unveraendert += 1
            continue
        erwartung.schulische_festlegung = neu
        erwartung.save(update_fields=["schulische_festlegung", "suchtext", "geaendert_am"])
        bericht.festlegungen += 1


def _lehrplan_schreiben(saetze, fach: str, bericht: Importbericht) -> None:
    partner: dict[str, str] = {}
    for satz in saetze:
        werte = {
            modellfeld: satz.get(jsonfeld)
            for jsonfeld, modellfeld in JSON_FELDER.items()
            if modellfeld != "id"
        }
        werte["fach"] = fach
        werte["klammer"] = werte.get("klammer") or ""
        werte["ua_weiterer_inhalt"] = bool(werte.get("ua_weiterer_inhalt"))
        werte["stufe_pruefen"] = bool(werte.get("stufe_pruefen"))
        werte["schwerpunkt_nr"] = int(werte["schwerpunkt_nr"])

        if satz.get("progressionspartner"):
            partner[satz["id"]] = satz["progressionspartner"]

        vorhanden = Kompetenzerwartung.objects.filter(pk=satz["id"]).first()
        if vorhanden is None:
            Kompetenzerwartung(id=satz["id"], **werte).save()
            bericht.angelegt += 1
            continue

        geaendert = [f for f, w in werte.items() if getattr(vorhanden, f) != w]
        if geaendert:
            for feldname, wert in werte.items():
                setattr(vorhanden, feldname, wert)
            # schulische_festlegung steht nicht in „werte“ und bleibt damit erhalten.
            vorhanden.save()
            bericht.aktualisiert += 1
        else:
            bericht.unveraendert += 1

    # Zweiter Durchgang: jetzt sind alle Kennungen vorhanden und die
    # Progressionspaare lassen sich verknüpfen.
    bekannt = set(Kompetenzerwartung.objects.filter(fach=fach).values_list("pk", flat=True))
    for kennung, partner_kennung in partner.items():
        if partner_kennung not in bekannt:
            bericht.fehler.append(
                f"{kennung}: Progressionspartner „{partner_kennung}“ gibt es nicht."
            )
            continue
        anzahl = (
            Kompetenzerwartung.objects.filter(pk=kennung)
            .exclude(progressionspartner_id=partner_kennung)
            .update(progressionspartner_id=partner_kennung)
        )
        bericht.partner_gesetzt += anzahl


@transaction.atomic
def importieren(
    quelle,
    fach: str = "deutsch",
    nur_pruefen: bool = False,
    modus: str = MODUS_LEHRPLAN,
) -> Importbericht:
    """Kompetenzerwartungen einlesen. ``quelle`` ist ein Pfad oder eine Liste."""
    bericht = Importbericht(modus=modus, fach=fach)
    if isinstance(quelle, (str, Path)):
        try:
            saetze = saetze_lesen(Path(quelle))
        except (ValueError, OSError) as fehler:
            bericht.fehler.append(f"Datei nicht lesbar: {fehler}")
            return bericht
    else:
        saetze = list(quelle)
    bericht.saetze = saetze

    bereiche = dict(bereiche_fuer(fach))
    if not Fach.objects.filter(schluessel=fach).exists() and fach != "deutsch":
        bericht.fehler.append("Das Fach muss zuerst in der Verwaltung angelegt werden.")
        return bericht

    gesehen = set()
    for satz in saetze:
        if not isinstance(satz, dict) or not isinstance(satz.get("id"), str):
            continue
        kennung = satz["id"]
        if kennung in gesehen:
            bericht.fehler.append(f"Doppelte Kompetenzkennung: {kennung}.")
        gesehen.add(kennung)
        if Kompetenzerwartung.objects.filter(pk=kennung).exclude(fach=fach).exists():
            bericht.fehler.append(f"{kennung}: Diese Kennung gehört bereits zu einem anderen Fach.")

    for nummer, satz in enumerate(saetze, start=1):
        bericht.fehler.extend(_satz_pruefen(satz, nummer, bereiche, modus, fach))
    if bericht.fehler:
        # Lehrplandaten sind amtlich: lieber gar nicht importieren als halb.
        transaction.set_rollback(True)
        return bericht

    if modus == MODUS_FESTLEGUNGEN:
        _festlegungen_schreiben(saetze, fach, bericht)
    else:
        _lehrplan_schreiben(saetze, fach, bericht)

    if bericht.fehler or nur_pruefen:
        transaction.set_rollback(True)
    return bericht
