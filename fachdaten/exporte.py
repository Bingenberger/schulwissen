"""Kompetenzerwartungen ausgeben: JSON, XLSX und CSV.

Der Export ist die Gegenseite des Imports: dieselben Spalten, dieselben Werte.
Eine exportierte Datei kann unverändert wieder eingelesen werden – das ist der
Weg, auf dem die Schule ihre Festlegungen in Ruhe in einer Tabelle pflegt und
anschließend zurückspielt (``docs/KOMPETENZDATEN.md``).
"""

from __future__ import annotations

import csv
import io
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from fachdaten.felder import SPALTEN, UEBERSCHRIFTEN

#: Spaltenbreiten der Tabellenausgabe, in Zeichen.
BREITEN = {
    "Kennung": 13,
    "Fach": 16,
    "Bereich": 9,
    "Bereich (Name)": 30,
    "Schwerpunkt-Nr.": 7,
    "Schwerpunkt": 30,
    "Stufe": 6,
    "Kompetenzerwartung": 70,
    "Klammerzusatz": 40,
    "u. a. – weiterer Inhalt": 12,
    "Progressionspartner": 14,
    "Stufe prüfen": 8,
    "Schulische Festlegung": 40,
}


def zeile(erwartung) -> dict:
    """Eine Kompetenzerwartung als Satz im Austauschformat."""
    satz = {}
    for schluessel, feld, _, _ in SPALTEN:
        satz[schluessel] = getattr(erwartung, feld)
    return satz


def als_json(erwartungen) -> bytes:
    saetze = [zeile(e) for e in erwartungen]
    return (json.dumps(saetze, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def _text(wert) -> str:
    if wert is None:
        return ""
    if isinstance(wert, bool):
        return "ja" if wert else "nein"
    return str(wert)


def als_csv(erwartungen) -> bytes:
    puffer = io.StringIO()
    # Semikolon und BOM: so öffnet Excel die Datei ohne Zwischenschritt.
    schreiber = csv.writer(puffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    schreiber.writerow(UEBERSCHRIFTEN)
    for e in erwartungen:
        satz = zeile(e)
        schreiber.writerow([_text(satz[s]) for s, _, _, _ in SPALTEN])
    return puffer.getvalue().encode("utf-8-sig")


def als_xlsx(erwartungen) -> bytes:
    mappe = Workbook()
    blatt = mappe.active
    blatt.title = "Kompetenzerwartungen"
    blatt.append(list(UEBERSCHRIFTEN))
    for zelle in blatt[1]:
        zelle.font = Font(bold=True)
        zelle.alignment = Alignment(vertical="top", wrap_text=True)
    for e in erwartungen:
        satz = zeile(e)
        blatt.append([_text(satz[s]) for s, _, _, _ in SPALTEN])
    for nummer, ueberschrift in enumerate(UEBERSCHRIFTEN, start=1):
        blatt.column_dimensions[get_column_letter(nummer)].width = BREITEN.get(ueberschrift, 18)
    for reihe in blatt.iter_rows(min_row=2):
        for zelle in reihe:
            zelle.alignment = Alignment(vertical="top", wrap_text=True)
    blatt.freeze_panes = "B2"
    blatt.auto_filter.ref = blatt.dimensions
    puffer = io.BytesIO()
    mappe.save(puffer)
    return puffer.getvalue()


#: Format → (Funktion, MIME-Typ, Dateiendung)
FORMATE = {
    "json": (als_json, "application/json", "json"),
    "csv": (als_csv, "text/csv; charset=utf-8", "csv"),
    "xlsx": (
        als_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    ),
}
