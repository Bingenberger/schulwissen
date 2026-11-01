"""Fachliche Stammdaten: die Kompetenzerwartungen des Lehrplans.

Diese Tabelle ist amtliche Vorgabe (Lehrplan Deutsch Primarstufe NRW, RdErl. v.
01.07.2021) und wird importiert, nicht in der App geschrieben. Lehrkräfte wählen
Erwartungen nur aus. Die einzige Ausnahme ist ``schulische_festlegung``: dort
legt die Schule fest, welcher weitere Inhalt bei einem „u. a.“ verbindlich ist
(SPEC.md §7.3).
"""

from __future__ import annotations

from django.contrib.postgres.indexes import GinIndex
from django.db import models

from kern.models import Zeitstempel


class Fach(Zeitstempel):
    schluessel = models.SlugField("Schlüssel", max_length=40, unique=True)
    name = models.CharField("Name", max_length=100, unique=True)
    bereiche = models.JSONField(
        "Kompetenzbereiche",
        default=list,
        blank=True,
        help_text="Liste aus Kürzel und Name in der Reihenfolge des Lehrplans, "
        'z. B. [["ZA", "Zahlen"], ["RF", "Raum und Form"]]. '
        'Ein Objekt {"ZA": "Zahlen"} geht auch, wird dann aber alphabetisch sortiert.',
    )
    quelle = models.URLField("Lehrplanquelle", max_length=500, blank=True)

    class Meta:
        verbose_name = "Fach"
        verbose_name_plural = "Fächer"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def bereichspaare(self) -> list[tuple[str, str]]:
        """Kürzel und Name in der Reihenfolge des Lehrplans.

        Die Reihenfolge ist fachlich: Mathematik beginnt mit „Problemlösen“,
        nicht mit „Argumentieren“. Ein JSON-Objekt kann sie nicht halten –
        PostgreSQL speichert ``jsonb`` und sortiert dessen Schlüssel um. Eine
        Liste bleibt dagegen so, wie sie geschrieben wurde. Ältere Fächer mit
        Objekt werden alphabetisch ausgegeben.
        """
        if isinstance(self.bereiche, dict):
            return sorted(self.bereiche.items())
        return [(paar[0], paar[1]) for paar in self.bereiche or [] if len(paar) == 2]

    def clean(self):
        import re

        from django.core.exceptions import ValidationError

        fehler = ValidationError(
            {"bereiche": "Bitte Bereichskürzel (bis 20 Zeichen) und Namen angeben."}
        )
        if not isinstance(self.bereiche, (dict, list)):
            raise fehler
        if isinstance(self.bereiche, list) and any(
            not isinstance(paar, (list, tuple)) or len(paar) != 2 for paar in self.bereiche
        ):
            raise fehler
        paare = self.bereichspaare()
        if len(paare) != len(self.bereiche) or len({k for k, _ in paare}) != len(paare):
            raise fehler
        if any(
            not isinstance(kuerzel, str)
            or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,19}", kuerzel)
            or not isinstance(name, str)
            or not name.strip()
            or len(name) > 80
            for kuerzel, name in paare
        ):
            raise fehler


class Bereich(models.TextChoices):
    SZ = "SZ", "Sprechen und Zuhören"
    SC = "SC", "Schreiben"
    LE = "LE", "Lesen – mit Texten und Medien umgehen"
    SP = "SP", "Sprache und Sprachgebrauch untersuchen"


class Stufe(models.TextChoices):
    S = "S", "Ende der Schuleingangsphase"
    K = "K", "Ende der Klasse 4"
    D = "D", "durchgängig"


#: Welche Stufen bei einem Vorhaben dieses Jahrgangs vorgeschlagen werden
#: (SPEC.md §7.4 „Kompetenzauswahl“). Ein Vorschlag, keine Einschränkung.
STUFEN_JE_JAHRGANG: dict[int, tuple[str, ...]] = {
    1: (Stufe.S, Stufe.D),
    2: (Stufe.S, Stufe.D),
    3: (Stufe.K, Stufe.D),
    4: (Stufe.K, Stufe.D),
}


