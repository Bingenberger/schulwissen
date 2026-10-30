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
        .only(
            "ziel_id",
            "art",
            "von_eintrag__eintragstyp",
            "von_eintrag__kennung",
            "von_eintrag__titel",
            "von_eintrag__status",
        )
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


# --- 7.5.2 Fahrplan je Jahrgang -------------------------------------------


@dataclass
class Quartalsspalte:
    schluessel: str
    name: str
    vorhaben: list = field(default_factory=list)

    @property
    def stunden(self) -> int:
        return sum(int(v.daten.get("zeitumfang_std") or 0) for v in self.vorhaben)


@dataclass
class Fahrplan:
    jahrgang: int
    quartale: list[Quartalsspalte] = field(default_factory=list)
    rituale: list = field(default_factory=list)

    @property
    def stunden_gesamt(self) -> int:
        return sum(q.stunden for q in self.quartale)

    @property
    def anzahl_vorhaben(self) -> int:
        return sum(len(q.vorhaben) for q in self.quartale)


def fahrplan(dokument, jahrgang: int, nur_beschlossene: bool = False) -> Fahrplan:
    """Was läuft in diesem Jahrgang wann? (SPEC.md §7.5.2)

    Die Vorhaben stehen nach Quartal sortiert, die Rituale daneben – jeweils
    mit der Ausprägung genau dieses Jahrgangs.
    """
    from deutsch.eintragstypen import QUARTALE

    status = (Status.BESCHLOSSEN,) if nur_beschlossene else STATUS_MIT_ENTWUERFEN
    eintraege = dokument.eintraege.filter(status__in=status)

    plan = Fahrplan(jahrgang=jahrgang)
    vorhaben = eintraege.filter(eintragstyp="vorhaben", daten__jahrgang=jahrgang).order_by(
        "kennung"
    )

    for schluessel, name in QUARTALE:
        spalte = Quartalsspalte(schluessel=schluessel, name=name)
        spalte.vorhaben = [v for v in vorhaben if v.daten.get("quartal") == schluessel]
        plan.quartale.append(spalte)

    for ritual in eintraege.filter(eintragstyp="ritual").order_by("kennung"):
        plan.rituale.append(
            {
                "eintrag": ritual,
                "auspraegung": ritual.daten.get(f"auspraegung_jg{jahrgang}") or "",
                "minuten_pro_woche": ritual.daten.get("minuten_pro_woche"),
            }
        )

    return plan


# --- 7.5.3 Ritual-Progression ---------------------------------------------


@dataclass
class Progressionsspalte:
    jahrgang: int
    auspraegung: str = ""

    @property
    def gefuellt(self) -> bool:
        return bool(self.auspraegung.strip())


@dataclass
class Ritualprogression:
    ritual: object
    spalten: list[Progressionsspalte] = field(default_factory=list)

    @property
    def vollstaendig(self) -> bool:
        return all(s.gefuellt for s in self.spalten)

    @property
    def offene_jahrgaenge(self) -> list[int]:
        return [s.jahrgang for s in self.spalten if not s.gefuellt]


def ritualprogressionen(dokument, nur_beschlossene: bool = False) -> list[Ritualprogression]:
    """Jedes Ritual mit seinen vier Jahrgängen nebeneinander (SPEC.md §7.5.3).

    Zeigt zugleich, welche Jahrgangsgruppe ihr Feld noch nicht gefüllt hat.
    """
    status = (Status.BESCHLOSSEN,) if nur_beschlossene else STATUS_MIT_ENTWUERFEN
    ergebnis = []
    for ritual in dokument.eintraege.filter(eintragstyp="ritual", status__in=status).order_by(
        "kennung"
    ):
        progression = Ritualprogression(ritual=ritual)
        for jahrgang in (1, 2, 3, 4):
            progression.spalten.append(
                Progressionsspalte(
                    jahrgang=jahrgang,
                    auspraegung=ritual.daten.get(f"auspraegung_jg{jahrgang}") or "",
                )
            )
        ergebnis.append(progression)
    return ergebnis


