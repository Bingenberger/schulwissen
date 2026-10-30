"""Textextraktion aus Anhängen und die Nextcloud-Verlinkung (SPEC.md §9, §10)."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from kern import extraktion, nextcloud
from kern.models import Anhang

pytestmark = pytest.mark.django_db

PASSWORT = "testpasswort-sehr-lang"


def anmelden(client, nutzer):
    assert client.login(email=nutzer.email, password=PASSWORT)
    return client


# --- Extraktion ------------------------------------------------------------


def test_lesbare_endungen():
    assert extraktion.ist_lesbar("Konzept.pdf")
    assert extraktion.ist_lesbar("Arbeitsplan.docx")
    assert extraktion.ist_lesbar("Protokoll.odt")
    assert extraktion.ist_lesbar("notizen.txt")
    assert not extraktion.ist_lesbar("Bild.jpg")
    assert not extraktion.ist_lesbar("ohne-endung")


def test_text_aus_txt(tmp_path):
    datei = tmp_path / "notizen.txt"
    datei.write_text("Märchen   sind\n\n  wichtig.", encoding="utf-8")

    assert extraktion.text_holen(datei, "notizen.txt") == "Märchen sind wichtig."


def test_text_aus_txt_mit_anderer_kodierung(tmp_path):
    datei = tmp_path / "alt.txt"
    datei.write_bytes("Märchen und Grüße".encode("cp1252"))

    assert "Märchen" in extraktion.text_holen(datei, "alt.txt")


def test_text_aus_docx_nimmt_tabellen_mit(tmp_path):
    """Die Arbeitspläne der Schule stecken in Word-Tabellen."""
    import docx

    pfad = tmp_path / "plan.docx"
    dokument = docx.Document()
    dokument.add_paragraph("Arbeitsplan Deutsch")
    tabelle = dokument.add_table(rows=1, cols=2)
    tabelle.rows[0].cells[0].text = "Vorhaben"
    tabelle.rows[0].cells[1].text = "Märchen entdecken"
    dokument.save(str(pfad))

    text = extraktion.text_holen(pfad, "plan.docx")

    assert "Arbeitsplan Deutsch" in text
    assert "Märchen entdecken" in text


def test_unbekannte_endung_wird_gemeldet(tmp_path):
    datei = tmp_path / "bild.jpg"
    datei.write_bytes(b"\xff\xd8\xff")

    with pytest.raises(extraktion.NichtLesbar, match="Leser"):
        extraktion.text_holen(datei, "bild.jpg")


def test_kaputte_datei_bricht_nichts_ab(tmp_path):
    datei = tmp_path / "kaputt.docx"
    datei.write_bytes(b"das ist kein ZIP")

    with pytest.raises(extraktion.NichtLesbar):
        extraktion.text_holen(datei, "kaputt.docx")


def test_text_wird_begrenzt(tmp_path):
    datei = tmp_path / "lang.txt"
    datei.write_text("wort " * 200_000, encoding="utf-8")

    assert len(extraktion.text_holen(datei, "lang.txt")) <= extraktion.HOECHSTLAENGE


# --- Das Kommando ----------------------------------------------------------


@pytest.fixture
def txt_anhang(importierter_arbeitsplan, lehrkraft):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    return Anhang.objects.create(
        eintrag=vorhaben,
        dokument=importierter_arbeitsplan,
        datei=SimpleUploadedFile(
            "Merkmale.txt",
            "Merkmale von Märchen: Es war einmal, Gut und Böse.".encode(),
            "text/plain",
        ),
        dateiname="Merkmale.txt",
        mimetype="text/plain",
        erstellt_von=lehrkraft,
    )


def test_kommando_liest_den_text_und_macht_ihn_auffindbar(txt_anhang, lehrkraft):
    from suche import dienste

    assert txt_anhang.index_stand is None

    call_command("anhaenge_indexieren", verbosity=0)

    txt_anhang.refresh_from_db()
    assert "Es war einmal" in txt_anhang.extrahierter_text
    assert txt_anhang.index_stand is not None

    # Und die Suche findet die Datei über ihren Inhalt.
    ergebnis = dienste.suchen(lehrkraft, "Böse")
    dateien = next(g for g in ergebnis.gruppen if g.schluessel == "dateien")
    assert "Merkmale.txt" in {t.titel for t in dateien.treffer}


def test_kommando_laeuft_nicht_zweimal_ueber_dasselbe(txt_anhang):
    call_command("anhaenge_indexieren", verbosity=0)
    txt_anhang.refresh_from_db()
    erster_stand = txt_anhang.index_stand

    call_command("anhaenge_indexieren", verbosity=0)

    txt_anhang.refresh_from_db()
    assert txt_anhang.index_stand == erster_stand


def test_nicht_lesbare_datei_wird_trotzdem_abgehakt(importierter_arbeitsplan, lehrkraft):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    anhang = Anhang.objects.create(
        eintrag=vorhaben,
        datei=SimpleUploadedFile("foto.jpg", b"\xff\xd8\xff", "image/jpeg"),
        dateiname="foto.jpg",
        erstellt_von=lehrkraft,
    )

    call_command("anhaenge_indexieren", verbosity=0)

    anhang.refresh_from_db()
    assert anhang.index_stand is not None, "Sonst versucht es jeder Lauf erneut."
    assert anhang.extrahierter_text == ""


def test_dateiname_bleibt_auch_ohne_text_auffindbar(importierter_arbeitsplan, lehrkraft):
    from suche import dienste

    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    Anhang.objects.create(
        eintrag=vorhaben,
        datei=SimpleUploadedFile("Elternbrief.jpg", b"\xff\xd8\xff", "image/jpeg"),
        dateiname="Elternbrief.jpg",
        beschreibung="Scan des Elternbriefs zur Märchenwoche",
        erstellt_von=lehrkraft,
    )

    ergebnis = dienste.suchen(lehrkraft, "Elternbrief")

    dateien = next(g for g in ergebnis.gruppen if g.schluessel == "dateien")
    assert "Elternbrief.jpg" in {t.titel for t in dateien.treffer}


# --- Nextcloud -------------------------------------------------------------


def test_ohne_zugang_ist_nextcloud_aus(settings):
    settings.NEXTCLOUD_URL = ""
    settings.NEXTCLOUD_NUTZER = ""
    settings.NEXTCLOUD_PASSWORT = ""

    assert nextcloud.ist_eingerichtet() is False
    with pytest.raises(nextcloud.NextcloudFehler, match="kein Nextcloud-Zugang"):
        nextcloud.auflisten()


def test_auswahlseite_erklaert_den_fehlenden_zugang(
    client, lehrkraft, arbeitsgruppe, importierter_arbeitsplan, settings
):
    settings.NEXTCLOUD_URL = ""
    lehrkraft.groups.add(arbeitsgruppe)
    eintrag = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    eintrag.verantwortlich_gruppe = arbeitsgruppe
    eintrag.save()
    anmelden(client, lehrkraft)

    antwort = client.get(
        reverse("kern:nextcloud_waehlen", args=[importierter_arbeitsplan.schluessel, "V-3-01"])
    )

    assert antwort.status_code == 200
    assert "kein Nextcloud-Zugang eingerichtet" in antwort.content.decode()


def test_weblink_zeigt_in_die_nextcloud_oberflaeche(settings):
    settings.NEXTCLOUD_URL = "https://cloud.ggs-ndk.de"

    link = nextcloud.weblink("Schulverwaltung/Konzepte/Leseförderung.pdf")

    assert link.startswith("https://cloud.ggs-ndk.de/apps/files/")
    assert "Schulverwaltung/Konzepte" in link.replace("%2F", "/")
    # Ausdrücklich kein öffentlicher Freigabe-Link.
    assert "/s/" not in link


def test_pfad_kann_nicht_aus_dem_wurzelordner_ausbrechen(settings):
    settings.NEXTCLOUD_URL = "https://cloud.ggs-ndk.de"
    settings.NEXTCLOUD_NUTZER = "technik"
    settings.NEXTCLOUD_PASSWORT = "geheim"

    assert nextcloud._pfad_saeubern("../../etc/passwd") == "etc/passwd"
    assert nextcloud._pfad_saeubern("/Konzepte//Deutsch/") == "Konzepte/Deutsch"


def test_webdav_antwort_wird_gelesen():
    """Eine echte PROPFIND-Antwort der Nextcloud, gekürzt."""
    xml = """<?xml version="1.0"?>
    <d:multistatus xmlns:d="DAV:">
      <d:response>
        <d:href>/remote.php/dav/files/technik/Konzepte/</d:href>
        <d:propstat><d:prop>
          <d:displayname>Konzepte</d:displayname>
          <d:resourcetype><d:collection/></d:resourcetype>
        </d:prop></d:propstat>
      </d:response>
      <d:response>
        <d:href>/remote.php/dav/files/technik/Konzepte/Deutsch/</d:href>
        <d:propstat><d:prop>
          <d:displayname>Deutsch</d:displayname>
          <d:resourcetype><d:collection/></d:resourcetype>
        </d:prop></d:propstat>
      </d:response>
      <d:response>
        <d:href>/remote.php/dav/files/technik/Konzepte/Lesen.pdf</d:href>
        <d:propstat><d:prop>
          <d:displayname>Lesen.pdf</d:displayname>
          <d:resourcetype/>
          <d:getcontentlength>12345</d:getcontentlength>
          <d:getcontenttype>application/pdf</d:getcontenttype>
          <d:getetag>"abc123"</d:getetag>
        </d:prop></d:propstat>
      </d:response>
    </d:multistatus>"""

    eintraege = nextcloud._antwort_lesen(
        xml, "https://cloud.ggs-ndk.de/remote.php/dav/files/technik/", "Konzepte"
    )

    # Der Ordner selbst taucht nicht als Eintrag auf.
    assert [e.name for e in eintraege] == ["Deutsch", "Lesen.pdf"]
    ordner, datei = eintraege
    assert ordner.ist_ordner and ordner.pfad == "Konzepte/Deutsch"
    assert not datei.ist_ordner
    assert datei.groesse == 12345
    assert datei.mimetype == "application/pdf"
    assert datei.etag == "abc123"
    assert datei.zeichen == "PDF"


def test_brotkrumen_fuehren_zurueck():
    assert nextcloud.brotkrumen("Konzepte/Deutsch") == [
        ("Nextcloud", ""),
        ("Konzepte", "Konzepte"),
        ("Deutsch", "Konzepte/Deutsch"),
    ]


def test_nextcloud_datei_verlinken(
    client, lehrkraft, arbeitsgruppe, importierter_arbeitsplan, settings
):
    settings.NEXTCLOUD_URL = "https://cloud.ggs-ndk.de"
    lehrkraft.groups.add(arbeitsgruppe)
    eintrag = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    eintrag.verantwortlich_gruppe = arbeitsgruppe
    eintrag.save()
    anmelden(client, lehrkraft)

    client.post(
        reverse("kern:nextcloud_verlinken", args=[importierter_arbeitsplan.schluessel, "V-3-01"]),
        {"pfad": "Konzepte/Deutsch/Maerchenraster.pdf", "mimetype": "application/pdf"},
    )

    anhang = eintrag.anhaenge.get()
    assert anhang.dateiname == "Maerchenraster.pdf"
    assert anhang.nextcloud_pfad == "Konzepte/Deutsch/Maerchenraster.pdf"
    assert anhang.nextcloud_link.startswith("https://cloud.ggs-ndk.de/apps/files/")
    assert not anhang.datei, "Die Datei bleibt in der Nextcloud."


def test_dieselbe_datei_wird_nicht_doppelt_verlinkt(
    client, lehrkraft, arbeitsgruppe, importierter_arbeitsplan, settings
):
    settings.NEXTCLOUD_URL = "https://cloud.ggs-ndk.de"
    lehrkraft.groups.add(arbeitsgruppe)
    eintrag = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    eintrag.verantwortlich_gruppe = arbeitsgruppe
    eintrag.save()
    anmelden(client, lehrkraft)
    adresse = reverse(
        "kern:nextcloud_verlinken", args=[importierter_arbeitsplan.schluessel, "V-3-01"]
    )

    client.post(adresse, {"pfad": "Konzepte/Lesen.pdf"})
    client.post(adresse, {"pfad": "Konzepte/Lesen.pdf"})

    assert eintrag.anhaenge.count() == 1
