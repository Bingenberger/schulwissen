"""Die Eintragstypen des Arbeitsplans Deutsch.

Felder, Pflichtangaben und Hilfetexte stammen aus SPEC.md §7.4 und dem Blatt
``Felddefinitionen`` der Arbeitsmappe. ``xlsx_spalten`` nennt jede Schreibweise,
unter der ein Feld in der Arbeitsmappe steht – die beiden Blätter benennen
manche Felder unterschiedlich (``Kurzbeschreibung`` gegen
``Kurzbeschreibung / Produkt``), und der Import soll daran nicht scheitern.

Wer ein Feld ergänzt, ergänzt es hier – Maske, Prüfung, Import und Export
ziehen nach, ohne dass der Kern angefasst wird.
"""

from __future__ import annotations

from eintragstypen.registry import Block, Eintragstyp, Feld, Feldtyp, registry
from kern.models import Verlinkungsart, Zieltyp

# --- Wertelisten (Blatt „Wertelisten“ der Arbeitsmappe) --------------------

JAHRGAENGE = ((1, "Jahrgang 1"), (2, "Jahrgang 2"), (3, "Jahrgang 3"), (4, "Jahrgang 4"))

QUARTALE = (
    ("Q1", "Q1 – August bis Oktober"),
    ("Q2", "Q2 – November bis Januar"),
    ("Q3", "Q3 – Februar bis April"),
    ("Q4", "Q4 – Mai bis Juli"),
    ("ganzjährig", "ganzjährig"),
)

BEURTEILUNGSBEREICHE = (
    ("Sonstige Leistungen", "Sonstige Leistungen"),
    ("Schriftliche Arbeiten", "Schriftliche Arbeiten"),
    ("formativ (ohne Bewertung)", "formativ (ohne Bewertung)"),
)


# --- Berechnete Felder und Sichtbarkeit ------------------------------------


def _minuten_pro_woche(daten: dict) -> int | None:
    """Einheiten × Minuten. Fehlt eine Angabe, bleibt das Feld leer."""
    einheiten = daten.get("einheiten_pro_woche")
    minuten = daten.get("minuten_je_einheit")
    if einheiten in (None, "") or minuten in (None, ""):
        return None
    return int(einheiten) * int(minuten)


# --- Felder, die beide Typen teilen ---------------------------------------

FELD_KOMPETENZEN_SCHWERPUNKT = Feld(
    schluessel="kompetenzen_schwerpunkt",
    label="Kompetenzen Schwerpunkt",
    typ=Feldtyp.VERLINKUNG,
    block=Block.KOMPETENZEN,
    pflicht=True,
    hilfe="Kompetenzerwartungen, die gezielt aufgebaut und ggf. überprüft werden. "
    "Speist die Abdeckungsmatrix.",
    verlinkungsart=Verlinkungsart.KOMPETENZ_SCHWERPUNKT,
    zieltyp=Zieltyp.KOMPETENZ,
    xlsx_spalten=("Kompetenzen Schwerpunkt (IDs)",),
)

FELD_KOMPETENZEN_BERUEHRT = Feld(
    schluessel="kompetenzen_beruehrt",
    label="Kompetenzen berührt",
    typ=Feldtyp.VERLINKUNG,
    block=Block.KOMPETENZEN,
    hilfe="Kompetenzerwartungen, die vorkommen, aber nicht im Fokus stehen.",
    verlinkungsart=Verlinkungsart.KOMPETENZ_BERUEHRT,
    zieltyp=Zieltyp.KOMPETENZ,
    xlsx_spalten=("Kompetenzen berührt (IDs)",),
)

FELD_DIDAKTIK = Feld(
    schluessel="didaktik_methoden",
    label="Didaktische Zugänge / Methoden",
    typ=Feldtyp.RICHTEXT,
    block=Block.UNTERRICHT,
    pflicht=True,
    hilfe="Verbindliche methodische Absprachen.",
)