# --- 7.5.4 Zeitbudget ------------------------------------------------------

#: Eine Unterrichtsstunde in Minuten.
STUNDE_MINUTEN = 45


@dataclass
class Zeitbudgetzeile:
    jahrgang: int
    stunden_pro_woche: int
    minuten_durch_rituale: int

    @property
    def minuten_pro_woche(self) -> int:
        return self.stunden_pro_woche * STUNDE_MINUTEN

    @property
    def anteil(self) -> float:
        if not self.minuten_pro_woche:
            return 0.0
        return self.minuten_durch_rituale / self.minuten_pro_woche

    @property
    def anteil_prozent(self) -> float:
        return round(self.anteil * 100, 1)

    @property
    def minuten_frei(self) -> int:
        return self.minuten_pro_woche - self.minuten_durch_rituale

    @property
    def ueberbucht(self) -> bool:
        return self.minuten_frei < 0


@dataclass
class Zeitbudget:
    zeilen: list[Zeitbudgetzeile] = field(default_factory=list)
    rituale: list = field(default_factory=list)
    ohne_angabe: list = field(default_factory=list)

    @property
    def minuten_durch_rituale(self) -> int:
        return sum(int(r.daten.get("minuten_pro_woche") or 0) for r in self.rituale)


def zeitbudget(dokument, nur_beschlossene: bool = False) -> Zeitbudget:
    """Wie viel der Deutschzeit binden die Rituale? (SPEC.md §7.5.4)

    Die Deutschstunden je Jahrgang stehen in den Einstellungen des Dokuments
    (``einstellungen["deutschstunden_pro_woche"]``) und lassen sich in der
    Verwaltung ändern.
    """
    status = (Status.BESCHLOSSEN,) if nur_beschlossene else STATUS_MIT_ENTWUERFEN
    budget = Zeitbudget()

    rituale = list(
        dokument.eintraege.filter(eintragstyp="ritual", status__in=status).order_by("kennung")
    )
    budget.rituale = [r for r in rituale if r.daten.get("minuten_pro_woche")]
    budget.ohne_angabe = [r for r in rituale if not r.daten.get("minuten_pro_woche")]

    stundentafel = (dokument.einstellungen or {}).get("deutschstunden_pro_woche") or {}
    gebunden = budget.minuten_durch_rituale

    for jahrgang in (1, 2, 3, 4):
        try:
            stunden = int(stundentafel.get(str(jahrgang), 0))
        except (TypeError, ValueError):
            stunden = 0
        budget.zeilen.append(
            Zeitbudgetzeile(
                jahrgang=jahrgang,
                stunden_pro_woche=stunden,
                minuten_durch_rituale=gebunden,
            )
        )

    return budget


# --- 7.5.5 Leistungsübersicht („Leistungskonzept") -------------------------


@dataclass
class Leistungszeile:
    eintrag: object
    bereich: str = ""
    form: str = ""
    kriterien: str = ""
    klassenarbeit: bool = False
    quartal: str = ""

    @property
    def ist_ritual(self) -> bool:
        return self.eintrag.eintragstyp == "ritual"


@dataclass
class Leistungsjahrgang:
    jahrgang: int
    zeilen: list[Leistungszeile] = field(default_factory=list)

    @property
    def klassenarbeiten(self) -> int:
        return sum(1 for z in self.zeilen if z.klassenarbeit)

    @property
    def schriftliche_arbeiten(self) -> int:
        return sum(1 for z in self.zeilen if z.bereich == "Schriftliche Arbeiten")


@dataclass
class Leistungsuebersicht:
    jahrgaenge: list[Leistungsjahrgang] = field(default_factory=list)
    rituale: list[Leistungszeile] = field(default_factory=list)
    ohne_angabe: list = field(default_factory=list)


