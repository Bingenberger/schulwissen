"""Anhänge direkt beim Anlegen und Bearbeiten eines Eintrags."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from kern import nextcloud
from kern.models import Anhang

pytestmark = pytest.mark.django_db


def erfassung(dokument):
    return reverse("kern:eintrag_neu", args=[dokument.schluessel, "grundlagenkapitel"])


def test_neues_kapitel_mit_mehreren_dateien(client, redaktion_nutzer, dokument, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client.force_login(redaktion_nutzer)
    seite = client.get(erfassung(dokument))
    assert b"multipart/form-data" in seite.content
    assert b"Nextcloud durchsuchen" in seite.content
    antwort = client.post(erfassung(dokument), {
        "titel": "Kapitel mit Material", "status": "entwurf",
        "anhang_dateien": [
            SimpleUploadedFile("eins.txt", b"Erste Datei", content_type="text/plain"),
            SimpleUploadedFile("zwei.txt", b"Zweite Datei", content_type="text/plain"),
        ],
        "anhang_link": "https://cloud.example.org/s/material",
    })
    assert antwort.status_code == 302
    eintrag = dokument.eintraege.get(titel="Kapitel mit Material")
    assert eintrag.anhaenge.count() == 3
    assert eintrag.anhaenge.get(dateiname="eins.txt").datei.read() == b"Erste Datei"
    assert eintrag.anhaenge.get(dateiname="material").nextcloud_link.endswith("/s/material")


def test_nextcloud_auswahl_bleibt_bei_formularfehler(client, redaktion_nutzer, dokument, monkeypatch):
    client.force_login(redaktion_nutzer)
    monkeypatch.setattr(nextcloud, "auflisten", lambda pfad: [
        nextcloud.Eintrag("Lesen.pdf", "Konzepte/Lesen.pdf", False, 123, "application/pdf")
    ])
    url = reverse("kern:nextcloud_erfassung", args=[dokument.schluessel])
    auswahl = client.get(url, {"pfad": "Konzepte"})
    token = auswahl.context["dateien"][0]["token"]
    anzahl = dokument.eintraege.count()
    # Die Ordnerauswahl allein legt noch keinen Eintrag an.
    assert not Anhang.objects.exists()
    fehler = client.post(erfassung(dokument), {"anhang_nextcloud": [token]})
    assert fehler.status_code == 200
    assert token.encode() in fehler.content
    assert dokument.eintraege.count() == anzahl
    assert not Anhang.objects.exists()
    antwort = client.post(erfassung(dokument), {
        "titel": "Mit Nextcloud", "status": "entwurf", "anhang_nextcloud": [token, token],
    })
    assert antwort.status_code == 302
    anhang = dokument.eintraege.get(titel="Mit Nextcloud").anhaenge.get()
    assert anhang.nextcloud_pfad == "Konzepte/Lesen.pdf"
    assert anhang.groesse == 123
    assert not anhang.datei


def test_manipulierte_nextcloud_auswahl_speichert_nichts(client, redaktion_nutzer, dokument):
    client.force_login(redaktion_nutzer)
    antwort = client.post(erfassung(dokument), {
        "titel": "Ungültig", "anhang_nextcloud": ["manipuliert"],
    })
    assert antwort.status_code == 200
    assert "anhang_nextcloud" in antwort.context["formular"].errors
    assert not dokument.eintraege.filter(titel="Ungültig").exists()
    assert not Anhang.objects.exists()


def test_jede_hochgeladene_datei_wird_geprueft(
    client, redaktion_nutzer, dokument, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    client.force_login(redaktion_nutzer)
    antwort = client.post(erfassung(dokument), {
        "titel": "Mit leerer Datei",
        "anhang_dateien": [
            SimpleUploadedFile("gut.txt", b"Inhalt"),
            SimpleUploadedFile("leer.txt", b""),
        ],
    })
    assert antwort.status_code == 200
    assert "anhang_dateien" in antwort.context["formular"].errors
    assert not dokument.eintraege.filter(titel="Mit leerer Datei").exists()
    assert not Anhang.objects.exists()


def test_nextcloud_auswahl_gilt_nur_fuer_den_angemeldeten_nutzer(
    client, redaktion_nutzer, admin_nutzer, dokument, monkeypatch
):
    monkeypatch.setattr(nextcloud, "auflisten", lambda pfad: [
        nextcloud.Eintrag("Lesen.pdf", "Lesen.pdf", False)
    ])
    client.force_login(admin_nutzer)
    auswahl = client.get(reverse("kern:nextcloud_erfassung", args=[dokument.schluessel]))
    token = auswahl.context["dateien"][0]["token"]
    client.force_login(redaktion_nutzer)
    antwort = client.post(erfassung(dokument), {
        "titel": "Fremde Auswahl", "anhang_nextcloud": [token],
    })
    assert antwort.status_code == 200
    assert "anhang_nextcloud" in antwort.context["formular"].errors
    assert not dokument.eintraege.filter(titel="Fremde Auswahl").exists()


def test_lesende_duerfen_nextcloud_nicht_durchsuchen(client, lesend_nutzer, dokument, monkeypatch):
    client.force_login(lesend_nutzer)

    def unerlaubt(*args, **kwargs):
        pytest.fail("Nextcloud darf ohne Bearbeitungsrecht nicht abgefragt werden.")

    monkeypatch.setattr(nextcloud, "auflisten", unerlaubt)
    antwort = client.get(reverse("kern:nextcloud_erfassung", args=[dokument.schluessel]))
    assert antwort.status_code in (403, 404)


def test_bearbeiten_ergaenzt_anhaenge(client, redaktion_nutzer, dokument, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client.force_login(redaktion_nutzer)
    client.post(erfassung(dokument), {"titel": "Kapitel", "status": "entwurf"})
    eintrag = dokument.eintraege.get(titel="Kapitel")
    vorhanden = Anhang.objects.create(
        eintrag=eintrag, dokument=dokument, dateiname="Alt", erstellt_von=redaktion_nutzer,
        nextcloud_link="https://cloud.example.org/s/alt",
    )
    url = reverse("kern:eintrag_bearbeiten", args=[dokument.schluessel, eintrag.kennung])
    formular = client.get(url).context["formular"]
    antwort = client.post(url, {
        "titel": "Kapitel", "status": "entwurf",
        "ausgangsstand": formular["ausgangsstand"].value(),
        "anhang_dateien": SimpleUploadedFile("neu.txt", b"Neues Material"),
    })
    assert antwort.status_code == 302
    assert eintrag.anhaenge.count() == 2
    assert eintrag.anhaenge.filter(pk=vorhanden.pk).exists()