FELD_MATERIAL = Feld(
    schluessel="material_medien",
    label="Material / Medien",
    typ=Feldtyp.RICHTEXT,
    block=Block.UNTERRICHT,
    hilfe="Lehrwerk, Materialkiste, digitale Werkzeuge. Dateien gehören als Anhang dazu.",
)

FELD_DIFFERENZIERUNG = Feld(
    schluessel="differenzierung",
    label="Differenzierung / Förderung",
    typ=Feldtyp.RICHTEXT,
    block=Block.UNTERRICHT,
    pflicht=True,
    hilfe="Unterstützungs- und Erweiterungsangebote, Hinweise für GL und DaZ.",
)

FELD_LEISTUNG_BEREICH = Feld(
    schluessel="leistung_bereich",
    label="Leistung: Beurteilungsbereich",
    typ=Feldtyp.AUSWAHL,
    block=Block.LEISTUNG,
    pflicht=True,
    auswahl=BEURTEILUNGSBEREICHE,
    hilfe="Sonstige Leistungen, Schriftliche Arbeiten oder rein formativ.",
)

FELD_DOKUMENTATION = Feld(
    schluessel="dokumentation",
    label="Dokumentation",
    typ=Feldtyp.LANGTEXT,
    block=Block.SONSTIGES,
    zeilen=2,
    hilfe="Wo Beobachtungen festgehalten werden, z. B. KompetenzKompass.",
)

FELD_BEMERKUNGEN = Feld(
    schluessel="bemerkungen",
    label="Bemerkungen",
    typ=Feldtyp.LANGTEXT,
    block=Block.SONSTIGES,
    zeilen=3,
    hilfe="Offene Fragen, Hinweise.",
)


# --- Grundlagenkapitel ----------------------------------------------------

GRUNDLAGENKAPITEL = registry.registrieren(
    Eintragstyp(
        schluessel="grundlagenkapitel",
        name="Kapitel",
        name_plural="Kapitel",
        beschreibung="Ein Kapitel des Arbeitsplans mit formatiertem Text, Anhängen und Verweisen.",
        bloecke=(Block.UEBERBLICK, Block.SONSTIGES),
        felder=(
            Feld(
                schluessel="text",
                label="Text",
                typ=Feldtyp.RICHTEXT,
                block=Block.UEBERBLICK,
                hilfe="Überschriften, Listen und einfache Tabellen sind möglich.",
            ),
            Feld(
                schluessel="bemerkungen",
                label="Bemerkungen",
                typ=Feldtyp.LANGTEXT,
                block=Block.SONSTIGES,
                zeilen=3,
                hilfe="Offene Fragen, Hinweise – erscheinen nicht im Export.",
            ),
        ),
    )
)


# --- Ritual ---------------------------------------------------------------

