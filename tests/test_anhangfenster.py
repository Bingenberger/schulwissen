"""Vollständige PDF-Vorschau, Dateirechte und sicheres Löschen von Anhängen."""

import io

import pytest
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from pypdf import PdfReader, PdfWriter

from kern import nextcloud
from kern.models import Anhang, FreigegebeneDatei, Verlinkung
from tests.test_anhaenge_erfassung import erfassung

pytestmark = pytest.mark.django_db


@pytest.fixture
def kapitel(client, redaktion_nutzer, dokument):
    client.force_login(redaktion_nutzer)
    antwort = client.post(erfassung(dokument), {"titel": "Dateifenster", "status": "entwurf"})
    assert antwort.status_code == 302
    return dokument.eintraege.get(titel="Dateifenster")


@pytest.fixture
def pdf_bytes():
    pdf = PdfWriter()
    pdf.add_blank_page(width=300, height=400)
    pdf.add_blank_page(width=400, height=300)
    puffer = io.BytesIO()
    pdf.write(puffer)
    return puffer.getvalue()


@pytest.fixture
def anhang(kapitel, pdf_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return Anhang.objects.create(
        eintrag=kapitel, dokument=kapitel.dokument, dateiname="Zwei Seiten.pdf",
        datei=SimpleUploadedFile("mehrseitig.pdf", pdf_bytes, content_type="application/pdf"),
    )


def loesch_url(anhang):
    return reverse("kern:anhang_loeschen", args=[
        anhang.eintrag.dokument.schluessel, anhang.eintrag.kennung, anhang.pk,
    ])


def test_pdf_vorschau_enthaelt_alle_seiten(client, anhang):
    antwort = client.get(reverse("kern:anhang_vorschau", args=[anhang.pk]))
    assert antwort.status_code == 200
    assert antwort["Content-Type"] == "application/pdf"
    assert antwort["Content-Disposition"].startswith("inline")
    assert antwort["X-Frame-Options"] == "SAMEORIGIN"
    assert antwort["Cache-Control"] == "private, no-store"
    inhalt = b"".join(antwort.streaming_content)
    assert len(PdfReader(io.BytesIO(inhalt)).pages) == 2
    antwort.close()


def test_vorschau_ist_kein_oeffentlicher_dateizugang(client, anhang, lesend_nutzer):
    client.logout()
    url = reverse("kern:anhang_vorschau", args=[anhang.pk])
    assert client.get(url).status_code == 302
    client.force_login(lesend_nutzer)
    assert client.get(url).status_code == 404  # Noch nicht freigegebener Anhang.


def test_html_wird_auch_mit_pdf_dateinamen_nicht_eingebettet(client, anhang):
    anhang.datei.save("falsch.pdf", SimpleUploadedFile("falsch.pdf", b"<script>alert(1)</script>"))
    antwort = client.get(reverse("kern:anhang_vorschau", args=[anhang.pk]))
    assert not antwort.streaming
    assert b"<script>" not in antwort.content
    assert "keine eingebettete Vorschau" in antwort.content.decode()


@pytest.mark.parametrize("vor_speichern", [False, True])
def test_nextcloud_vorschau_ist_temporaer(
    client, kapitel, pdf_bytes, monkeypatch, vor_speichern
):
    pfade = []

    def herunterladen(pfad, ziel):
        assert pfad == "Konzepte/Plan.pdf"
        ziel.write_bytes(pdf_bytes)
        pfade.append(ziel)
        return nextcloud.Download(200)

    monkeypatch.setattr(nextcloud, "herunterladen", herunterladen)
    if vor_speichern:
        token = signing.dumps({
            "nutzer": kapitel.erstellt_von_id, "dokument": kapitel.dokument_id,
            "pfad": "Konzepte/Plan.pdf", "name": "Plan.pdf",
        }, salt="anhang-erfassung")
        antwort = client.get(
            reverse("kern:nextcloud_vorschau", args=[kapitel.dokument.schluessel]),
            {"auswahl": token, "kennung": kapitel.kennung},
        )
    else:
        anhang = Anhang.objects.create(
            eintrag=kapitel, dokument=kapitel.dokument,
            nextcloud_pfad="Konzepte/Plan.pdf", dateiname="Plan.pdf",
        )
        antwort = client.get(reverse("kern:anhang_vorschau", args=[anhang.pk]))
    assert len(PdfReader(io.BytesIO(b"".join(antwort.streaming_content))).pages) == 2
    antwort.close()
    assert not pfade[0].exists()
    assert not pfade[0].parent.exists()


def test_freigabelinks_werden_nicht_vom_server_abgerufen(client, kapitel, monkeypatch):
    anhang = Anhang.objects.create(
        eintrag=kapitel, dokument=kapitel.dokument, dateiname="Link",
        nextcloud_link="https://cloud.example.org/s/token",
    )

    def unerlaubt(*args, **kwargs):
        pytest.fail("Ein freier Link darf keine serverseitige Anfrage auslösen.")

    monkeypatch.setattr(nextcloud, "herunterladen", unerlaubt)
    antwort = client.get(reverse("kern:anhang_vorschau", args=[anhang.pk]))
    assert "Freigabe-Link" in antwort.content.decode()


def test_auswahlvorschau_prueft_signatur_und_nutzer(client, kapitel, andere_lehrkraft, monkeypatch):
    def unerlaubt(*args, **kwargs):
        pytest.fail("Unberechtigte Vorschauen dürfen nicht geladen werden.")

    monkeypatch.setattr(nextcloud, "herunterladen", unerlaubt)
    url = reverse("kern:nextcloud_vorschau", args=[kapitel.dokument.schluessel])
    assert client.get(url, {"auswahl": "ungueltig"}).status_code == 403
    token = signing.dumps({
        "nutzer": andere_lehrkraft.pk, "dokument": kapitel.dokument_id,
        "pfad": "Geheim.pdf", "name": "Geheim.pdf",
    }, salt="anhang-erfassung")
    assert client.get(url, {"auswahl": token}).status_code == 403


def test_loeschen_braucht_bestaetigung_und_bereinigt_datei(
    client, anhang, django_capture_on_commit_callbacks
):
    url = loesch_url(anhang)
    seite = client.get(url)
    assert Anhang.objects.filter(pk=anhang.pk).exists()
    assert client.post(url).status_code == 409
    speicher, name = anhang.datei.storage, anhang.datei.name
    with django_capture_on_commit_callbacks(execute=True):
        antwort = client.post(url, {"stand": seite.context["stand"]})
    assert antwort.status_code == 302
    assert not Anhang.objects.filter(pk=anhang.pk).exists()
    assert not speicher.exists(name)


def test_geaenderter_anhang_wird_nicht_mit_alter_bestaetigung_geloescht(client, anhang):
    url = loesch_url(anhang)
    token = client.get(url).context["stand"]
    anhang.beschreibung = "Inzwischen überarbeitet"
    anhang.save()
    assert client.post(url, {"stand": token}).status_code == 409
    assert Anhang.objects.filter(pk=anhang.pk).exists()


@pytest.mark.parametrize("verwendung", ["verweis", "freigabekopie"])
def test_verwendete_anhaenge_bleiben_erhalten(client, anhang, verwendung):
    if verwendung == "verweis":
        Verlinkung.objects.create(
            von_eintrag=anhang.eintrag, ziel_typ="anhang", ziel_id=str(anhang.pk), art="nutzt",
        )
    else:
        FreigegebeneDatei.objects.create(
            original=anhang, version=anhang.eintrag.letzte_version(),
            dateiname=anhang.dateiname, inhalt=b"Kopie", sha256="0" * 64, originalstand="0" * 64,
        )
    url = loesch_url(anhang)
    seite = client.get(url)
    assert seite.context["grund"]
    assert client.post(url, {"stand": seite.context["stand"]}).status_code == 409
    assert Anhang.objects.filter(pk=anhang.pk).exists()


def test_loeschen_ohne_bearbeitungsrecht_verboten(client, anhang, andere_lehrkraft):
    client.force_login(andere_lehrkraft)
    assert client.post(loesch_url(anhang)).status_code == 403
    assert Anhang.objects.filter(pk=anhang.pk).exists()


def test_bearbeitungsmaske_loescht_nur_eigene_markierte_anhaenge(client, anhang):
    eintrag = anhang.eintrag
    url = reverse("kern:eintrag_bearbeiten", args=[eintrag.dokument.schluessel, eintrag.kennung])
    seite = client.get(url)
    assert seite.content.count(b'id="nextcloud-ordner"') == 1
    assert b'data-nextcloud-oeffnen' in seite.content
    antwort = client.post(url, {
        "titel": eintrag.titel, "status": "entwurf",
        "ausgangsstand": seite.context["formular"]["ausgangsstand"].value(),
        "anhang_entfernen": [anhang.pk],
    })
    assert antwort.status_code == 302
    assert not Anhang.objects.filter(pk=anhang.pk).exists()


def test_fremder_anhang_kann_nicht_ueber_das_formular_geloescht_werden(client, anhang):
    fremd = Anhang.objects.create(
        dokument=anhang.dokument, dateiname="Anderer Anhang",
        nextcloud_link="https://cloud.example.org/s/anderer",
    )
    eintrag = anhang.eintrag
    url = reverse("kern:eintrag_bearbeiten", args=[eintrag.dokument.schluessel, eintrag.kennung])
    seite = client.get(url)
    antwort = client.post(url, {
        "titel": "Soll nicht gespeichert werden", "status": "entwurf",
        "ausgangsstand": seite.context["formular"]["ausgangsstand"].value(),
        "anhang_entfernen": [fremd.pk],
    })
    assert antwort.status_code == 200
    assert "anhang_entfernen" in antwort.context["formular"].errors
    assert Anhang.objects.filter(pk=fremd.pk).exists()
    eintrag.refresh_from_db()
    assert eintrag.titel != "Soll nicht gespeichert werden"
