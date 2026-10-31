"""Zwei Fassungen eines Eintrags gegenüberstellen (SPEC.md §6, Diff-Ansicht).

Verglichen wird Feld für Feld anhand des Schemas aus der Registry – nicht
Zeile für Zeile über rohes JSON. So sieht das Kollegium „Differenzierung /
Förderung wurde geändert“ und nicht einen Haufen geschweifter Klammern.

Innerhalb eines Feldes wird wortweise verglichen; Hinzugefügtes und
Entferntes wird markiert.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from django.utils.html import escape
from django.utils.safestring import mark_safe

from eintragstypen import html
from eintragstypen.registry import Feldtyp, registry

NEU = "neu"
WEG = "weg"
GEAENDERT = "geaendert"
GLEICH = "gleich"


@dataclass
class Feldvergleich:
    label: str
    schluessel: str
    art: str
    vorher: str = ""
    nachher: str = ""
    gegenueberstellung: str = ""

    @property
    def hat_aenderung(self) -> bool:
        return self.art != GLEICH


@dataclass
class Fassungsvergleich:
    alt: object
    neu: object
    titel_geaendert: bool = False
    felder: list[Feldvergleich] = field(default_factory=list)
    verweise_dazu: list[str] = field(default_factory=list)
    verweise_weg: list[str] = field(default_factory=list)

    @property
    def titel_gegenueberstellung(self) -> str:
        """Der Titel wortweise – gleiche Wörter bleiben unmarkiert."""
        return woerter_vergleichen(self.alt.titel, self.neu.titel)

    @property
    def geaenderte_felder(self) -> list[Feldvergleich]:
        return [f for f in self.felder if f.hat_aenderung]

    @property
    def hat_aenderungen(self) -> bool:
        return bool(
            self.titel_geaendert
            or self.geaenderte_felder
            or self.verweise_dazu
            or self.verweise_weg
        )


def _als_text(feld, wert) -> str:
    """Einen Feldwert in vergleichbaren Klartext verwandeln."""
    if wert in (None, "", []):
        return ""
    if feld is None:
        return str(wert)
    if feld.typ == Feldtyp.RICHTEXT:
        return html.als_text(str(wert))
    return feld.anzeige(wert)


def _woerter(text: str) -> list[str]:
    """In Wörter und Leerräume zerlegen, damit der Vergleich lesbar wird."""
    return re.findall(r"\S+\s*", text)


def woerter_vergleichen(vorher: str, nachher: str) -> str:
    """Zwei Texte wortweise gegenüberstellen, als HTML mit ``ins`` und ``del``."""
    alt, neu = _woerter(vorher), _woerter(nachher)
    teile: list[str] = []
    for art, i1, i2, j1, j2 in difflib.SequenceMatcher(None, alt, neu).get_opcodes():
        if art == "equal":
            teile.append(escape("".join(alt[i1:i2])))
        elif art == "delete":
            teile.append(f"<del>{escape(''.join(alt[i1:i2]))}</del>")
        elif art == "insert":
            teile.append(f"<ins>{escape(''.join(neu[j1:j2]))}</ins>")
        else:
            teile.append(f"<del>{escape(''.join(alt[i1:i2]))}</del>")
            teile.append(f"<ins>{escape(''.join(neu[j1:j2]))}</ins>")
    return mark_safe("".join(teile))  # noqa: S308 – alle Teile sind escaped


def vergleichen(alt, neu, nutzer=None) -> Fassungsvergleich:
    """Stellt zwei ``Eintragsversion`` gegenüber."""
    ergebnis = Fassungsvergleich(alt=alt, neu=neu)
    ergebnis.titel_geaendert = alt.titel != neu.titel

    typ = registry.holen(neu.eintrag.eintragstyp)
    for feld in typ.datenfelder:
        vorher = _als_text(feld, (alt.daten or {}).get(feld.schluessel))
        nachher = _als_text(feld, (neu.daten or {}).get(feld.schluessel))
        if (
            feld.typ == Feldtyp.PROZESSGRAPH
            and vorher == nachher
            and (alt.daten or {}).get(feld.schluessel) != (neu.daten or {}).get(feld.schluessel)
        ):
            art = GEAENDERT
            vorher += "\nBisherige Schrittkennungen oder Ressourcenverweise."
            nachher += "\nSchrittkennungen oder Ressourcenverweise geändert."
        elif vorher == nachher:
            art = GLEICH
        elif not vorher:
            art = NEU
        elif not nachher:
            art = WEG
        else:
            art = GEAENDERT

        ergebnis.felder.append(
            Feldvergleich(
                label=feld.label,
                schluessel=feld.schluessel,
                art=art,
                vorher=vorher,
                nachher=nachher,
                gegenueberstellung=(
                    woerter_vergleichen(vorher, nachher) if art == GEAENDERT else ""
                ),
            )
        )

    # Verweise (Kompetenzen, Bezüge) stehen im Schnappschuss der Fassung.
    def schluessel(verlinkungen):
        if nutzer is not None:
            from kern.staende import sichtbare_verweise

            verlinkungen = sichtbare_verweise(nutzer, verlinkungen or [])
        return {
            f"{v.get('ziel_typ', '')}:{v.get('art', '')}:{v.get('ziel_id', '')}": v.get(
                "beschriftung"
            )
            or v.get("ziel_id")
            for v in (verlinkungen or [])
            if v.get("feld") != "prozess_ablauf"
        }

    vorher_verweise = schluessel(alt.verlinkungen)
    nachher_verweise = schluessel(neu.verlinkungen)
    ergebnis.verweise_dazu = [
        text for s, text in nachher_verweise.items() if s not in vorher_verweise
    ]
    ergebnis.verweise_weg = [
        text for s, text in vorher_verweise.items() if s not in nachher_verweise
    ]
    return ergebnis
