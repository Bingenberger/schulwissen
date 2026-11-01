"""Baut aus dem Lehrplan-Sammelband die Importdateien je Fach.

Ergebnis: ein JSON je Fach im Format aus JSON-IMPORT.md und eine
``faecher.json`` mit Fachnamen, Bereichskürzeln und Quelle.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from englisch import lesen_fluss  # noqa: E402
from lesen import Rohposten, lesen, saeubern, text_zusammen  # noqa: E402

PROJEKT = Path(__file__).resolve().parent.parent.parent
PDF = str(PROJEKT / "ps_lp_sammelband_2025_03_18_0.pdf")
QUELLE = "https://www.schulentwicklung.nrw.de/lehrplaene/lehrplannavigator-grundschule/"

# fach -> (Name, Kürzel für die Kennung, erste/letzte Seite, Modus,
#          graue Kästen sind Bereiche?, Bereichskürzel)
FAECHER: dict[str, dict] = {
    "deutsch": dict(
        name="Deutsch",
        code="",
        seiten=(19, 29),
        modus="tabelle",
        grau_ist_bereich=False,
        bereiche={
            "Sprechen und Zuhören": "SZ",
            "Schreiben": "SC",
            "Lesen – mit Texten und Medien umgehen": "LE",
            "Sprache und Sprachgebrauch untersuchen": "SP",
        },
    ),
    "englisch": dict(
        name="Englisch",
        code="EN",
        seiten=(44, 48),
        modus="fluss",
        grau_ist_bereich=False,
        bereiche={
            "Funktionale kommunikative Kompetenz": "FK",
            "Verfügen über sprachliche Mittel": "SM",
            "Interkulturelle kommunikative Kompetenz": "IK",
            "Text- und Medienkompetenz": "TM",
            "Sprachlernkompetenz": "SL",
            "Sprachbewusstheit": "SB",
        },
    ),
    "kunst": dict(
        name="Kunst",
        code="KU",
        seiten=(61, 67),
        modus="tabelle",
        grau_ist_bereich=True,
        bereiche={
            "Bilder betrachten und verstehen": "BV",
            "Malen": "MA",
            "Zeichnen und Drucken": "ZD",
            "Plastizieren und Montieren": "PM",
            "Agieren und Inszenieren": "AI",
            "Fotografieren und Filmen": "FF",
            "Textiles Gestalten": "TG",
        },
    ),
    "mathematik": dict(
        name="Mathematik",
        code="MA",
        seiten=(82, 94),
        modus="tabelle",
        grau_ist_bereich="2.3.1",
        bereiche={
            "Problemlösen": "PL",
            "Modellieren": "MO",
            "Kommunizieren": "KO",
            "Argumentieren": "AR",
            "Darstellen": "DA",
            "Zahlen und Operationen": "ZO",
            "Raum und Form": "RF",
            "Größen und Messen": "GM",
            "Daten, Häufigkeiten, Wahrscheinlichkeiten": "DH",
        },
    ),
    "musik": dict(
        name="Musik",
        code="MU",
        seiten=(106, 109),
        modus="tabelle",
        grau_ist_bereich=True,
        bereiche={
            "Musik machen und gestalten": "MG",
            "Musik hören und verstehen": "MH",
            "Musik umsetzen und darstellen": "MU",
        },
    ),
    "philosophie": dict(
        name="Praktische Philosophie",
        code="PP",
        seiten=(120, 127),
        modus="tabelle",
        grau_ist_bereich=False,
        bereiche={
            "Das Ich": "ICH",
            "Das Du": "DU",
            "Das Wir und das Miteinander": "WIR",
            "Verantwortetes Leben – Umwelt und Technik": "VL",
            "Sichtweisen auf die Welt": "SW",
        },
    ),
    "religion-evangelisch": dict(
        name="Evangelische Religionslehre",
        code="ER",
        seiten=(139, 148),
        modus="tabelle",
        grau_ist_bereich=False,
        bereiche={
            "Miteinander leben in Gottes Schöpfung": "MS",
            "Die Frage nach Gott": "FG",
            "Jesus Christus": "JC",
            "Kirche und Gemeinde": "KG",
            "Die Bibel": "BI",
            "Religionen und Weltanschauungen": "RW",
        },
    ),
    "religion-katholisch": dict(
        name="Katholische Religionslehre",
        code="KR",
        seiten=(162, 172),
        modus="tabelle",
        grau_ist_bereich=False,
        bereiche={
            "Miteinander leben in Gottes Schöpfung": "MS",
            "Die Frage nach Gott": "FG",
            "Jesus Christus": "JC",
            "Kirche und Gemeinde": "KG",
            "Die Bibel": "BI",
            "Religionen und Weltanschauungen": "RW",
        },
    ),
    "sachunterricht": dict(
        name="Sachunterricht",
        code="SU",
        seiten=(185, 194),
        modus="tabelle",
        grau_ist_bereich=False,
        bereiche={
            "Demokratie und Gesellschaft": "DG",
            "Körper und Gesundheit": "KG",
            "Natur und Umwelt": "NU",
            "Raum und Mobilität": "RM",
            "Technik, digitale Technologie und Arbeit": "TA",
            "Zeit und Wandel": "ZW",
        },
    ),
    "sport": dict(
        name="Sport",
        code="SP",
        seiten=(210, 223),
        modus="tabelle",
        grau_ist_bereich=False,
        bereiche={
            "Den Körper wahrnehmen und Bewegungsfähigkeiten ausprägen": "KW",
            "Das Spielen entdecken und Spielräume nutzen": "SE",
            "Laufen, Springen, Werfen - Leichtathletik": "LA",
            "Bewegen im Wasser – Schwimmen": "SW",
            "Bewegen an Geräten – Turnen": "TU",
            "Gestalten, Tanzen, Darstellen – Gymnastik/Tanz, Bewegungskünste": "GT",
            "Spielen in und mit Regelstrukturen – Sportspiele": "SS",
            "Gleiten, Fahren, Rollen – Rollsport/Bootssport/Wintersport": "GF",
            "Ringen und Kämpfen – Zweikampfsport": "RK",
        },
    ),
}

STUFE_JE_SPALTE = {"V": "D", "L": "S", "R": "K"}


def klammer_von(text: str) -> str:
    """Der Klammerzusatz: die verbindlichen Inhalte in Klammern.

    Nicht jede Klammer ist ein Klammerzusatz. „(digitaler) Medien“ oder
    „(eigene) Vorstellungen“ sind Einschübe mitten im Satz und nennen keinen
    verbindlichen Inhalt. Ein Klammerzusatz steht hinter dem Begriff, den er
    aufzählt – er ist entweder mehrteilig oder beendet den Satzteil.
    """
    gruppen, tiefe, start = [], 0, None
    for i, zeichen in enumerate(text):
        if zeichen == "(":
            if tiefe == 0:
                start = i
            tiefe += 1
        elif zeichen == ")":
            tiefe = max(tiefe - 1, 0)
            if tiefe == 0 and start is not None:
                gruppen.append((text[start + 1 : i], text[i + 1 :]))
                start = None
    tauglich = [inhalt for inhalt, rest in gruppen if " " in inhalt or not rest.strip(" ,.;:")]
    return max(tauglich, key=len) if tauglich else ""


def text_putzen(text: str) -> str:
    return saeubern(text).rstrip(" ,.;").strip()


def _reihen_bilden(posten):
    """Linke und rechte Spalte derselben Tabellenzeile zusammenführen."""
    reihen: list[list] = []
    offen: dict[tuple, list] = {}
    for p in posten:
        if p.spalte == "V":
            reihen.append([p])
            offen.clear()
            continue
        schluessel = (p.seite, round(p.reihe / 4))
        if schluessel in offen and all(q.spalte != p.spalte for q in offen[schluessel]):
            offen[schluessel].append(p)
            continue
        gruppe = [p]
        reihen.append(gruppe)
        offen[schluessel] = gruppe
    return reihen


GRAMMATIK_SATZ = (
    "erproben in vertrauten Situationen ausgewählte, grundlegende grammatische "
    "Strukturen und nutzen dabei implizit-intuitiv folgende Formen und Strukturen"
)


def _grammatik(posten, vorgaben) -> Rohposten:
    """Der Schwerpunkt „Grammatik" hat im Sammelband keine Aufzählung.

    Dort stehen ein beschreibender Satz und darunter die verbindlichen Formen
    als Strichliste. Daraus wird eine Kompetenzerwartung mit Klammerzusatz –
    die einzige Stelle, an der der Satz zusammengesetzt wurde.
    """
    vorbild = next(p for p in posten if p.schwerpunkt == "Wortschatz")
    liste = "; ".join(text_zusammen(z) for z in vorgaben)
    return Rohposten(
        bereich=vorbild.bereich,
        schwerpunkt="Grammatik",
        spalte="R",
        tabellenart="nur_K",
        kapitel=vorbild.kapitel,
        seite=46,
        reihe=0.0,
        zeilen=[f"{GRAMMATIK_SATZ} ({liste})"],
    )


def fach_bauen(schluessel: str) -> tuple[list[dict], dict]:
    cfg = FAECHER[schluessel]
    von, bis = cfg["seiten"]
    if cfg["modus"] == "fluss":
        posten, vorgaben = lesen_fluss(PDF, von, bis)
        posten = [p for p in posten if p.zeilen]
        posten.append(_grammatik(posten, vorgaben))
    else:
        posten = [p for p in lesen(PDF, von, bis) if p.zeilen and "Kompetenzerwartung" in p.kapitel]

    # Bereich und Schwerpunkt je Posten festlegen.
    for p in posten:
        grau_bereich = cfg["grau_ist_bereich"]
        if grau_bereich is True or (isinstance(grau_bereich, str) and grau_bereich in p.kapitel):
            p.bereich, p.schwerpunkt = p.schwerpunkt, p.schwerpunkt
    unbekannt = sorted({p.bereich for p in posten if p.bereich not in cfg["bereiche"]})
    if unbekannt:
        raise SystemExit(f"{schluessel}: unbekannte Bereiche {unbekannt}")

    # Nummerierung je Bereich und Schwerpunkt, Partner teilen die Nummer.
    je_schwerpunkt: dict[tuple, list] = defaultdict(list)
    for p in posten:
        je_schwerpunkt[(p.bereich, p.schwerpunkt)].append(p)

    schwerpunkt_nr: dict[tuple, int] = {}
    for bereich in dict.fromkeys(p.bereich for p in posten):
        for i, (b, s) in enumerate([k for k in je_schwerpunkt if k[0] == bereich], start=1):
            schwerpunkt_nr[(b, s)] = i

    saetze: list[dict] = []
    for (bereich, schwerpunkt), gruppe in je_schwerpunkt.items():
        kuerzel = cfg["bereiche"][bereich]
        nr = schwerpunkt_nr[(bereich, schwerpunkt)]
        vorsatz = f"{cfg['code']}-" if cfg["code"] else ""
        for lauf, reihe in enumerate(_reihen_bilden(gruppe), start=1):
            kennungen = []
            for p in sorted(reihe, key=lambda q: q.spalte):
                stufe = "K" if cfg["modus"] == "fluss" else STUFE_JE_SPALTE[p.spalte]
                text = text_putzen(text_zusammen(p.zeilen))
                klammer = klammer_von(text)
                kennung = f"{vorsatz}{kuerzel}{nr}.{lauf:02d}{stufe}"
                kennungen.append(kennung)
                saetze.append(
                    {
                        "id": kennung,
                        "fach": schluessel,
                        "bereich": kuerzel,
                        "bereichName": bereich,
                        "schwerpunktNr": nr,
                        "schwerpunkt": schwerpunkt or bereich,
                        "stufe": stufe,
                        "text": text,
                        "klammer": klammer,
                        "uaWeitererInhalt": klammer.startswith("u. a."),
                        "progressionspartner": None,
                        "stufePruefen": False,
                        "seite": p.seite,
                    }
                )
            if len(kennungen) == 2:
                saetze[-1]["progressionspartner"] = kennungen[0]
                saetze[-2]["progressionspartner"] = kennungen[1]

    fach = {
        "schluessel": schluessel,
        "name": cfg["name"],
        # Eine Liste, keine Zuordnung: PostgreSQL sortiert die Schlüssel eines
        # JSON-Objekts um, die Reihenfolge der Bereiche ist aber fachlich.
        "bereiche": [
            [kuerzel, name]
            for name, kuerzel in cfg["bereiche"].items()
            if any(s["bereich"] == kuerzel for s in saetze)
        ],
        "quelle": QUELLE,
        "anzahl": len(saetze),
    }
    return saetze, fach


#: Der frühere Deutsch-Datensatz aus der Arbeitsmappe. Er dient nur noch
#: dazu, die gewachsenen Kennungen zu bewahren (docs/KOMPETENZDATEN.md).
ALTBESTAND = PROJEKT / "lehrplan" / "kompetenzerwartungen_deutsch.json"


def kennungen_bewahren(saetze: list[dict]) -> list[dict]:
    """Deutsch behält die Kennungen, unter denen es bereits verlinkt ist.

    Die Kennung ist der Verweis in ``kern.Verlinkung`` und in den
    Schnappschüssen beschlossener Fassungen. Beschlossene Fassungen sind
    unveränderlich (SPEC.md §2.4), also darf eine Kennung nicht umbenannt
    werden – auch dann nicht, wenn der Lehrplan eine andere Stufe ausweist
    als der bisherige Datensatz. Korrigiert wird deshalb nur das Feld
    ``stufe``; der Buchstabe in der Kennung bleibt historisch.
    """
    if not ALTBESTAND.exists():
        return []
    alt = json.loads(ALTBESTAND.read_text(encoding="utf-8"))
    nach_vorsatz: dict[str, list[dict]] = defaultdict(list)
    for a in alt:
        nach_vorsatz[a["id"][:-1]].append(a)
    bekannt = {a["id"] for a in alt}
    umbenannt: dict[str, str] = {}
    berichte = []
    for satz in saetze:
        if satz["id"] in bekannt:
            continue
        kandidaten = [
            a for a in nach_vorsatz[satz["id"][:-1]] if a["id"] not in {s["id"] for s in saetze}
        ]
        if len(kandidaten) != 1:
            raise SystemExit(f"Kennung {satz['id']} lässt sich nicht zuordnen.")
        alt_id = kandidaten[0]["id"]
        umbenannt[satz["id"]] = alt_id
        if kandidaten[0]["stufe"] != satz["stufe"]:
            berichte.append(
                f"{alt_id}: Stufe {kandidaten[0]['stufe']} → {satz['stufe']}; "
                f"die Kennung bleibt {alt_id}"
            )
    for satz in saetze:
        satz["id"] = umbenannt.get(satz["id"], satz["id"])
        partner = satz["progressionspartner"]
        satz["progressionspartner"] = umbenannt.get(partner, partner)
    altm = {a["id"]: a for a in alt}
    for satz in saetze:
        a = altm.get(satz["id"])
        if a and a["text"] != satz["text"]:
            berichte.append(f"{satz['id']}: Wortlaut nach Lehrplan-PDF berichtigt")
    return berichte


def main():
    ziel = Path(sys.argv[1] if len(sys.argv) > 1 else "lp/fertig")
    ziel.mkdir(parents=True, exist_ok=True)
    faecher = []
    for schluessel in FAECHER:
        saetze, fach = fach_bauen(schluessel)
        for s in saetze:
            s.pop("seite", None)
        if schluessel == "deutsch":
            for zeile in kennungen_bewahren(saetze):
                print("   berichtigt:", zeile)
        (ziel / f"kompetenzerwartungen_{schluessel}.json").write_text(
            json.dumps(saetze, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        faecher.append(fach)
        print(f"{fach['name']:30s} {len(saetze):4d} Erwartungen, {len(fach['bereiche'])} Bereiche")
    (ziel / "faecher.json").write_text(
        json.dumps(faecher, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("Gesamt:", sum(f["anzahl"] for f in faecher))


if __name__ == "__main__":
    main()
