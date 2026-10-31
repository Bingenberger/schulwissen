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


def version_indexieren(version) -> None:
    """Nur den gespeicherten Schnappschuss indexieren, nie aktuelle Verweise."""
    from django.utils.html import strip_tags

    from kern.models import Eintragsversion, Zieltyp

    def texte(wert):
        if isinstance(wert, dict):
            return " ".join(texte(v) for v in wert.values())
        if isinstance(wert, list):
            return " ".join(texte(v) for v in wert)
        return strip_tags(str(wert)) if wert is not None else ""

    # Eintragsbeschriftungen sind dynamische Metadaten des Ziels. Sie könnten
    # beim Freigeben der Quelle noch einen fremden Zielentwurf benannt haben.
    verweise = [
        {k: w for k, w in v.items() if k != "beschriftung"}
        if v.get("ziel_typ") == Zieltyp.EINTRAG
        else v
        for v in version.verlinkungen or []
    ]
    daten = version.daten
    if version.eintrag.eintragstyp == "prozess":
        from kern.prozessdaten import als_text

        daten = {**daten, "ablauf": als_text(daten.get("ablauf"))}
        verweise = []  # Zielkennungen und fremde Metadaten sind kein Suchtext.
    text = " ".join(
        [
            version.eintrag.kennung,
            version.titel,
            texte(daten),
            texte(version.kurzantwort),
            texte(version.suchbegriffe),
            version.get_aufgabe_display() if version.aufgabe else "",
            texte(verweise),
        ]
    )
    Eintragsversion.objects.filter(pk=version.pk).update(suchtext=text)
    Eintragsversion.objects.filter(pk=version.pk).update(
        suchvektor=SearchVector("titel", weight="A", config=KONFIGURATION)
        + SearchVector("suchtext", weight="B", config=KONFIGURATION)
    )
    version.suchtext = text


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
    from kern.models import Anhang, Beschluss, Eintrag, Eintragsversion

    zahlen = {"eintraege": 0, "beschluesse": 0, "anhaenge": 0, "versionen": 0}

    for eintrag in Eintrag.objects.all().iterator():
        suchtext_aktualisieren(eintrag)
        zahlen["eintraege"] += 1
    for beschluss in Beschluss.objects.all().iterator():
        beschluss_indexieren(beschluss)
        zahlen["beschluesse"] += 1
    for anhang in Anhang.objects.all().iterator():
        anhang_indexieren(anhang)
        zahlen["anhaenge"] += 1
    for version in Eintragsversion.objects.select_related("eintrag").iterator():
        version_indexieren(version)
        zahlen["versionen"] += 1

    return zahlen
