"""Zusätzliche Dokumenttypen: Konzepte, Konferenzprotokolle und Schulhandbuch."""

from eintragstypen.registry import Block, Eintragstyp, Feld, Feldtyp, registry

registry.registrieren(
    Eintragstyp(
        schluessel="protokollkopf",
        name="Protokollkopf",
        kennung_muster="P-{nr:02d}",
        beschreibung="Datum und Gremium der Konferenz.",
        felder=(
            Feld("datum", "Datum", Feldtyp.DATUM, Block.UEBERBLICK, pflicht=True),
            Feld("gremium", "Gremium", block=Block.UEBERBLICK, pflicht=True),
            Feld("text", "Rahmen und Hinweise", Feldtyp.RICHTEXT, Block.UEBERBLICK),
        ),
    )
)
registry.registrieren(
    Eintragstyp(
        schluessel="tagesordnungspunkt",
        name="Tagesordnungspunkt",
        kennung_muster="TOP-{nr:02d}",
        beschreibung="Beratungsergebnis und Wortlaut der Beschlüsse zu einem Tagesordnungspunkt.",
        felder=(
            Feld("text", "Beratung und Ergebnis", Feldtyp.RICHTEXT, Block.UEBERBLICK, pflicht=True),
            Feld("beschluesse", "Beschlüsse", Feldtyp.RICHTEXT, Block.UEBERBLICK),
        ),
    )
)

registry.registrieren(
    Eintragstyp(
        schluessel="prozess",
        name="Prozess",
        name_plural="Prozesse",
        kennung_muster="PR-{nr:02d}",
        beschreibung="Allgemeiner schulischer Ablauf mit Entscheidungen und Zuständigkeiten.",
        felder=(
            Feld("anlass", "Anlass und Ziel", Feldtyp.LANGTEXT, Block.UEBERBLICK, pflicht=True),
            Feld("zielgruppe", "Für wen?", block=Block.UEBERBLICK),
            Feld("schlagwoerter", "Schlagwörter", block=Block.UEBERBLICK),
            Feld(
                "ablauf",
                "Ablauf",
                Feldtyp.PROZESSGRAPH,
                Block.UEBERBLICK,
                pflicht=True,
                hilfe="Der Ablauf ist hier zur Ansicht dargestellt.",
            ),
        ),
    )
)

DOKUMENTTYPEN = {
    "arbeitsplan": ("Arbeitsplan", ["grundlagenkapitel", "ritual", "vorhaben"]),
    "schulhandbuch": ("Schulhandbuch", ["grundlagenkapitel", "prozess"]),
    "konzept": ("Konzept", ["grundlagenkapitel"]),
    "protokoll": ("Konferenzprotokoll", ["protokollkopf", "tagesordnungspunkt"]),
}


def typen_sichern():
    from kern.models import Dokumenttyp

    for schluessel, (name, eintragstypen) in DOKUMENTTYPEN.items():
        Dokumenttyp.objects.update_or_create(
            schluessel=schluessel,
            defaults={"name": name, "eintragstypen": eintragstypen},
        )
