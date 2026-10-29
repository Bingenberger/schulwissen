"""Die Abdeckungsmatrix muss mit dem Blatt „Übersicht“ übereinstimmen.

Das ist der Prüfstein aus SPEC.md §13: stimmen diese Zahlen, sind Kompetenz-
Stammdaten, XLSX-Import und Verlinkung zusammen richtig. Die Erwartungswerte
unten sind aus dem Blatt „Übersicht“ der Arbeitsmappe (Zeilen 4–18) abgelesen –
bei nur den beiden Beispielzeilen als Inhalt.
"""

from __future__ import annotations

import pytest

from deutsch.auswertungen import BERUEHRT, FEHLT, SCHWERPUNKT, abdeckungsmatrix
from kern.models import Status

pytestmark = pytest.mark.django_db

#: (Bereich, SP-Nr., Erwartungen, mit Schwerpunkt, nur berührt, fehlt)
UEBERSICHT = [
    ("SZ", 1, 8, 0, 0, 8),
    ("SZ", 2, 8, 0, 2, 6),
    ("SZ", 3, 9, 0, 0, 9),
    ("SC", 1, 6, 0, 0, 6),
    ("SC", 2, 9, 3, 1, 5),
    ("SC", 3, 7, 0, 0, 7),
    ("LE", 1, 10, 4, 0, 6),
    ("LE", 2, 5, 0, 1, 4),
    ("LE", 3, 18, 2, 0, 16),
    ("LE", 4, 8, 1, 3, 4),
    ("LE", 5, 2, 0, 0, 2),
    ("SP", 1, 9, 0, 0, 9),
    ("SP", 2, 13, 0, 1, 12),
    ("SP", 3, 5, 0, 0, 5),
]


def test_gesamtzahlen_wie_im_blatt_uebersicht(importierter_arbeitsplan):
    matrix = abdeckungsmatrix(importierter_arbeitsplan)

    assert matrix.erwartungen == 117
    assert matrix.mit_schwerpunkt == 10
    assert matrix.nur_beruehrt == 8
    assert matrix.fehlt == 99
    assert round(matrix.anteil_abgedeckt, 4) == 0.0855
    # Jede Erwartung ist genau einem der drei Zustände zugeordnet.
    assert matrix.mit_schwerpunkt + matrix.nur_beruehrt + matrix.fehlt == 117


@pytest.mark.parametrize(
    ("bereich", "nr", "erwartungen", "schwerpunkt", "beruehrt", "fehlt"),
    UEBERSICHT,
    ids=[f"{b}{n}" for b, n, *_ in UEBERSICHT],
)
def test_jeder_schwerpunkt_wie_im_blatt_uebersicht(
    importierter_arbeitsplan, bereich, nr, erwartungen, schwerpunkt, beruehrt, fehlt
):
    matrix = abdeckungsmatrix(importierter_arbeitsplan)

    zeile = matrix.schwerpunkt(bereich, nr)
    assert zeile is not None, f"Schwerpunkt {bereich}{nr} fehlt in der Matrix."
    assert zeile.erwartungen == erwartungen
    assert zeile.mit_schwerpunkt == schwerpunkt
    assert zeile.nur_beruehrt == beruehrt
    assert zeile.fehlt == fehlt


def test_einzelne_erwartungen_sind_richtig_eingeordnet(importierter_arbeitsplan):
    matrix = abdeckungsmatrix(importierter_arbeitsplan)

    # R-01 „Lesezeit“ baut diese gezielt auf.
    assert matrix.zeile("LE1.03S").abdeckung == SCHWERPUNKT
    # … und berührt diese nur.
    assert matrix.zeile("LE4.01S").abdeckung == BERUEHRT
    # V-3-01 „Märchen“ baut diese gezielt auf.
    assert matrix.zeile("SC2.02D").abdeckung == SCHWERPUNKT
    # Nirgends verlinkt.
    assert matrix.zeile("SZ1.01D").abdeckung == FEHLT


def test_zaehlung_getrennt_fuer_rituale_und_vorhaben(importierter_arbeitsplan):
    """SPEC.md §7.5.1: „Zählungen getrennt für Rituale und Vorhaben“."""
    matrix = abdeckungsmatrix(importierter_arbeitsplan)

    aus_ritual = matrix.zeile("LE1.03S")
    assert aus_ritual.rituale_schwerpunkt == 1
    assert aus_ritual.vorhaben_schwerpunkt == 0

    aus_vorhaben = matrix.zeile("SC2.02D")
    assert aus_vorhaben.rituale_schwerpunkt == 0
    assert aus_vorhaben.vorhaben_schwerpunkt == 1


def test_schwerpunkt_schlaegt_beruehrt(importierter_arbeitsplan, kompetenzen):
    """Ist eine Erwartung beides, zählt sie als Schwerpunkt – wie in der Mappe."""
    from kern.models import Verlinkung, Verlinkungsart, Zieltyp

    ritual = importierter_arbeitsplan.eintraege.get(kennung="R-01")
    # SC2.02D ist beim Vorhaben Schwerpunkt; jetzt berührt das Ritual sie zusätzlich.
    Verlinkung.objects.create(
        von_eintrag=ritual,
        ziel_typ=Zieltyp.KOMPETENZ,
        ziel_id="SC2.02D",
        art=Verlinkungsart.KOMPETENZ_BERUEHRT,
        feld="kompetenzen_beruehrt",
    )

    matrix = abdeckungsmatrix(importierter_arbeitsplan)

    assert matrix.zeile("SC2.02D").abdeckung == SCHWERPUNKT
    assert matrix.mit_schwerpunkt == 10
    assert matrix.nur_beruehrt == 8


def test_filter_nur_beschlossene_zaehlt_entwuerfe_nicht(importierter_arbeitsplan):
    """SPEC.md §7.5.1, Filter: nur beschlossene / inkl. Entwürfe."""
    mit_entwuerfen = abdeckungsmatrix(importierter_arbeitsplan, nur_beschlossene=False)
    nur_beschlossen = abdeckungsmatrix(importierter_arbeitsplan, nur_beschlossene=True)

    assert mit_entwuerfen.mit_schwerpunkt == 10
    # Die importierten Einträge sind Entwürfe – beschlossen ist noch nichts.
    assert nur_beschlossen.mit_schwerpunkt == 0
    assert nur_beschlossen.fehlt == 117


def test_archivierte_eintraege_zaehlen_nicht_mit(importierter_arbeitsplan):
    ritual = importierter_arbeitsplan.eintraege.get(kennung="R-01")
    ritual.status = Status.ARCHIVIERT
    ritual.save()

    matrix = abdeckungsmatrix(importierter_arbeitsplan)

    # Nur noch die fünf Schwerpunkte des Vorhabens.
    assert matrix.mit_schwerpunkt == 5
    assert matrix.zeile("LE1.03S").abdeckung == FEHLT
