"""Formatierten Text auf eine Positivliste reduzieren.

Der Editor im Browser läuft beim Kollegium, also darf sein HTML nicht ungeprüft
in die Datenbank. ``nh3`` lässt nur die Auszeichnungen durch, die die
Grundlagenkapitel brauchen: Überschriften, Listen, einfache Tabellen, Fettung,
Kursivierung und Links.
"""

from __future__ import annotations

import re

import nh3

ERLAUBTE_TAGS: set[str] = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "sub",
    "sup",
    "h2",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "blockquote",
    "hr",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "code",
    "pre",
}

ERLAUBTE_ATTRIBUTE: dict[str, set[str]] = {
    "a": {"href", "title"},
    "th": {"colspan", "rowspan", "scope"},
    "td": {"colspan", "rowspan"},
}

#: Keine „javascript:“-Links und keine „data:“-Verweise.
ERLAUBTE_SCHEMATA: set[str] = {"http", "https", "mailto"}


def saeubern(html: str) -> str:
    """Gibt den Text mit nur noch erlaubten Auszeichnungen zurück."""
    if not html:
        return ""
    sauber = nh3.clean(
        html,
        tags=ERLAUBTE_TAGS,
        attributes=ERLAUBTE_ATTRIBUTE,
        url_schemes=ERLAUBTE_SCHEMATA,
        link_rel="noopener noreferrer",
    )
    return "" if ist_leer(sauber) else sauber.strip()


def ist_leer(html: str) -> bool:
    """Wahr, wenn nach dem Entfernen der Auszeichnungen kein Text übrig bleibt.

    Viele Editoren schicken ``<p></p>`` oder ``<p><br></p>``, wenn das Feld
    leer ist. Das soll nicht als gefüllt gelten, sonst verfehlt die
    Pflichtfeldprüfung ihren Zweck.
    """
    if not html:
        return True
    return not als_text(html).strip()


def als_text(html: str) -> str:
    """Nur der Text – für Suchindex, Trefferausschnitt und XLSX-Export."""
    if not html:
        return ""
    # Blockgrenzen zu Leerzeichen machen, damit Wörter nicht verkleben.
    mit_luecken = re.sub(r"(?i)</(p|li|tr|h[2-4]|blockquote|pre)>", " ", html)
    mit_luecken = re.sub(r"(?i)<(br|hr)\s*/?>", " ", mit_luecken)
    mit_luecken = re.sub(r"(?i)</t[dh]>", " ", mit_luecken)
    nur_text = nh3.clean(mit_luecken, tags=set(), attributes={})
    nur_text = (
        nur_text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
    return re.sub(r"\s+", " ", nur_text).strip()
