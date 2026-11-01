"""Der Lehrplan Englisch ist nicht als Tabelle gesetzt.

Englisch beginnt in Klasse 3; es gibt deshalb nur Kompetenzerwartungen „am
Ende der Klasse 4". Die Gliederung steht als Fließtext: fette Bereichszeile,
Schwerpunkt in Kapitälchen, ein beschreibender Satz, dann die Aufzählung.
"""

from __future__ import annotations

import pdfplumber
from lesen import PUNKTE, Rohposten, zeilen_bauen

#: Kapitälchen sind im PDF Großbuchstaben. Hier die Schreibweise des
#: Lehrplannavigators, damit die Schwerpunkte lesbar bleiben.
SCHWERPUNKTE = {
    "HÖR-/HÖRSEHVERSTEHEN": "Hör-/Hörsehverstehen",
    "LESEVERSTEHEN": "Leseverstehen",
    "SPRECHEN: AN GESPRÄCHEN TEILNEHMEN": "Sprechen: an Gesprächen teilnehmen",
    "SPRECHEN: ZUSAMMENHÄNGENDES SPRECHEN": "Sprechen: zusammenhängendes Sprechen",
    "SCHREIBEN": "Schreiben",
    "SPRACHMITTLUNG": "Sprachmittlung",
    "WORTSCHATZ": "Wortschatz",
    "GRAMMATIK": "Grammatik",
    "AUSSPRACHE UND INTONATION": "Aussprache und Intonation",
    "ORTHOGRAFIE": "Orthografie",
    "SOZIOKULTURELLES ORIENTIERUNGSWISSEN": "Soziokulturelles Orientierungswissen",
    "INTERKULTURELLE EINSTELLUNGEN UND BEWUSSTHEIT": (
        "Interkulturelle Einstellungen und Bewusstheit"
    ),
    "INTERKULTURELLES VERSTEHEN UND HANDELN": "Interkulturelles Verstehen und Handeln",
}

SUS = "Die Schülerinnen und Schüler"
STRICH = ("−", "–", "-")


def _aus_zeichen(page, zeile, luecke: float = 1.6) -> str:
    """Kapitälchen aus den Einzelzeichen zusammensetzen."""
    oben = min(w["top"] for w in zeile["worte"])
    unten = max(w["bottom"] for w in zeile["worte"])
    zeichen = sorted(
        (c for c in page.chars if oben - 2 <= c["top"] <= unten + 2), key=lambda c: c["x0"]
    )
    aus, letzte = "", None
    for c in zeichen:
        if letzte is not None and c["x0"] - letzte > luecke:
            aus += " "
        aus += c["text"]
        letzte = c["x1"]
    return aus.strip()


def lesen_fluss(pfad: str, von: int, bis: int):
    pdf = pdfplumber.open(pfad)
    posten: list[Rohposten] = []
    bereich = schwerpunkt = ""
    offen: Rohposten | None = None
    vorgaben: list[list[str]] = []
    for nr in range(von, bis + 1):
        page = pdf.pages[nr - 1]
        for zeile in zeilen_bauen(page):
            text = zeile["text"].strip()
            x0 = min(w["x0"] for w in zeile["worte"])
            if not text or text.isdigit():
                continue
            if zeile["size"] >= 11.9:
                continue
            if zeile["fett"]:
                bereich, schwerpunkt, offen = text, "", None
                continue
            gross = text.upper() == text and any(ch.isalpha() for ch in text)
            if gross and len(text) > 3:
                roh = _aus_zeichen(page, zeile)
                schwerpunkt = SCHWERPUNKTE.get(roh, roh)
                offen = None
                continue
            if text.startswith(SUS):
                offen = None
                continue
            if zeile["worte"][0]["text"] in PUNKTE:
                offen = Rohposten(
                    bereich=bereich,
                    schwerpunkt=schwerpunkt,
                    spalte="R",
                    tabellenart="nur_K",
                    kapitel="2.2 Kompetenzerwartungen",
                    seite=nr,
                    reihe=zeile["top"],
                )
                posten.append(offen)
                offen.zeilen.append(" ".join(w["text"] for w in zeile["worte"][1:]))
                continue
            if zeile["worte"][0]["text"] in STRICH and len(zeile["worte"]) > 1:
                vorgaben.append([" ".join(w["text"] for w in zeile["worte"][1:])])
                offen = "strich"
                continue
            if offen == "strich":
                vorgaben[-1].append(text)
                continue
            if offen is not None and x0 > 110:
                offen.zeilen.append(text)
                continue
            offen = None
    return posten, vorgaben
