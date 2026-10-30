"""Den Suchindex fortschreiben.

Der Index wird beim Speichern aktualisiert (SPEC.md §9). Für Einträge macht
das ``eintragstypen.dienste.suchtext_aktualisieren`` – dort ist das Feldschema
bekannt. Beschlüsse und Anhänge sind einfacher und stehen hier.

Gesucht wird mit der deutschen Konfiguration von PostgreSQL, damit „Märchen“
auch „Märchens“ findet.
"""

from __future__ import annotations

from django.contrib.postgres.search import SearchVector

#: Die Sprachkonfiguration für Stammformen. An einer Stelle, damit sie beim
#: Indexieren und beim Suchen garantiert dieselbe ist – sonst findet die Suche
#: nichts, ohne dass ein Fehler auffiele.
KONFIGURATION = "german"


def beschluss_indexieren(beschluss) -> None:
    from kern.models import Beschluss

    Beschluss.objects.filter(pk=beschluss.pk).update(
        suchvektor=(
            SearchVector("titel", weight="A", config=KONFIGURATION)
            + SearchVector("text", weight="B", config=KONFIGURATION)
        )
    )


def anhang_indexieren(anhang) -> None:
    from kern.models import Anhang

    Anhang.objects.filter(pk=anhang.pk).update(
        suchvektor=(
            SearchVector("dateiname", weight="A", config=KONFIGURATION)
            + SearchVector("beschreibung", weight="A", config=KONFIGURATION)
            + SearchVector("extrahierter_text", weight="C", config=KONFIGURATION)
        )
    )


def alles_neu_aufbauen() -> dict[str, int]:
    """Baut den gesamten Index neu. Für Umzüge und nach Änderungen am Schema."""
    from eintragstypen.dienste import suchtext_aktualisieren
    from kern.models import Anhang, Beschluss, Eintrag

    zahlen = {"eintraege": 0, "beschluesse": 0, "anhaenge": 0}

    for eintrag in Eintrag.objects.all().iterator():
        suchtext_aktualisieren(eintrag)
        zahlen["eintraege"] += 1
    for beschluss in Beschluss.objects.all().iterator():
        beschluss_indexieren(beschluss)
        zahlen["beschluesse"] += 1
    for anhang in Anhang.objects.all().iterator():
        anhang_indexieren(anhang)
        zahlen["anhaenge"] += 1

    return zahlen