class Kompetenzerwartung(Zeitstempel):
    """Eine Kompetenzerwartung, z. B. ``SC1.02S``.

    Die Kennung ist der Primärschlüssel: sie steht im Lehrplan, in der
    Arbeitsmappe, in den Verlinkungen und in jedem Export. Damit bleibt sie
    auch für eine spätere Verknüpfung mit dem KompetenzKompass brauchbar
    (SPEC.md §14.7).
    """

    id = models.CharField(
        "Kennung",
        max_length=20,
        primary_key=True,
        help_text="Bereich + Schwerpunkt-Nr. + „.“ + laufende Nr. + Stufe, z. B. „SZ1.03S“.",
    )
    fach = models.CharField("Fach", max_length=40, default="deutsch")

    bereich = models.CharField("Bereich", max_length=20)
    bereich_name = models.CharField("Bereich (Name)", max_length=80)
    schwerpunkt_nr = models.PositiveSmallIntegerField("Schwerpunkt-Nr.")
    schwerpunkt = models.CharField("Schwerpunkt", max_length=120)
    stufe = models.CharField("Stufe", max_length=1, choices=Stufe)

    text = models.TextField("Kompetenzerwartung", help_text="„Die Schülerinnen und Schüler …“")
    klammer = models.TextField(
        "Klammerzusatz", blank=True, help_text="Verbindliche Inhalte laut Lehrplan."
    )
    ua_weiterer_inhalt = models.BooleanField(
        "„u. a.“ – weiterer Inhalt verbindlich",
        default=False,
        help_text="Wenn ja, muss die Schule mindestens einen weiteren Inhalt festlegen.",
    )
    schulische_festlegung = models.TextField(
        "schulische Festlegung",
        blank=True,
        help_text="Welcher weitere Inhalt ist bei uns verbindlich? "
        "Pflicht, wenn der Lehrplan „u. a.“ sagt.",
    )
    progressionspartner = models.ForeignKey(
        "self",
        verbose_name="Progressionspartner",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Erwartung gleicher Nummer der anderen Stufe.",
    )
    stufe_pruefen = models.BooleanField(
        "Stufe prüfen",
        default=False,
        help_text="Die Stufenzuordnung wurde rekonstruiert und ist am Lehrplan-PDF zu prüfen.",
    )

    suchtext = models.TextField("Suchtext", blank=True, editable=False)

    class Meta:
        verbose_name = "Kompetenzerwartung"
        verbose_name_plural = "Kompetenzerwartungen"
        ordering = ["fach", "bereich", "schwerpunkt_nr", "id"]
        indexes = [
            models.Index(
                fields=["fach", "bereich", "schwerpunkt_nr"], name="kompetenz_schwerpunkt"
            ),
            models.Index(fields=["stufe"], name="kompetenz_stufe"),
            GinIndex(
                name="kompetenz_suchtext_trgm",
                fields=["suchtext"],
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.id} {self.text[:60]}"

    @property
    def schwerpunkt_voll(self) -> str:
        """Wie im Blatt „Übersicht“: „1 Mit anderen sprechen“."""
        return f"{self.schwerpunkt_nr} {self.schwerpunkt}"

    @property
    def stufe_klartext(self) -> str:
        return Stufe(self.stufe).label

    @property
    def festlegung_fehlt(self) -> bool:
        """Für die Prüfliste (Auswertung 7.5.7)."""
        return self.ua_weiterer_inhalt and not self.schulische_festlegung.strip()

    def suchtext_bauen(self) -> str:
        teile = [
            self.id,
            self.text,
            self.klammer,
            self.schwerpunkt,
            self.bereich_name,
            self.schulische_festlegung,
        ]
        return " ".join(teil for teil in teile if teil)

    def save(self, *args, **kwargs):
        self.suchtext = self.suchtext_bauen()
        return super().save(*args, **kwargs)
