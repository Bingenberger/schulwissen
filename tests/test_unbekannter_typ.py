"""Einträge mit unbekanntem Eintragstyp.

Hintergrund: In der Verwaltung war „Eintragstyp“ ein freies Textfeld. Wer dort
„Kapitel“ statt „grundlagenkapitel“ eintrug, legte damit einen Eintrag an, der
beim Anzeigen des Dokuments einen Serverfehler auslöste – und zwar für das
*ganze* Dokument, nicht nur für diesen einen Eintrag.

Zwei Dinge müssen stimmen: so etwas darf nicht mehr entstehen, und falls es
doch vorkommt (altes Modul entfernt, Daten von Hand eingespielt), muss die App
es aushalten und erklären.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from eintragstypen.registry import registry
from kern.models import Eintrag, Status

pytestmark = pytest.mark.django_db

PASSWORT = "testpasswort-sehr-lang"


def anmelden(client, nutzer):
    assert client.login(email=nutzer.email, password=PASSWORT)
    return client


@pytest.fixture
def kaputter_eintrag(dokument, admin_nutzer):
    """Ein Eintrag mit einem Typ, den es nicht gibt.

    Angelegt mit ``Model.save()`` unter Umgehung der Prüfung – genau so, wie er
    vor der Korrektur über die Verwaltung entstand.
    """
    eintrag = Eintrag(
        dokument=dokument,
        eintragstyp="Kapitel",
        kennung="1.1",
        titel="Von Hand angelegt",
        status=Status.ENTWURF,
        erstellt_von=admin_nutzer,
    )
    eintrag.save()
    return eintrag


# --- So etwas darf nicht mehr entstehen -----------------------------------


def test_das_feld_bietet_eine_auswahl_an():
    """Ohne Auswahlliste tippt man im Zweifel den Klartextnamen ein."""
    feld = Eintrag._meta.get_field("eintragstyp")
    moegliche = {wert for wert, _ in feld.get_choices(include_blank=False)}

    assert moegliche == {"grundlagenkapitel", "ritual", "vorhaben"}
    assert moegliche == {s for s, _ in registry.auswahl()}


def test_unbekannter_typ_wird_abgelehnt(dokument):
    eintrag = Eintrag(dokument=dokument, eintragstyp="Kapitel", kennung="X-1", titel="Test")

    with pytest.raises(ValidationError) as fehler:
        eintrag.full_clean()

    meldung = str(fehler.value)
    assert "Kapitel" in meldung
    assert "grundlagenkapitel" in meldung, "Die Meldung soll die gültigen Werte nennen."


def test_im_dokumenttyp_nicht_vorgesehener_typ_wird_abgelehnt(dokument):
    dokument.dokumenttyp.eintragstypen = ["grundlagenkapitel"]
    dokument.dokumenttyp.save()
    eintrag = Eintrag(dokument=dokument, eintragstyp="vorhaben", kennung="V-9-01", titel="Test")

    with pytest.raises(ValidationError, match="nicht vorgesehen"):
        eintrag.full_clean()


def test_gueltiger_typ_geht_durch(dokument):
    eintrag = Eintrag(dokument=dokument, eintragstyp="vorhaben", kennung="V-9-02", titel="Test")

    eintrag.full_clean()  # darf nicht werfen


def test_verwaltung_weist_unbekannten_typ_zurueck(client, admin_nutzer, dokument):
    """Der Weg, auf dem der Fehler entstand: das Formular der Verwaltung."""
    anmelden(client, admin_nutzer)

    antwort = client.post(
        reverse("admin:kern_eintrag_add"),
        {
            "dokument": str(dokument.pk),
            "eintragstyp": "Kapitel",
            "kennung": "1.1",
            "titel": "Von Hand angelegt",
            "status": Status.ENTWURF,
            "position": "0",
            "daten": "{}",
            "verlinkungen-TOTAL_FORMS": "0",
            "verlinkungen-INITIAL_FORMS": "0",
        },
    )

    assert antwort.status_code == 200, "Das Formular soll wieder erscheinen."
    assert not Eintrag.objects.filter(kennung="1.1").exists()


# --- Und falls es doch vorkommt -------------------------------------------


def test_dokument_bleibt_lesbar(client, lehrkraft, kaputter_eintrag, dokument):
    """Vorher riss ein einziger Datensatz das ganze Dokument mit (500)."""
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("kern:dokument", args=[dokument.schluessel]))

    assert antwort.status_code == 200
    inhalt = antwort.content.decode()
    assert "Rahmenbedingungen der fachlichen Arbeit" in inhalt
    assert "Unbekannter Eintragstyp" in inhalt


def test_der_eintrag_selbst_erklaert_das_problem(client, admin_nutzer, kaputter_eintrag, dokument):
    anmelden(client, admin_nutzer)

    antwort = client.get(reverse("kern:eintrag", args=[dokument.schluessel, "1.1"]))
    inhalt = antwort.content.decode()

    assert antwort.status_code == 200
    assert "den die App nicht kennt" in inhalt
    # Die Administration bekommt den Weg zur Richtigstellung gezeigt.
    assert reverse("admin:kern_eintrag_change", args=[kaputter_eintrag.pk]) in inhalt


def test_bearbeiten_fuehrt_zurueck_statt_zu_bersten(
    client, admin_nutzer, kaputter_eintrag, dokument
):
    anmelden(client, admin_nutzer)

    antwort = client.get(
        reverse("kern:eintrag_bearbeiten", args=[dokument.schluessel, "1.1"]), follow=True
    )

    assert antwort.status_code == 200
    assert "den die App nicht kennt" in antwort.content.decode()


def test_platzhalter_hat_keine_felder(kaputter_eintrag):
    typ = kaputter_eintrag.typ

    assert typ.ist_platzhalter
    assert typ.felder == ()
    assert kaputter_eintrag.typ_bekannt is False
    assert "Kapitel" in typ.name


def test_suche_und_auswertungen_stolpern_nicht(client, lehrkraft, kaputter_eintrag, dokument):
    anmelden(client, lehrkraft)

    for adresse in (
        reverse("suche:suchen") + "?q=Hand",
        reverse("deutsch:abdeckung", args=[dokument.schluessel]),
        reverse("kern:aenderungen", args=[dokument.schluessel]),
        reverse("kern:fassungen", args=[dokument.schluessel, "1.1"]),
    ):
        assert client.get(adresse).status_code == 200, adresse


# --- Das Aufräum-Kommando --------------------------------------------------


def test_kommando_findet_den_eintrag(kaputter_eintrag, capsys):
    call_command("eintraege_pruefen")

    ausgabe = capsys.readouterr().out
    assert "1.1" in ausgabe
    assert "'Kapitel'" in ausgabe
    assert "--setzen" in ausgabe


def test_kommando_stellt_richtig(kaputter_eintrag):
    call_command("eintraege_pruefen", setzen="grundlagenkapitel", verbosity=0)

    kaputter_eintrag.refresh_from_db()
    assert kaputter_eintrag.eintragstyp == "grundlagenkapitel"
    assert kaputter_eintrag.typ_bekannt


def test_kommando_lehnt_einen_unsinnigen_zieltyp_ab(kaputter_eintrag):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="kein Eintragstyp"):
        call_command("eintraege_pruefen", setzen="Quatsch", verbosity=0)

    kaputter_eintrag.refresh_from_db()
    assert kaputter_eintrag.eintragstyp == "Kapitel"


def test_kommando_meldet_sauberen_stand(dokument, capsys):
    call_command("eintraege_pruefen")

    assert "Alle Einträge haben einen gültigen Typ." in capsys.readouterr().out
