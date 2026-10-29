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

from fachdaten.models import Bereich, Kompetenzerwartung, Stufe

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
        raise ValueError(
            "In der JSON-Datei ist keine Liste von Kompetenzerwartungen zu finden."
        )
    if not isinstance(rohdaten, list):
        raise ValueError("Die JSON-Datei muss eine Liste von Kompetenzerwartungen enthalten.")
    return rohdaten


def _satz_pruefen(satz: dict, nummer: int) -> list[str]:
    fehler = []
    kennung = satz.get("id")
    if not kennung:
        fehler.append(f"Satz {nummer}: ohne „id“.")
        return fehler
    if satz.get("bereich") not in Bereich.values:
        fehler.append(
            f"{kennung}: unbekannter Bereich „{satz.get('bereich')}“ "
            f"(erlaubt: {', '.join(Bereich.values)})."
        )
    if satz.get("stufe") not in Stufe.values:
        fehler.append(
            f"{kennung}: unbekannte Stufe „{satz.get('stufe')}“ "
            f"(erlaubt: {', '.join(Stufe.values)})."
        )
    if not satz.get("text"):
        fehler.append(f"{kennung}: ohne Kompetenzerwartung („text“).")
    try:
        int(satz.get("schwerpunktNr"))
    except (TypeError, ValueError):
        fehler.append(f"{kennung}: „schwerpunktNr“ ist keine Zahl.")
    return fehler


@transaction.atomic
def importieren(pfad: Path, fach: str = "deutsch", nur_pruefen: bool = False) -> Importbericht:
    bericht = Importbericht()
    saetze = saetze_lesen(Path(pfad))

    for nummer, satz in enumerate(saetze, start=1):
        bericht.fehler.extend(_satz_pruefen(satz, nummer))
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
    bekannt = set(Kompetenzerwartung.objects.values_list("pk", flat=True))
    for kennung, partner_kennung in partner.items():
        if partner_kennung not in bekannt:
            bericht.fehler.append(
                f"{kennung}: Progressionspartner „{partner_kennung}“ gibt es nicht."
            )
            continue
        anzahl = Kompetenzerwartung.objects.filter(pk=kennung).exclude(
            progressionspartner_id=partner_kennung
        ).update(progressionspartner_id=partner_kennung)
        bericht.partner_gesetzt += anzahl

    if nur_pruefen:
        transaction.set_rollback(True)
    return bericht