RITUAL = registry.registrieren(
    Eintragstyp(
        schluessel="ritual",
        name="Ritual",
        name_plural="Rituale",
        beschreibung="Läuft dauerhaft im festen Takt, meist über alle Jahrgänge.",
        kennung_muster="R-{nr:02d}",
        xlsx_blatt="Rituale",
        felder=(
            # --- Überblick ---
            Feld(
                schluessel="kurzbeschreibung",
                label="Kurzbeschreibung",
                typ=Feldtyp.LANGTEXT,
                block=Block.UEBERBLICK,
                pflicht=True,
                zeilen=3,
                hilfe="Worum geht es, was entsteht am Ende?",
                xlsx_spalten=("Kurzbeschreibung / Produkt",),
            ),
            # --- Kompetenzen ---
            FELD_KOMPETENZEN_SCHWERPUNKT,
            FELD_KOMPETENZEN_BERUEHRT,
            # --- Zeit ---
            Feld(
                schluessel="einheiten_pro_woche",
                label="Einheiten pro Woche",
                typ=Feldtyp.ZAHL,
                block=Block.ZEIT,
                pflicht=True,
                min_wert=1,
                max_wert=20,
                hilfe="Takt des Rituals.",
            ),
            Feld(
                schluessel="minuten_je_einheit",
                label="Minuten je Einheit",
                typ=Feldtyp.ZAHL,
                block=Block.ZEIT,
                pflicht=True,
                min_wert=1,
                max_wert=180,
                einheit="Min.",
                hilfe="Dauer einer Einheit.",
            ),
            Feld(
                schluessel="minuten_pro_woche",
                label="Minuten pro Woche",
                typ=Feldtyp.ZAHL,
                block=Block.ZEIT,
                einheit="Min.",
                berechnet=_minuten_pro_woche,
                hilfe="Einheiten × Minuten. Fließt ins Zeitbudget.",
            ),
            # --- Unterricht ---
            Feld(
                schluessel="fester_ablauf",
                label="Fester Ablauf",
                typ=Feldtyp.RICHTEXT,
                block=Block.UNTERRICHT,
                pflicht=True,
                hilfe="Wiederkehrende Struktur einer Einheit.",
            ),
            *(
                Feld(
                    schluessel=f"auspraegung_jg{jg}",
                    label=f"Ausprägung Jg. {jg}",
                    typ=Feldtyp.RICHTEXT,
                    block=Block.UNTERRICHT,
                    pflicht=True,
                    hilfe=f"Wie sieht das Ritual in Jahrgang {jg} aus, was kommt hinzu? "
                    f"Füllt die Jahrgangsgruppe {jg}.",
                    xlsx_spalten=(f"Ausprägung Jg. {jg}", f"Ausprägung Jahrgang {jg}"),
                )
                for jg in (1, 2, 3, 4)
            ),
            FELD_DIDAKTIK,
            FELD_MATERIAL,
            FELD_DIFFERENZIERUNG,
            Feld(
                schluessel="lernorte_kooperationen",
                label="Außerschulische Lernorte / Kooperationen",
                typ=Feldtyp.LANGTEXT,
                block=Block.UNTERRICHT,
                zeilen=2,
                hilfe="Bücherei, Theater, Eltern, OGS …",
                # Die Arbeitsmappe nennt die Spalte im Blatt „Rituale“ anders
                # als im Blatt „Vorhaben“.
                xlsx_spalten=(
                    "Kooperationen / außerschulisch",
                    "Außerschulische Lernorte / Kooperationen",
                ),
            ),
            # --- Leistung ---
            FELD_LEISTUNG_BEREICH,
            Feld(
                schluessel="leistung_feststellung",
                label="Leistung: Feststellung und Kriterien",
                typ=Feldtyp.RICHTEXT,
                block=Block.LEISTUNG,
                pflicht=True,
                hilfe="Beobachtung, Rückmeldeformat, Kriterien.",
            ),
            # --- Sonstiges ---
            FELD_DOKUMENTATION,
            FELD_BEMERKUNGEN,
        ),
    )
)


# --- Vorhaben -------------------------------------------------------------

