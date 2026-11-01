"""Liest die Kompetenzerwartungstabellen des NRW-Lehrplan-Sammelbands.

Jede Tabelle hat zwei Spalten: „am Ende der Schuleingangsphase" und „am Ende
der Klasse 4". Erwartungen, die für beide gelten, stehen im Lehrplan in einer
über beide Spalten verbundenen Zeile. Genau das muss der Leser erkennen.

Dafür werden drei Signale aus dem PDF zusammengenommen:

1. die Zellrahmen (dünne gefüllte Rechtecke) – der linke Rahmen gibt die
   Zeilengrenzen, ein Rahmen in der Mitte zeigt eine geteilte Zeile,
2. der Aufzählungspunkt der rechten Spalte an seiner festen x-Position,
3. die Einrückung des rechten Spaltentexts mit sichtbarer Lücke zur linken.

Fehlt der Mittelrahmen (das kommt bei Zeilen über einen Seitenumbruch vor),
tragen die Signale 2 und 3.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field

import pdfplumber

X_LINKS, X_MITTE, X_RAND = 99.2, 297.6, 496.0
X_RECHTS_PUNKT, X_RECHTS_TEXT = 303.2, 321.2
TOL = 2.0
PUNKTE = ("•", "●", "▪", "‣")
KOPF = "Kompetenzerwartungen am Ende"
SUS = "Die Schülerinnen und Schüler"
STUFENZEILEN = ("der Schuleingangsphase", "der Klasse 4", "der Klasse 2")


@dataclass
class Rohposten:
    bereich: str
    schwerpunkt: str
    spalte: str
    tabellenart: str
    kapitel: str
    seite: int
    reihe: float
    zeilen: list = field(default_factory=list)


def _senkrechte(page, x, mindesthoehe=1.0):
    return sorted(
        (r["top"], r["bottom"])
        for r in page.rects
        if r["width"] < 2.0 and abs(r["x0"] - x) < TOL and r["height"] > mindesthoehe
    )


def _grauzellen(page):
    return [
        r
        for r in page.rects
        if r["fill"]
        and r["height"] > 8
        and r["width"] > 200
        and r["x0"] > X_LINKS + 2
        and isinstance(r.get("non_stroking_color"), (int, float))
        and 0.6 < r["non_stroking_color"] < 0.9
    ]


def zeilen_bauen(page):
    worte = page.extract_words(x_tolerance=1.5, y_tolerance=2, extra_attrs=["size", "fontname"])
    gruppen: list[list[dict]] = []
    for w in sorted(worte, key=lambda w: (round(w["top"], 0), w["x0"])):
        if gruppen and abs(gruppen[-1][0]["top"] - w["top"]) <= 3.5:
            gruppen[-1].append(w)
        else:
            gruppen.append([w])
    zeilen = []
    for g in gruppen:
        g.sort(key=lambda w: w["x0"])
        oben, unten = min(w["top"] for w in g), max(w["bottom"] for w in g)
        zeilen.append(
            {
                "top": oben,
                "mitte": (oben + unten) / 2,
                "size": max(w["size"] for w in g),
                "fett": all("Bold" in w["fontname"] for w in g if w["text"] not in PUNKTE),
                "worte": g,
                "text": " ".join(w["text"] for w in g),
            }
        )
    return zeilen


def _spalten(worte):
    links = [w for w in worte if w["x0"] < X_MITTE]
    rechts = [w for w in worte if w["x0"] >= X_MITTE]
    return links, rechts


def _zweispaltig(links, rechts) -> bool:
    """Steht rechts eine eigene Spalte – oder läuft der Text nur durch?

    Verlässlich ist nur der Aufzählungspunkt: er sitzt in der rechten Spalte
    immer auf derselben x-Position. Ein beliebiges Wort an dieser Stelle sagt
    nichts, denn auch ein durchlaufender Text kann dort ein Wort beginnen.
    """
    if not rechts:
        return False
    if rechts[0]["text"] in PUNKTE and abs(rechts[0]["x0"] - X_RECHTS_PUNKT) < 2.0:
        return not links or max(w["x1"] for w in links) < X_MITTE + 1
    return not links


def seite_lesen(page, zustand, posten, seitennr):
    mitten = _senkrechte(page, X_MITTE)
    reihen = [(t, b) for t, b in _senkrechte(page, X_LINKS, 6.0)]
    grau = _grauzellen(page)
    zeilen = zeilen_bauen(page)

    def deckt(bereiche, y):
        return any(t - 1 <= y <= b + 1 for t, b in bereiche)

    def reihe_von(y):
        for t, b in reihen:
            if t - 1 <= y <= b + 1:
                return (t, b)
        return None

    # Pro Tabellenzeile einmal entscheiden: geteilt oder verbunden.
    geteilt_je_reihe: dict[tuple, bool] = {}
    for t, b in reihen:
        mitte = (t + b) / 2
        wert = deckt(mitten, mitte) or deckt(mitten, t + 2) or deckt(mitten, b - 2)
        if not wert:
            for z in zeilen:
                if not (t - 1 <= z["mitte"] <= b + 1):
                    continue
                links, rechts = _spalten(z["worte"])
                if _zweispaltig(links, rechts) or (rechts and not links):
                    wert = True
                    break
        geteilt_je_reihe[(t, b)] = wert

    erste_reihe = reihen[0] if reihen else None
    for zeile in zeilen:
        text = zeile["text"].strip()
        y = zeile["mitte"]
        if not text or re.fullmatch(r"\d{1,3}", text):
            continue
        if zeile["size"] >= 11.9 and zeile["fett"] and re.match(r"\d+(\.\d+)*\s", text):
            zustand.update(bereich="", schwerpunkt="", kapitel=text, offen={})
            continue
        if KOPF in text:
            zustand["spalten"] = text.count(KOPF)
            zustand["stufen"] = []
            zustand["offen"] = {}
            continue
        if any(text.startswith(s) for s in STUFENZEILEN):
            zustand["stufen"] = [s for s in STUFENZEILEN if s in text]
            continue
        if SUS in text:
            continue
        kasten = next((r for r in grau if r["top"] - 1 <= y <= r["bottom"] + 1), None)
        if kasten is not None:
            if zeile["fett"]:
                marke = (seitennr, round(kasten["top"], 1))
                if zustand.get("kasten") == marke:
                    zustand["schwerpunkt"] = f"{zustand['schwerpunkt']} {text}".strip()
                else:
                    zustand["kasten"] = marke
                    zustand["schwerpunkt"] = text
                zustand["offen"] = {}
            continue
        reihe = reihe_von(y)
        if reihe is None:
            if zeile["fett"]:
                marke = (seitennr, round(zeile["top"] / 14))
                vorher = zustand.get("fettmarke")
                if vorher is not None and marke[0] == vorher[0] and marke[1] - vorher[1] == 1:
                    zustand["bereich"] = f"{zustand['bereich']} {text}".strip()
                else:
                    zustand.update(bereich=text, schwerpunkt="")
                zustand["fettmarke"] = marke
                zustand["offen"] = {}
            continue

        links, rechts = _spalten(zeile["worte"])
        if geteilt_je_reihe[reihe]:
            teile = [t for t in (("L", links), ("R", rechts)) if t[1]]
        else:
            teile = [("V", zeile["worte"])]

        for spalte, worte in teile:
            for weg in ("L", "R") if spalte == "V" else ("V",):
                zustand["offen"].pop(weg, None)
            if worte[0]["text"] in PUNKTE:
                worte = worte[1:]
                neu = Rohposten(
                    bereich=zustand["bereich"],
                    schwerpunkt=zustand["schwerpunkt"],
                    spalte=spalte,
                    tabellenart=_art(zustand),
                    kapitel=zustand["kapitel"],
                    seite=seitennr,
                    reihe=zeile["top"],
                )
                posten.append(neu)
                zustand["offen"][spalte] = neu
            offen = zustand["offen"].get(spalte)
            if offen is None and reihe == erste_reihe:
                # Zeile läuft über den Seitenumbruch weiter.
                vorher = [
                    p for p in posten if p.spalte == spalte and p.kapitel == zustand["kapitel"]
                ]
                if vorher:
                    offen = vorher[-1]
                    zustand["offen"][spalte] = offen
            if offen is not None and worte:
                offen.zeilen.append(" ".join(w["text"] for w in worte))


def _art(zustand) -> str:
    if zustand.get("spalten", 2) >= 2:
        return "zwei"
    stufen = zustand.get("stufen") or []
    return "nur_S" if "der Schuleingangsphase" in stufen else "nur_K"


#: Wörter, vor denen ein Strich am Zeilenende kein Trennstrich ist, sondern
#: eine Ergänzungsstrich-Verkürzung: „Hör- und Hörsehverstehen“.
ERGAENZUNGSSTRICH = ("und", "oder", "bzw.", "sowie")


def text_zusammen(zeilen: list[str]) -> str:
    """Zeilen zu einem Satz fügen und Trennstriche auflösen."""
    ergebnis = ""
    for zeile in zeilen:
        zeile = re.sub(r"\s+", " ", zeile).strip()
        if not zeile:
            continue
        if not ergebnis:
            ergebnis = zeile
            continue
        erstes_wort = zeile.split(" ", 1)[0]
        if ergebnis.endswith("-") and erstes_wort in ERGAENZUNGSSTRICH:
            ergebnis += " " + zeile
        elif ergebnis.endswith("-") and (zeile[:1].islower() or zeile[:1] == ")"):
            ergebnis = ergebnis[:-1] + zeile
        else:
            ergebnis += " " + zeile
    return ergebnis


def saeubern(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("( ", "(").replace(" )", ")")
    text = re.sub(r"(\w)\s+-\s+(und|oder|bzw\.|sowie)\b", r"\1- \2", text)
    # „EVA- Prinzip“, „Figur- Grund-Bezug“: im PDF steht dort kein Leerzeichen.
    text = re.sub(r"(\w)-\s+([A-ZÄÖÜ])", r"\1-\2", text)
    for kurz in ("u. a.", "z. B.", "ggf.", "d. h.", "bzw.", "evtl."):
        text = re.sub(re.escape(kurz).replace(r"\ ", r"\s*") + r"\s*", kurz + " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def lesen(pfad, von, bis):
    pdf = pdfplumber.open(pfad)
    posten: list[Rohposten] = []
    zustand = {
        "bereich": "",
        "schwerpunkt": "",
        "offen": {},
        "kapitel": "",
        "spalten": 2,
        "stufen": [],
    }
    for nr in range(von, bis + 1):
        seite_lesen(pdf.pages[nr - 1], zustand, posten, nr)
    return posten


def main():
    pfad, von, bis, ziel = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    posten = lesen(pfad, von, bis)
    raus = [
        {
            "seite": p.seite,
            "kapitel": p.kapitel,
            "bereich": p.bereich,
            "schwerpunkt": p.schwerpunkt,
            "spalte": p.spalte,
            "art": p.tabellenart,
            "text": saeubern(text_zusammen(p.zeilen)),
        }
        for p in posten
    ]
    json.dump(raus, open(ziel, "w"), ensure_ascii=False, indent=1)
    print(f"{len(raus)} Posten -> {ziel}")


if __name__ == "__main__":
    main()