def leistungsuebersicht(dokument, nur_beschlossene: bool = False) -> Leistungsuebersicht:
    """Alle Überprüfungen und Klassenarbeiten je Jahrgang (SPEC.md §7.5.5).

    Das ist die Sicht „Leistungskonzept": sie entsteht aus den Leistungsfeldern
    der Vorhaben und Rituale, nicht aus einem eigenen Dokument.
    """
    status = (Status.BESCHLOSSEN,) if nur_beschlossene else STATUS_MIT_ENTWUERFEN
    eintraege = dokument.eintraege.filter(status__in=status)
    uebersicht = Leistungsuebersicht()

    for jahrgang in (1, 2, 3, 4):
        spalte = Leistungsjahrgang(jahrgang=jahrgang)
        for vorhaben in eintraege.filter(eintragstyp="vorhaben", daten__jahrgang=jahrgang).order_by(
            "daten__quartal", "kennung"
        ):
            daten = vorhaben.daten
            spalte.zeilen.append(
                Leistungszeile(
                    eintrag=vorhaben,
                    bereich=daten.get("leistung_bereich") or "",
                    form=daten.get("leistung_form") or "",
                    kriterien=daten.get("leistung_kriterien") or "",
                    klassenarbeit=bool(daten.get("klassenarbeit")),
                    quartal=daten.get("quartal") or "",
                )
            )
        uebersicht.jahrgaenge.append(spalte)

    for ritual in eintraege.filter(eintragstyp="ritual").order_by("kennung"):
        uebersicht.rituale.append(
            Leistungszeile(
                eintrag=ritual,
                bereich=ritual.daten.get("leistung_bereich") or "",
                form=ritual.daten.get("leistung_feststellung") or "",
            )
        )

    uebersicht.ohne_angabe = [
        e
        for e in eintraege.filter(eintragstyp__in=("ritual", "vorhaben"))
        if not e.daten.get("leistung_bereich")
    ]
    return uebersicht


# --- 7.5.6 Progressionspaare ----------------------------------------------


@dataclass
class Progressionspaar:
    sep: object
    """Erwartung am Ende der Schuleingangsphase."""
    klasse4: object
    sep_eintraege: list = field(default_factory=list)
    klasse4_eintraege: list = field(default_factory=list)

    @property
    def beide_abgedeckt(self) -> bool:
        return bool(self.sep_eintraege) and bool(self.klasse4_eintraege)

    @property
    def luecke(self) -> str:
        if self.beide_abgedeckt:
            return ""
        if not self.sep_eintraege and not self.klasse4_eintraege:
            return "beide Stufen fehlen"
        if not self.sep_eintraege:
            return "Schuleingangsphase fehlt"
        return "Klasse 4 fehlt"


def progressionspaare(
    dokument, nur_beschlossene: bool = False, fach: str = "deutsch"
) -> list[Progressionspaar]:
    """S- und K-Erwartung nebeneinander mit den Vorhaben dazu (SPEC.md §7.5.6).

    Zeigt, wo eine Kompetenz zwar angebahnt, aber nie vertieft wird – oder
    umgekehrt.
    """
    matrix = abdeckungsmatrix(dokument, nur_beschlossene=nur_beschlossene, fach=fach)
    nach_kennung = {z.erwartung.pk: z for z in matrix.zeilen}

    paare: list[Progressionspaar] = []
    gesehen: set[str] = set()

    for zeile in matrix.zeilen:
        erwartung = zeile.erwartung
        partner_kennung = erwartung.progressionspartner_id
        if not partner_kennung or erwartung.pk in gesehen:
            continue
        partnerzeile = nach_kennung.get(partner_kennung)
        if partnerzeile is None:
            continue

        gesehen.update({erwartung.pk, partner_kennung})
        sep = zeile if erwartung.stufe == "S" else partnerzeile
        klasse4 = partnerzeile if erwartung.stufe == "S" else zeile

        paare.append(
            Progressionspaar(
                sep=sep.erwartung,
                klasse4=klasse4.erwartung,
                sep_eintraege=sep.als_schwerpunkt,
                klasse4_eintraege=klasse4.als_schwerpunkt,
            )
        )

    return sorted(paare, key=lambda p: p.sep.pk)
