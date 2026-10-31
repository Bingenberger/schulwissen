"""Registry der Eintragstypen: Felder als Daten statt als Formularcode.

Ein Eintragstyp beschreibt, welche Felder ein Eintrag hat, in welchem Block sie
in der Maske stehen, welche Pflicht sind und unter welchen Spaltennamen sie in
der Arbeitsmappe auftauchen. Daraus entstehen – aus **einer** Quelle:

* die Eingabemaske mit Blöcken und Hilfetexten (SPEC.md §7.4),
* die Prüfung von ``Eintrag.daten``,
* die Liste „was fehlt noch“ beim Wechsel auf „abgestimmt“,
* die Spaltenzuordnung des XLSX-Imports (SPEC.md §11),
* das Schema des generischen JSON-Imports,
* später die Spaltenreihenfolge von PDF- und XLSX-Export.

Ein neuer Dokumenttyp ist damit eine neue Moduldatei mit ``Feld``-Listen und
kein Umbau des Kerns (Leitprinzip 3).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date


class Feldtyp:
    PROZESSGRAPH = "prozessgraph"
    DATUM = "datum"
    TEXT = "text"
    """Einzeilige Eingabe."""
    LANGTEXT = "langtext"
    """Mehrzeilige Eingabe ohne Formatierung."""
    RICHTEXT = "richtext"
    """Formatierter Text: Überschriften, Listen, einfache Tabellen."""
    ZAHL = "zahl"
    AUSWAHL = "auswahl"
    JANEIN = "janein"
    VERLINKUNG = "verlinkung"
    """Steht nicht in ``daten``, sondern als Zeilen in ``kern.Verlinkung``."""


class Block:
    """Gruppen der Eingabemaske (SPEC.md §7.4 „Eingabemaske“)."""

    UEBERBLICK = "Überblick"
    KOMPETENZEN = "Kompetenzen"
    ZEIT = "Zeit"
    UNTERRICHT = "Unterricht"
    LEISTUNG = "Leistung"
    SONSTIGES = "Sonstiges"


def spalte_normalisieren(bezeichnung: object) -> str:
    """Spaltenüberschrift auf eine vergleichbare Form bringen.

    Die Arbeitsmappe schreibt Überschriften für Menschen: ``Ausprägung Jg. 1``,
    ``Leistung: Beurteilungsbereich``, ``Zeitumfang (Std.)``. Beim Import soll
    es nicht an einem Punkt oder einem doppelten Leerzeichen scheitern.
    """
    text = str(bezeichnung or "").strip().lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class Feld:
    """Ein Feld eines Eintragstyps."""

    schluessel: str
    label: str
    typ: str = Feldtyp.TEXT
    block: str = Block.SONSTIGES
    pflicht: bool = False
    hilfe: str = ""
    auswahl: tuple[tuple[object, str], ...] = ()
    einheit: str = ""
    zeilen: int = 4
    min_wert: float | None = None
    max_wert: float | None = None
    ganzzahl: bool = True

    #: Berechnet den Wert aus den übrigen Daten – z. B. Minuten pro Woche.
    #: Berechnete Felder sind in der Maske nur lesbar.
    berechnet: Callable[[dict], object] | None = None

    #: Steuert, ob das Feld überhaupt gilt – z. B. „Klassenarbeit“ nur in Jg. 3/4.
    #: Ein unsichtbares Feld wird nie als Pflichtfeld verlangt.
    #:
    #: Absichtlich zwei schlichte Angaben statt einer Funktion: so kann auch
    #: die Vorlage die Bedingung lesen und das Feld im Browser ein- und
    #: ausblenden, während der Nutzer noch tippt.
    sichtbar_wenn_feld: str = ""
    sichtbar_wenn_werte: tuple = ()

    #: Alle Schreibweisen, unter denen dieses Feld in der Arbeitsmappe steht.
    xlsx_spalten: tuple[str, ...] = ()

    # Nur für typ == VERLINKUNG:
    verlinkungsart: str = ""
    zieltyp: str = ""

    @property
    def ist_verlinkung(self) -> bool:
        return self.typ == Feldtyp.VERLINKUNG

    @property
    def ist_berechnet(self) -> bool:
        return self.berechnet is not None

    @property
    def ist_bedingt(self) -> bool:
        return bool(self.sichtbar_wenn_feld)

    def gilt_fuer(self, daten: dict) -> bool:
        """Gilt dieses Feld bei diesen Daten?"""
        if not self.sichtbar_wenn_feld:
            return True
        wert = (daten or {}).get(self.sichtbar_wenn_feld)
        if wert in (None, ""):
            return False
        return str(wert) in {str(erlaubt) for erlaubt in self.sichtbar_wenn_werte}

    @property
    def sichtbar_wenn_werte_js(self):
        """Die erlaubten Werte als JavaScript-Liste für x-show in der Vorlage.

        ``mark_safe`` ist hier richtig: die Werte stehen im Code dieser Datei,
        nicht in einer Eingabe. Ohne das würden die Anführungszeichen zu
        ``&#x27;`` und das Attribut wäre nicht mehr lesbar.
        """
        from django.utils.safestring import mark_safe

        werte = ", ".join(f"'{wert}'" for wert in self.sichtbar_wenn_werte)
        return mark_safe(f"[{werte}]")  # noqa: S308

    def auswahlwerte(self) -> tuple[object, ...]:
        return tuple(wert for wert, _ in self.auswahl)

    def anzeige(self, wert: object) -> str:
        """Wert als Klartext – für Leseansicht, PDF und XLSX-Export."""
        if wert is None or wert == "":
            return ""
        if self.typ == Feldtyp.PROZESSGRAPH:
            from kern.prozessdaten import als_text

            return als_text(wert)
        if self.typ == Feldtyp.JANEIN:
            return "ja" if wert else "nein"
        if self.typ == Feldtyp.AUSWAHL:
            for kandidat, beschriftung in self.auswahl:
                if str(kandidat) == str(wert):
                    return beschriftung
        if self.einheit:
            return f"{wert} {self.einheit}"
        return str(wert)


@dataclass(frozen=True)
class Eintragstyp:
    """Beschreibung eines Eintragstyps, z. B. ``ritual``."""

    schluessel: str
    name: str
    felder: tuple[Feld, ...]
    name_plural: str = ""
    beschreibung: str = ""
    #: Muster für neue Kennungen, z. B. ``R-{nr:02d}`` oder ``V-{jahrgang}-{nr:02d}``.
    #: Leer heißt: die Kennung wird von Hand oder von der Gliederung gesetzt.
    kennung_muster: str = ""
    #: Reihenfolge der Blöcke in der Maske.
    bloecke: tuple[str, ...] = (
        Block.UEBERBLICK,
        Block.KOMPETENZEN,
        Block.ZEIT,
        Block.UNTERRICHT,
        Block.LEISTUNG,
        Block.SONSTIGES,
    )
    #: Blatt der Arbeitsmappe, aus dem dieser Typ importiert wird.
    xlsx_blatt: str = ""
    #: Erlaubt Anhänge an Einträgen dieses Typs.
    mit_anhaengen: bool = True
    #: Wahr für den Ersatztyp zu einem Schlüssel, den es nicht (mehr) gibt.
    ist_platzhalter: bool = False

    _nach_schluessel: dict = field(default_factory=dict, repr=False, compare=False)
    _nach_spalte: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        for feld in self.felder:
            if feld.schluessel in self._nach_schluessel:
                raise ValueError(
                    f"Eintragstyp {self.schluessel}: Feld {feld.schluessel} ist doppelt."
                )
            self._nach_schluessel[feld.schluessel] = feld
            for spalte in (feld.label, *feld.xlsx_spalten):
                self._nach_spalte.setdefault(spalte_normalisieren(spalte), feld)

    # --- Zugriff ---------------------------------------------------------

    def feld(self, schluessel: str) -> Feld | None:
        return self._nach_schluessel.get(schluessel)

    def feld_fuer_spalte(self, bezeichnung: object) -> Feld | None:
        """Ordnet eine Spaltenüberschrift der Arbeitsmappe einem Feld zu."""
        return self._nach_spalte.get(spalte_normalisieren(bezeichnung))

    @property
    def datenfelder(self) -> tuple[Feld, ...]:
        return tuple(f for f in self.felder if not f.ist_verlinkung)

    @property
    def verlinkungsfelder(self) -> tuple[Feld, ...]:
        return tuple(f for f in self.felder if f.ist_verlinkung)

    def felder_im_block(
        self, block: str, daten: dict | None = None, alle: bool = False
    ) -> tuple[Feld, ...]:
        """Felder eines Blocks.

        ``alle=True`` nimmt auch bedingte Felder mit, deren Bedingung noch
        nicht erfüllt ist. Das braucht die Eingabemaske: „Klassenarbeit“ muss
        im Formular stehen, bevor der Jahrgang gewählt ist – sonst erschiene
        das Feld erst nach dem Speichern.
        """
        return tuple(
            f for f in self.felder if f.block == block and (alle or f.gilt_fuer(daten or {}))
        )

    def bloecke_mit_feldern(self, daten: dict | None = None, alle: bool = False):
        """Blöcke in Maskenreihenfolge, leere übersprungen."""
        for block in self.bloecke:
            felder = self.felder_im_block(block, daten, alle=alle)
            if felder:
                yield block, felder

    # --- Rechnen und Prüfen ----------------------------------------------

    def berechnen(self, daten: dict) -> dict:
        """Füllt alle berechneten Felder. Gibt eine neue Abbildung zurück."""
        ergebnis = dict(daten or {})
        for feld in self.datenfelder:
            if feld.ist_berechnet:
                try:
                    ergebnis[feld.schluessel] = feld.berechnet(ergebnis)
                except (TypeError, ValueError):
                    ergebnis[feld.schluessel] = None
        return ergebnis

    def daten_pruefen(self, rohdaten: dict) -> tuple[dict, dict[str, str]]:
        """Werte in den richtigen Typ bringen und prüfen.

        Gibt ``(daten, fehler)`` zurück; ``fehler`` ist leer, wenn alles passt.
        Fehlende Pflichtfelder gelten hier **nicht** als Fehler: Speichern als
        Entwurf muss immer möglich sein (SPEC.md §7.4). Darum gibt es dafür
        ``fehlende_pflichtfelder``.
        """
        daten: dict = {}
        fehler: dict[str, str] = {}
        rohdaten = rohdaten or {}

        for feld in self.datenfelder:
            if feld.ist_berechnet:
                continue
            if feld.schluessel not in rohdaten:
                continue
            wert = rohdaten[feld.schluessel]
            if wert is None or (isinstance(wert, str) and not wert.strip()):
                continue
            geprueft, meldung = _wert_pruefen(feld, wert)
            if meldung:
                fehler[feld.schluessel] = meldung
            else:
                daten[feld.schluessel] = geprueft

        unbekannt = set(rohdaten) - {f.schluessel for f in self.datenfelder}
        for schluessel in sorted(unbekannt):
            fehler[schluessel] = f"Das Feld „{schluessel}“ gibt es im Typ „{self.name}“ nicht."

        return self.berechnen(daten), fehler

    def fehlende_pflichtfelder(
        self, daten: dict, verlinkungsschluessel: Iterable[str] = ()
    ) -> list[Feld]:
        """Welche Pflichtfelder sind noch leer?

        ``verlinkungsschluessel`` sind die Feldschlüssel, zu denen bereits
        Verlinkungen bestehen – etwa ``kompetenzen_schwerpunkt``.
        """
        vorhanden = set(verlinkungsschluessel)
        daten = daten or {}
        fehlt = []
        for feld in self.felder:
            if not feld.pflicht or feld.ist_berechnet or not feld.gilt_fuer(daten):
                continue
            if feld.ist_verlinkung:
                if feld.schluessel not in vorhanden:
                    fehlt.append(feld)
                continue
            wert = daten.get(feld.schluessel)
            if wert is None or (isinstance(wert, str) and not wert.strip()):
                fehlt.append(feld)
        return fehlt

    def kennung_bauen(self, dokument, **teile) -> str:
        if not self.kennung_muster:
            raise ValueError(f"Eintragstyp {self.schluessel} vergibt keine Kennungen selbst.")
        return dokument.naechste_kennung(self.kennung_muster, **teile)

    def mit_feldern(self, *zusatz: Feld) -> Eintragstyp:
        """Kopie mit weiteren Feldern – für verwandte Typen."""
        return replace(self, felder=self.felder + zusatz, _nach_schluessel={}, _nach_spalte={})


def _wert_pruefen(feld: Feld, wert: object) -> tuple[object, str]:
    """Einen einzelnen Wert in den Typ des Feldes bringen."""
    if feld.typ == Feldtyp.PROZESSGRAPH:
        from django.core.exceptions import ValidationError

        from kern.prozessdaten import normalisieren

        try:
            return normalisieren(wert), ""
        except ValidationError as fehler:
            return None, " ".join(fehler.messages)
    if feld.typ == Feldtyp.DATUM:
        try:
            return date.fromisoformat(str(wert)).isoformat(), ""
        except ValueError:
            return None, "Bitte ein Datum im Format JJJJ-MM-TT angeben."

    if feld.typ == Feldtyp.ZAHL:
        if isinstance(wert, bool):
            return None, "Hier wird eine Zahl erwartet."
        try:
            zahl = float(str(wert).replace(",", "."))
        except (TypeError, ValueError):
            return None, f"„{wert}“ ist keine Zahl."
        if not math.isfinite(zahl):
            return None, "Bitte eine endliche Zahl angeben."
        if feld.ganzzahl:
            if zahl != int(zahl):
                return None, "Hier wird eine ganze Zahl erwartet."
            zahl = int(zahl)
        if feld.min_wert is not None and zahl < feld.min_wert:
            return None, f"Der Wert muss mindestens {feld.min_wert:g} sein."
        if feld.max_wert is not None and zahl > feld.max_wert:
            return None, f"Der Wert darf höchstens {feld.max_wert:g} sein."
        return zahl, ""

    if feld.typ == Feldtyp.JANEIN:
        if isinstance(wert, bool):
            return wert, ""
        text = str(wert).strip().lower()
        if text in {"ja", "true", "1", "wahr", "x"}:
            return True, ""
        if text in {"nein", "false", "0", "falsch", "-"}:
            return False, ""
        return None, f"„{wert}“ ist weder ja noch nein."

    if feld.typ == Feldtyp.AUSWAHL:
        erlaubt = feld.auswahlwerte()
        for kandidat in erlaubt:
            if str(kandidat).strip().lower() == str(wert).strip().lower():
                return kandidat, ""
        aufzaehlung = ", ".join(f"„{k}“" for k in erlaubt)
        return None, f"„{wert}“ ist kein erlaubter Wert. Erlaubt: {aufzaehlung}."

    if feld.typ == Feldtyp.RICHTEXT:
        from eintragstypen.html import saeubern

        return saeubern(str(wert)), ""

    return str(wert).strip(), ""


class Registry:
    """Hält alle bekannten Eintragstypen."""

    def __init__(self) -> None:
        self._typen: dict[str, Eintragstyp] = {}

    def registrieren(self, typ: Eintragstyp) -> Eintragstyp:
        vorhanden = self._typen.get(typ.schluessel)
        if vorhanden is not None and vorhanden is not typ:
            # Beim erneuten Laden eines Moduls (Tests, autoreload) ist das normal;
            # ein echter Namenskonflikt zweier Module wäre ein Fehler.
            if vorhanden.name != typ.name:
                raise ValueError(
                    f"Der Eintragstyp „{typ.schluessel}“ ist schon mit einem anderen "
                    f"Namen registriert: „{vorhanden.name}“ gegen „{typ.name}“."
                )
        self._typen[typ.schluessel] = typ
        return typ

    def holen(self, schluessel: str) -> Eintragstyp:
        try:
            return self._typen[schluessel]
        except KeyError:
            bekannt = ", ".join(sorted(self._typen)) or "(noch keine)"
            raise KeyError(
                f"Unbekannter Eintragstyp „{schluessel}“. Bekannt sind: {bekannt}."
            ) from None

    def bekannt(self, schluessel: str) -> bool:
        return schluessel in self._typen

    def platzhalter(self, schluessel: str) -> Eintragstyp:
        """Ersatztyp für einen Schlüssel, den es nicht gibt.

        Damit bleibt ein Dokument lesbar, auch wenn ein einzelner Eintrag einen
        unbekannten Typ trägt – etwa weil er von Hand in der Verwaltung
        angelegt wurde oder ein Modul entfernt wurde. Ohne ihn risse ein
        einziger Datensatz die ganze Seite mit.
        """
        return Eintragstyp(
            schluessel=schluessel,
            name=f"Unbekannter Eintragstyp „{schluessel}“",
            beschreibung=(
                "Diesen Eintragstyp kennt die App nicht. Der Eintrag lässt sich "
                "weder anzeigen noch bearbeiten, bis die Administration den Typ "
                "richtigstellt."
            ),
            felder=(),
            ist_platzhalter=True,
        )

    def holen_oder_platzhalter(self, schluessel: str) -> Eintragstyp:
        """Wie ``holen``, gibt aber einen Platzhalter statt eines Fehlers."""
        return self._typen.get(schluessel) or self.platzhalter(schluessel)

    def alle(self) -> Sequence[Eintragstyp]:
        return tuple(self._typen.values())

    def auswahl(self) -> list[tuple[str, str]]:
        return [(t.schluessel, t.name) for t in self._typen.values()]


#: Die eine Registry der Anwendung.
registry = Registry()
