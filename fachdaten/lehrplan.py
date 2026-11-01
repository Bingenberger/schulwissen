"""Wo die Lehrplandaten liegen und welche Fächer es gibt.

Das Verzeichnis ``lehrplan/`` enthält je Fach eine JSON-Datei mit den
Kompetenzerwartungen und daneben ``faecher.json`` mit Fachnamen,
Bereichskürzeln und Quelle. Beides ist aus dem amtlichen Sammelband
„Lehrplan für die Primarstufe in Nordrhein-Westfalen“ (RdErl. v. 01.07.2021)
abgeleitet – siehe ``docs/KOMPETENZDATEN.md``.

Diese Datei ist die einzige Stelle, die die Dateinamen kennt: der
Verwaltungsbefehl, die Migration der Fächer und die Tests lesen sie hier.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

#: Name der Datei mit den Fachstammdaten.
FAECHERDATEI = "faecher.json"

#: Das Projektverzeichnis – dieselbe Wurzel wie ``schulwissen.einstellungen``.
BASIS = Path(__file__).resolve().parent.parent


def verzeichnis() -> Path:
    return BASIS / "lehrplan"


@lru_cache(maxsize=1)
def faecher() -> tuple[dict, ...]:
    """Die Fächer des Sammelbands mit Bereichskürzeln und Quelle."""
    pfad = verzeichnis() / FAECHERDATEI
    if not pfad.exists():
        return ()
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return tuple(daten)


def datei_fuer(schluessel: str) -> Path:
    return verzeichnis() / f"kompetenzerwartungen_{schluessel}.json"


def vorhandene_dateien() -> list[tuple[str, Path]]:
    """Alle Fächer, für die eine Importdatei bereitliegt – in Reihenfolge."""
    gefunden = []
    for fach in faecher():
        pfad = datei_fuer(fach["schluessel"])
        if pfad.exists():
            gefunden.append((fach["schluessel"], pfad))
    return gefunden
