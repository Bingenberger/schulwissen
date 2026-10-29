"""Gliederung des Arbeitsplans Deutsch (SPEC.md §7.1).

Die Struktur folgt dem QUA-LiS-Beispiel für schuleigene Unterrichtsvorgaben:
Kern sind die Unterrichtsvorhaben, Arbeitsplan und Leistungskonzept sind **ein**
Dokument.

Die Gliederung wird beim Anlegen des Dokuments erzeugt. Kapitel dürfen danach
umbenannt, ergänzt und verschachtelt werden – die Kennung bleibt, die angezeigte
Nummer rechnet sich aus dem Baum (siehe ``Eintrag.anzeige_nummer``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

#: Schlüssel des Dokumenttyps.
DOKUMENTTYP = "arbeitsplan_deutsch"

#: Kapitel, unter dem Rituale und Vorhaben einsortiert werden.
SAMMELKAPITEL = "2.1"


@dataclass(frozen=True)
class Kapitel:
    kennung: str
    titel: str
    hinweis: str = ""
    kinder: tuple[Kapitel, ...] = field(default_factory=tuple)


GLIEDERUNG: tuple[Kapitel, ...] = (
    Kapitel(
        "1",
        "Rahmenbedingungen der fachlichen Arbeit",
        "Lage der Schule, Ausstattung, Stundentafel, Lehrwerke, Zusammensetzung der "
        "Fachkonferenz.",
    ),
    Kapitel(
        "2",
        "Entscheidungen zum Unterricht",
        "Klammerkapitel – die Inhalte stehen in den Unterkapiteln.",
        kinder=(
            Kapitel(
                SAMMELKAPITEL,
                "Unterrichtsvorhaben",
                "Hier stehen die Rituale und die Unterrichtsvorhaben je Jahrgang. "
                "Die Steckbriefe werden direkt angelegt, nicht in diesen Text geschrieben.",
            ),
            Kapitel(
                "2.2",
                "Fachdidaktische und fachmethodische Grundsätze",
                "Verbindliche Absprachen, die für alle Vorhaben gelten.",
            ),
            Kapitel(
                "2.3",
                "Differenzierung und individuelle Förderung",
                "Grundsätze für GL, DaZ, Förderung und Forderung.",
            ),
            Kapitel(
                "2.4",
                "Leistungsbewertung und Leistungsrückmeldung",
                "Das Leistungskonzept: Beurteilungsbereiche, Kriterien, Niveaustufen, "
                "Rückmeldeformate. Die Vorhaben verweisen auf dieses Kapitel.",
            ),
            Kapitel(
                "2.5",
                "Lehr- und Lernmittel",
                "Eingeführte Lehrwerke je Jahrgang, Materialkisten, digitale Werkzeuge.",
            ),
        ),
    ),
    Kapitel("3", "Fächerverbindende Projekte"),
    Kapitel(
        "4",
        "Qualitätssicherung und Evaluation",
        "Wann und wie wird der Arbeitsplan überprüft und fortgeschrieben?",
    ),
    Kapitel("A", "Anhang", "Nur Anhänge: Raster, Formulare, Übersichten."),
)


def dokumenttyp_sichern():
    """Legt den Dokumenttyp an oder bringt ihn auf den Stand des Codes."""
    from deutsch.eintragstypen import EINTRAGSTYPEN_ARBEITSPLAN
    from kern.models import Dokumenttyp

    typ, _ = Dokumenttyp.objects.update_or_create(
        schluessel=DOKUMENTTYP,
        defaults={
            "name": "Arbeitsplan Deutsch",
            "beschreibung": (
                "Schuleigener Arbeitsplan Deutsch inklusive Leistungskonzept. "
                "Struktur nach dem QUA-LiS-Beispiel für schuleigene Unterrichtsvorgaben."
            ),
            "eintragstypen": list(EINTRAGSTYPEN_ARBEITSPLAN),
        },
    )
    return typ


@transaction.atomic
def dokument_anlegen(
    schluessel: str = "arbeitsplan-deutsch",
    titel: str = "Arbeitsplan Deutsch",
    gueltig_ab_schuljahr: str = "2027/28",
    nutzer=None,
):
    """Legt das Dokument mit vollständiger Gliederung an.

    Ist das Dokument schon vorhanden, werden nur fehlende Kapitel ergänzt –
    vorhandene Texte bleiben unangetastet.
    """
    from kern.models import Dokument, Status

    dokumenttyp = dokumenttyp_sichern()
    dokument, neu = Dokument.objects.get_or_create(
        schluessel=schluessel,
        defaults={
            "titel": titel,
            "dokumenttyp": dokumenttyp,
            "fach": "deutsch",
            "beschreibung": "Arbeitsplan und Leistungskonzept Deutsch der GGS Niederkassel.",
            "gueltig_ab_schuljahr": gueltig_ab_schuljahr,
            # Grundlage der Auswertung „Zeitbudget“ (SPEC.md §7.5.4):
            # Deutschstunden pro Woche je Jahrgang, à 45 Minuten.
            "einstellungen": {"deutschstunden_pro_woche": {"1": 6, "2": 6, "3": 5, "4": 5}},
            "erstellt_von": nutzer,
        },
    )

    angelegt = 0

    def kapitel_anlegen(kapitel: Kapitel, eltern, position: int) -> None:
        nonlocal angelegt
        eintrag, ist_neu = dokument.eintraege.get_or_create(
            kennung=kapitel.kennung,
            defaults={
                "eintragstyp": "grundlagenkapitel",
                "titel": kapitel.titel,
                "eltern": eltern,
                "position": position,
                "status": Status.ENTWURF,
                "daten": {"bemerkungen": kapitel.hinweis} if kapitel.hinweis else {},
                "erstellt_von": nutzer,
            },
        )
        if ist_neu:
            angelegt += 1
        for nr, kind in enumerate(kapitel.kinder, start=1):
            kapitel_anlegen(kind, eintrag, nr * 10)

    for nr, kapitel in enumerate(GLIEDERUNG, start=1):
        kapitel_anlegen(kapitel, None, nr * 10)

    return dokument, neu, angelegt


def sammelkapitel(dokument):
    """Das Kapitel 2.1, unter dem Rituale und Vorhaben hängen."""
    return dokument.eintraege.filter(kennung=SAMMELKAPITEL).first()
