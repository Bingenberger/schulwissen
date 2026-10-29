"""Auswertungen über den Arbeitsplan – automatisch und nur lesend.

Phase 1 braucht davon die **Abdeckungsmatrix** (SPEC.md §7.5.1): sie ist der
Prüfstein dafür, dass die Kompetenzverlinkung stimmt, und lässt sich Zeile für
Zeile mit dem Blatt „Übersicht“ der Arbeitsmappe vergleichen.

Die übrigen sechs Auswertungen folgen in Phase 2 und setzen auf denselben
Zählungen auf.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fachdaten.models import Kompetenzerwartung
from kern.models import Status, Verlinkung, Verlinkungsart, Zieltyp

SCHWERPUNKT = "schwerpunkt"
BERUEHRT = "beruehrt"
FEHLT = "fehlt"

ABDECKUNG_BESCHRIFTUNG = {
    SCHWERPUNKT: "Schwerpunkt",
    BERUEHRT: "nur berührt",
    FEHLT: "fehlt",
}


@dataclass
class Erwartungszeile:
    """Eine Kompetenzerwartung mit ihrer Abdeckung."""

    erwartung: Kompetenzerwartung
    als_schwerpunkt: list = field(default_factory=list)
    nur_beruehrt: list = field(default_factory=list)

    @property
    def abdeckung(self) -> str:
        if self.als_schwerpunkt:
            return SCHWERPUNKT
        if self.nur_beruehrt:
            return BERUEHRT
        return FEHLT

    @property
    def beschriftung(self) -> str:
        return ABDECKUNG_BESCHRIFTUNG[self.abdeckung]

    @property
    def anzahl_schwerpunkt(self) -> int:
        return len(self.als_schwerpunkt)

    @property
    def anzahl_beruehrt(self) -> int:
        return len(self.nur_beruehrt)

    def _zaehlen(self, eintraege, typ: str) -> int:
        return sum(1 for e in eintraege if e.eintragstyp == typ)

    @property
    def rituale_schwerpunkt(self) -> int:
        return self._zaehlen(self.als_schwerpunkt, "ritual")

    @property
    def vorhaben_schwerpunkt(self) -> int:
        return self._zaehlen(self.als_schwerpunkt, "vorhaben")

    @property
    def rituale_beruehrt(self) -> int:
        return self._zaehlen(self.nur_beruehrt, "ritual")

    @property
    def vorhaben_beruehrt(self) -> int:
        return self._zaehlen(self.nur_beruehrt, "vorhaben")


@dataclass
class Schwerpunktzeile:
    """Aggregat je Schwerpunkt – entspricht einer Zeile im Blatt „Übersicht“."""

    bereich: str
    schwerpunkt_nr: int
    schwerpunkt: str
    zeilen: list[Erwartungszeile] = field(default_factory=list)

    @property
    def erwartungen(self) -> int:
        return len(self.zeilen)

    @property
    def mit_schwerpunkt(self) -> int:
        return sum(1 for z in self.zeilen if z.abdeckung == SCHWERPUNKT)

    @property
    def nur_beruehrt(self) -> int:
        return sum(1 for z in self.zeilen if z.abdeckung == BERUEHRT)

    @property
    def fehlt(self) -> int:
        return sum(1 for z in self.zeilen if z.abdeckung == FEHLT)

    @property
    def anteil_abgedeckt(self) -> float:
        if not self.zeilen:
            return 0.0
        return self.mit_schwerpunkt / self.erwartungen

    @property
    def anteil_prozent(self) -> float:
        return round(self.anteil_abgedeckt * 100, 1)

    @property
    def beschriftung(self) -> str:
        return f"{self.schwerpunkt_nr} {self.schwerpunkt}"


@dataclass
class Abdeckungsmatrix:
    zeilen: list[Erwartungszeile] = field(default_factory=list)
    schwerpunkte: list[Schwerpunktzeile] = field(default_factory=list)
    nur_beschlossene: bool = False

    @property
    def erwartungen(self) -> int:
        return len(self.zeilen)

    @property
    def mit_schwerpunkt(self) -> int:
        return sum(s.mit_schwerpunkt for s in self.schwerpunkte)

    @property
    def nur_beruehrt(self) -> int:
        return sum(s.nur_beruehrt for s in self.schwerpunkte)

    @property
    def fehlt(self) -> int:
        return sum(s.fehlt for s in self.schwerpunkte)

    @property
    def anteil_abgedeckt(self) -> float:
        if not self.zeilen:
            return 0.0
        return self.mit_schwerpunkt / self.erwartungen

    @property
    def anteil_prozent(self) -> float:
        return round(self.anteil_abgedeckt * 100, 1)

    def zeile(self, kennung: str) -> Erwartungszeile | None:
        return next((z for z in self.zeilen if z.erwartung.pk == kennung), None)

    def schwerpunkt(self, bereich: str, nr: int) -> Schwerpunktzeile | None:
        return next(
            (s for s in self.schwerpunkte if s.bereich == bereich and s.schwerpunkt_nr == nr),
            None,
        )


#: Status, die in die Auswertung einfließen, wenn Entwürfe mitzählen.
STATUS_MIT_ENTWUERFEN = (Status.IDEE, Status.ENTWURF, Status.ABGESTIMMT, Status.BESCHLOSSEN)


def abdeckungsmatrix(
    dokument, nur_beschlossene: bool = False, fach: str = "deutsch"
) -> Abdeckungsmatrix:
    """Welche Kompetenzerwartung wird wo aufgebaut, wo nur berührt, wo gar nicht?

    ``nur_beschlossene`` schaltet von „inkl. Entwürfe“ auf den beschlossenen
    Stand um (SPEC.md §7.5.1, Filter).

    Archivierte Einträge zählen nie mit: sie sind von einem neueren Beschluss
    abgelöst worden.
    """
    status = (Status.BESCHLOSSEN,) if nur_beschlossene else STATUS_MIT_ENTWUERFEN

    verlinkungen = (
        Verlinkung.objects.filter(
            von_eintrag__dokument=dokument,
            von_eintrag__status__in=status,
            ziel_typ=Zieltyp.KOMPETENZ,
            art__in=(
                Verlinkungsart.KOMPETENZ_SCHWERPUNKT,
                Verlinkungsart.KOMPETENZ_BERUEHRT,
            ),
        )
        .select_related("von_eintrag")
        .only("ziel_id", "art", "von_eintrag__eintragstyp", "von_eintrag__kennung",
              "von_eintrag__titel", "von_eintrag__status")
    )

    schwerpunkt_je_kennung: dict[str, list] = {}
    beruehrt_je_kennung: dict[str, list] = {}
    for verlinkung in verlinkungen:
        ziel = (
            schwerpunkt_je_kennung
            if verlinkung.art == Verlinkungsart.KOMPETENZ_SCHWERPUNKT
            else beruehrt_je_kennung
        )
        ziel.setdefault(verlinkung.ziel_id, []).append(verlinkung.von_eintrag)

    matrix = Abdeckungsmatrix(nur_beschlossene=nur_beschlossene)
    nach_schwerpunkt: dict[tuple[str, int], Schwerpunktzeile] = {}

    for erwartung in Kompetenzerwartung.objects.filter(fach=fach).order_by(
        "bereich", "schwerpunkt_nr", "pk"
    ):
        schwerpunkte = schwerpunkt_je_kennung.get(erwartung.pk, [])
        zeile = Erwartungszeile(
            erwartung=erwartung,
            als_schwerpunkt=schwerpunkte,
            # „nur berührt“ heißt: berührt und nirgends Schwerpunkt. Ist beides
            # verlinkt, gewinnt der Schwerpunkt – so zählt das Blatt „Übersicht“.
            nur_beruehrt=beruehrt_je_kennung.get(erwartung.pk, []) if not schwerpunkte else [],
        )
        matrix.zeilen.append(zeile)

        schluessel = (erwartung.bereich, erwartung.schwerpunkt_nr)
        if schluessel not in nach_schwerpunkt:
            nach_schwerpunkt[schluessel] = Schwerpunktzeile(
                bereich=erwartung.bereich,
                schwerpunkt_nr=erwartung.schwerpunkt_nr,
                schwerpunkt=erwartung.schwerpunkt,
            )
        nach_schwerpunkt[schluessel].zeilen.append(zeile)

    # Reihenfolge wie im Lehrplan und im Blatt „Übersicht“: SZ, SC, LE, SP.
    reihenfolge = {"SZ": 1, "SC": 2, "LE": 3, "SP": 4}
    matrix.schwerpunkte = sorted(
        nach_schwerpunkt.values(),
        key=lambda s: (reihenfolge.get(s.bereich, 9), s.schwerpunkt_nr),
    )
    return matrix


def pruefliste(fach: str = "deutsch") -> dict[str, list[Kompetenzerwartung]]:
    """Auswertung 7.5.7: was noch am Lehrplan zu prüfen ist."""
    erwartungen = Kompetenzerwartung.objects.filter(fach=fach)
    return {
        "stufe_pruefen": list(erwartungen.filter(stufe_pruefen=True)),
        "festlegung_fehlt": list(
            erwartungen.filter(ua_weiterer_inhalt=True).filter(schulische_festlegung="")
        ),
    }
