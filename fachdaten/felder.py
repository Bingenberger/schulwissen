"""Die Spalten der Kompetenzdateien – für Import und Export gemeinsam.

Import und Export benutzen bewusst dieselbe Liste: was exportiert wurde, lässt
sich unverändert wieder importieren. Die Überschriften sind die der
Tabellenausgabe; der JSON-Schlüssel ist der aus SPEC.md §11.
"""

from __future__ import annotations

#: (JSON-Schlüssel, Modellfeld, Tabellenüberschrift, gehört dem Lehrplan?)
SPALTEN: tuple[tuple[str, str, str, bool], ...] = (
    ("id", "id", "Kennung", True),
    ("fach", "fach", "Fach", True),
    ("bereich", "bereich", "Bereich", True),
    ("bereichName", "bereich_name", "Bereich (Name)", True),
    ("schwerpunktNr", "schwerpunkt_nr", "Schwerpunkt-Nr.", True),
    ("schwerpunkt", "schwerpunkt", "Schwerpunkt", True),
    ("stufe", "stufe", "Stufe", True),
    ("text", "text", "Kompetenzerwartung", True),
    ("klammer", "klammer", "Klammerzusatz", True),
    ("uaWeitererInhalt", "ua_weiterer_inhalt", "u. a. – weiterer Inhalt", True),
    ("progressionspartner", "progressionspartner_id", "Progressionspartner", True),
    ("stufePruefen", "stufe_pruefen", "Stufe prüfen", True),
    ("schulischeFestlegung", "schulische_festlegung", "Schulische Festlegung", False),
)

#: Überschrift → JSON-Schlüssel, damit eine bearbeitete Tabelle wieder passt.
UEBERSCHRIFT_ZU_SCHLUESSEL = {
    ueberschrift.lower(): schluessel for schluessel, _, ueberschrift, _ in SPALTEN
}

#: Die Spalte, die der Schule gehört und nicht dem Lehrplan (SPEC.md §7.3).
FESTLEGUNG = "schulischeFestlegung"

UEBERSCHRIFTEN = tuple(ueberschrift for _, _, ueberschrift, _ in SPALTEN)
