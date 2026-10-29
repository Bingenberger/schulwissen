"""Der Import der Lehrplandaten muss wiederholbar sein."""

from __future__ import annotations

import json

import pytest

from fachdaten.importe import importieren
from fachdaten.models import Kompetenzerwartung

pytestmark = pytest.mark.django_db


def test_alle_117_erwartungen_werden_angelegt(kompetenz_json):
    bericht = importieren(kompetenz_json)

    assert bericht.fehler == []
    assert bericht.angelegt == 117
    assert Kompetenzerwartung.objects.count() == 117
    assert Kompetenzerwartung.objects.values("bereich").distinct().count() == 4
    assert (
        Kompetenzerwartung.objects.values("bereich", "schwerpunkt_nr").distinct().count() == 14
    )


def test_zweiter_lauf_legt_nichts_doppelt_an(kompetenz_json):
    importieren(kompetenz_json)
    bericht = importieren(kompetenz_json)

    assert bericht.angelegt == 0
    assert bericht.aktualisiert == 0
    assert bericht.unveraendert == 117
    assert Kompetenzerwartung.objects.count() == 117


def test_schulische_festlegung_bleibt_beim_erneuten_import_erhalten(kompetenz_json):
    """Diese Spalte gehört der Schule, nicht dem Lehrplan (SPEC.md §7.3)."""
    importieren(kompetenz_json)
    erwartung = Kompetenzerwartung.objects.filter(ua_weiterer_inhalt=True).first()
    assert erwartung is not None, "Es muss „u. a.“-Erwartungen geben."
    erwartung.schulische_festlegung = "Bei uns verbindlich: Streitschlichtungsgespräch"
    erwartung.save()

    importieren(kompetenz_json)

    erwartung.refresh_from_db()
    assert erwartung.schulische_festlegung == (
        "Bei uns verbindlich: Streitschlichtungsgespräch"
    )


def test_progressionspartner_werden_verknuepft(kompetenz_json):
    importieren(kompetenz_json)

    paare = Kompetenzerwartung.objects.exclude(progressionspartner=None)
    assert paare.count() == 52
    for erwartung in paare:
        partner = erwartung.progressionspartner
        # Progressionspaare sind beidseitig und verbinden S mit K.
        assert partner.progressionspartner_id == erwartung.pk
        assert {erwartung.stufe, partner.stufe} == {"S", "K"}


def test_stufe_pruefen_wird_uebernommen(kompetenz_json):
    """SPEC.md §16 nennt 58 Fälle, die Datei enthält 61 – es gilt die Datei."""
    rohdaten = json.loads(kompetenz_json.read_text(encoding="utf-8"))
    erwartet = sum(1 for satz in rohdaten if satz.get("stufePruefen"))

    importieren(kompetenz_json)

    assert Kompetenzerwartung.objects.filter(stufe_pruefen=True).count() == erwartet
    assert erwartet == 61


def test_fehlerhafte_datei_schreibt_nichts(tmp_path):
    datei = tmp_path / "kaputt.json"
    datei.write_text(
        json.dumps(
            [
                {
                    "id": "XX9.99Z",
                    "bereich": "XX",
                    "bereichName": "Unsinn",
                    "schwerpunktNr": 9,
                    "schwerpunkt": "Unsinn",
                    "stufe": "Z",
                    "text": "",
                    "klammer": "",
                    "uaWeitererInhalt": False,
                    "progressionspartner": None,
                    "stufePruefen": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    bericht = importieren(datei)

    assert bericht.fehler, "Unbekannter Bereich und Stufe müssen gemeldet werden."
    assert Kompetenzerwartung.objects.count() == 0


def test_festlegung_fehlt_kennzeichnet_offene_ua_erwartungen(kompetenz_json):
    importieren(kompetenz_json)

    offen = [e for e in Kompetenzerwartung.objects.all() if e.festlegung_fehlt]
    assert len(offen) == Kompetenzerwartung.objects.filter(ua_weiterer_inhalt=True).count()
    assert len(offen) == 20