VORHABEN = registry.registrieren(
    Eintragstyp(
        schluessel="vorhaben",
        name="Unterrichtsvorhaben",
        name_plural="Unterrichtsvorhaben",
        beschreibung="Zeitlich begrenzt, mit Produkt, genau einem Jahrgang zugeordnet.",
        kennung_muster="V-{jahrgang}-{nr:02d}",
        xlsx_blatt="Vorhaben",
        felder=(
            # --- Überblick ---
            Feld(
                schluessel="kurzbeschreibung",
                label="Kurzbeschreibung / Produkt",
                typ=Feldtyp.LANGTEXT,
                block=Block.UEBERBLICK,
                pflicht=True,
                zeilen=3,
                hilfe="Worum geht es, was entsteht am Ende?",
                xlsx_spalten=("Kurzbeschreibung",),
            ),
            # --- Kompetenzen ---
            FELD_KOMPETENZEN_SCHWERPUNKT,
            FELD_KOMPETENZEN_BERUEHRT,
            # --- Zeit ---
            Feld(
                schluessel="jahrgang",
                label="Jahrgang",
                typ=Feldtyp.AUSWAHL,
                block=Block.ZEIT,
                pflicht=True,
                auswahl=JAHRGAENGE,
                hilfe="Verbindliche Zuordnung; ergibt den Fahrplan je Jahrgang.",
            ),
            Feld(
                schluessel="quartal",
                label="Quartal",
                typ=Feldtyp.AUSWAHL,
                block=Block.ZEIT,
                pflicht=True,
                auswahl=QUARTALE,
                hilfe="Zeitliche Lage im Schuljahr.",
            ),
            Feld(
                schluessel="zeitumfang_std",
                label="Zeitumfang",
                typ=Feldtyp.ZAHL,
                block=Block.ZEIT,
                pflicht=True,
                min_wert=1,
                max_wert=200,
                einheit="Std.",
                hilfe="Grobe Orientierung.",
                xlsx_spalten=("Zeitumfang (Std.)",),
            ),
            Feld(
                schluessel="bezug_rituale",
                label="Bezug zu Ritualen",
                typ=Feldtyp.VERLINKUNG,
                block=Block.ZEIT,
                hilfe="Welche Rituale das Vorhaben nutzt oder speist.",
                verlinkungsart=Verlinkungsart.BEZUG_RITUAL,
                zieltyp=Zieltyp.EINTRAG,
                xlsx_spalten=("Bezug zu Ritualen (IDs)",),
            ),
            # --- Unterricht ---
            FELD_DIDAKTIK,
            FELD_MATERIAL,
            Feld(
                schluessel="lernorte_kooperationen",
                label="Außerschulische Lernorte / Kooperationen",
                typ=Feldtyp.LANGTEXT,
                block=Block.UNTERRICHT,
                zeilen=2,
                hilfe="Bücherei, Theater, Eltern, OGS …",
                xlsx_spalten=("Kooperationen / außerschulisch",),
            ),
            Feld(
                schluessel="faecherverbindung",
                label="Fächerverbindung",
                typ=Feldtyp.LANGTEXT,
                block=Block.UNTERRICHT,
                zeilen=2,
                hilfe="Bezug zu anderen Fächern.",
            ),
            FELD_DIFFERENZIERUNG,
            # --- Leistung ---
            FELD_LEISTUNG_BEREICH,
            Feld(
                schluessel="leistung_form",
                label="Leistung: Form der Überprüfung",
                typ=Feldtyp.RICHTEXT,
                block=Block.LEISTUNG,
                pflicht=True,
                hilfe="Was wird wie überprüft?",
            ),
            Feld(
                schluessel="leistung_kriterien",
                label="Kriterien / Erwartungshorizont",
                typ=Feldtyp.RICHTEXT,
                block=Block.LEISTUNG,
                pflicht=True,
                hilfe="Bewertungskriterien inklusive Niveau „befriedigend“; "
                "Verweis auf Kapitel 2.4.",
            ),
            Feld(
                schluessel="klassenarbeit",
                label="Klassenarbeit",
                typ=Feldtyp.JANEIN,
                block=Block.LEISTUNG,
                pflicht=True,
                hilfe="Kennzeichnet schriftliche Arbeiten. Nur in Jahrgang 3 und 4.",
                # Klassenarbeiten gibt es in der Grundschule erst ab Klasse 3.
                sichtbar_wenn_feld="jahrgang",
                sichtbar_wenn_werte=(3, 4),
            ),
            # --- Sonstiges ---
            FELD_DOKUMENTATION,
            FELD_BEMERKUNGEN,
        ),
    )
)

#: Welche Eintragstypen im Dokumenttyp „Arbeitsplan Deutsch“ vorkommen dürfen.
EINTRAGSTYPEN_ARBEITSPLAN = (
    GRUNDLAGENKAPITEL.schluessel,
    RITUAL.schluessel,
    VORHABEN.schluessel,
)
