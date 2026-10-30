"""Import der Kompetenzerwartungen aus ``kompetenzerwartungen_lp2021.json``.

Der Import ist **idempotent**: ein erneuter Lauf aktualisiert die Lehrplandaten
und legt nichts doppelt an. ``schulische_festlegung`` wird dabei nie
überschrieben – das ist die einzige Spalte, die der Schule gehört und nicht dem
Lehrplan (SPEC.md §7.3, §11).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from fachdaten.faecher import bereiche_fuer
from fachdaten.models import Fach, Kompetenzerwartung, Stufe

#: Schlüssel der JSON-Datei (SPEC.md §11) auf Modellfelder.
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


@dataclass
class Importbericht:
    angelegt: int = 0
    aktualisiert: int = 0
    unveraendert: int = 0
    partner_gesetzt: int = 0
    fehler: list[str] = field(default_factory=list)

    @property
    def gesamt(self) -> int:
        return self.angelegt + self.aktualisiert + self.unveraendert

    def als_text(self) -> str:
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


def saetze_lesen(pfad: Path) -> list[dict]:
    rohdaten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    if isinstance(rohdaten, dict):
        # Erlaubt sowohl eine nackte Liste als auch ein umhüllendes Objekt.
        for schluessel in ("kompetenzerwartungen", "daten", "eintraege"):
            if isinstance(rohdaten.get(schluessel), list):
                return rohdaten[schluessel]
        raise ValueError("In der JSON-Datei ist keine Liste von Kompetenzerwartungen zu finden.")
    if not isinstance(rohdaten, list):
        raise ValueError("Die JSON-Datei muss eine Liste von Kompetenzerwartungen enthalten.")
    return rohdaten


def _satz_pruefen(satz: dict, nummer: int, bereiche) -> list[str]:
    fehler = []
    if not isinstance(satz, dict):
        return [f"Satz {nummer}: ein JSON-Objekt wird erwartet."]
    kennung = satz.get("id")
    if not isinstance(kennung, str) or not kennung.strip() or len(kennung) > 20:
        fehler.append(f"Satz {nummer}: ohne „id“.")
        return fehler
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


@transaction.atomic
def importieren(pfad: Path, fach: str = "deutsch", nur_pruefen: bool = False) -> Importbericht:
    bericht = Importbericht()
    try:
        saetze = saetze_lesen(Path(pfad))
    except (ValueError, OSError) as fehler:
        bericht.fehler.append(f"Datei nicht lesbar: {fehler}")
        return bericht
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
        bericht.fehler.extend(_satz_pruefen(satz, nummer, bereiche))
    if bericht.fehler:
        # Lehrplandaten sind amtlich: lieber gar nicht importieren als halb.
        transaction.set_rollback(True)
        return bericht

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

    if bericht.fehler or nur_pruefen:
        transaction.set_rollback(True)
    return bericht
