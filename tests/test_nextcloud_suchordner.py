"""Ordnerinventur, Suchrechte, ETags und Entfernung veralteter Suchtexte."""

import io
from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from kern import nextcloud, nextcloud_ordner
from kern.models import Anhang, NextcloudOrdner
from kern.nextcloud_index import indexieren
from kern.nextcloud_ordner import ordner_einlesen
from kern.staende import sichtbare_anhaenge
from suche.dienste import suchen

pytestmark = pytest.mark.django_db


@pytest.fixture
def quelle(settings):
    settings.NEXTCLOUD_URL = "https://cloud.example.org"
    settings.NEXTCLOUD_NUTZER = "technik"
    settings.NEXTCLOUD_PASSWORT = "app-passwort"
    return NextcloudOrdner.objects.create(name="Schulkonzepte", pfad="Kollegium/Konzepte")


@pytest.fixture
def baum(quelle, monkeypatch):
    daten = {
        quelle.pfad: [
            nextcloud.Eintrag("Lesen.txt", quelle.pfad + "/Lesen.txt", False, etag="stand-1"),
            nextcloud.Eintrag("Deutsch", quelle.pfad + "/Deutsch", True),
        ],
        quelle.pfad + "/Deutsch": [
            nextcloud.Eintrag("Plan.txt", quelle.pfad + "/Deutsch/Plan.txt", False, etag="stand-1"),
        ],
    }

    def auflisten(pfad):
        wert = daten[pfad]
        if isinstance(wert, Exception):
            raise wert
        return wert

    monkeypatch.setattr(nextcloud, "auflisten", auflisten)
    return daten


@pytest.fixture
def download(monkeypatch):
    anfragen = []

    def herunterladen(pfad, ziel, etag=""):
        anfragen.append((pfad, etag))
        if etag == '"stand-1"':
            return nextcloud.Download(304)
        ziel.write_text("Leseförderung im Unterricht", encoding="utf-8")
        return nextcloud.Download(200, '"stand-1"', "text/plain", ziel.stat().st_size)

    monkeypatch.setattr(nextcloud, "herunterladen", herunterladen)
    return anfragen


def dateitreffer(nutzer, begriff="Leseförderung", **filterwerte):
    return suchen(nutzer, begriff, gruppe="dateien", **filterwerte).gruppen[0]


def test_ordner_inklusive_unterordner_erscheint_in_der_suche(quelle, baum, download, lehrkraft):
    quelle.kollegiumsweit = True
    quelle.save()
    ordner_einlesen(quelle)
    assert quelle.dateien.count() == 2
    for datei in quelle.dateien.all():
        assert indexieren(datei) == "gelesen"
    gruppe = dateitreffer(lehrkraft)
    assert gruppe.gesamt == 2
    assert all(t.zusatz == "Nextcloud" for t in gruppe.treffer)
    assert all("Schulkonzepte" in t.kontext for t in gruppe.treffer)
    assert all(t.url.startswith("https://cloud.example.org/apps/files/") for t in gruppe.treffer)
    assert all(t.vorschau_url for t in gruppe.treffer)
    assert dateitreffer(lehrkraft, dokument="arbeitsplan-deutsch").gesamt == 0


def test_ohne_unterordner_werden_nur_direkte_dateien_erfasst(quelle, baum):
    quelle.unterordner = False
    quelle.save()
    ordner_einlesen(quelle)
    assert list(quelle.dateien.values_list("dateiname", flat=True)) == ["Lesen.txt"]


def test_rechte_schuetzen_dateinamen_suchtext_und_vorschau(
    quelle, baum, download, client, admin_nutzer, lehrkraft, arbeitsgruppe, andere_lehrkraft
):
    quelle.gruppen.add(arbeitsgruppe)
    lehrkraft.groups.add(arbeitsgruppe)
    ordner_einlesen(quelle)
    for datei in quelle.dateien.all():
        indexieren(datei)
    assert dateitreffer(lehrkraft).gesamt == 2
    assert dateitreffer(admin_nutzer).gesamt == 2
    assert dateitreffer(andere_lehrkraft).gesamt == 0
    assert dateitreffer(andere_lehrkraft, "Lesen.txt").gesamt == 0
    assert not sichtbare_anhaenge(AnonymousUser(), quelle.dateien.all()).exists()
    url = reverse("kern:anhang_vorschau", args=[quelle.dateien.first().pk])
    client.force_login(andere_lehrkraft)
    assert client.get(url).status_code == 404
    # Eine Rechteänderung gilt sofort und erfordert keinen neuen Indexierungslauf.
    quelle.gruppen.clear()
    assert dateitreffer(lehrkraft).gesamt == 0


def test_ohne_freigabe_sieht_nur_die_administration_dateien(quelle, baum, admin_nutzer, lehrkraft):
    ordner_einlesen(quelle)
    assert dateitreffer(admin_nutzer, "Lesen.txt").gesamt == 1
    assert dateitreffer(lehrkraft, "Lesen.txt").gesamt == 0


def test_entfernte_dateien_verlieren_auch_dateinamentreffer(quelle, baum, download, admin_nutzer):
    ordner_einlesen(quelle)
    for datei in quelle.dateien.all():
        indexieren(datei)
    baum[quelle.pfad] = []
    ordner_einlesen(quelle)
    assert dateitreffer(admin_nutzer).gesamt == 0
    assert dateitreffer(admin_nutzer, "Lesen.txt").gesamt == 0
    assert not quelle.dateien.exclude(extrahierter_text="").exists()


@pytest.mark.parametrize("status", [403, 404, 410])
def test_nicht_mehr_zugaengliche_ordner_werden_ausgeblendet(
    quelle, baum, download, admin_nutzer, status
):
    ordner_einlesen(quelle)
    for datei in quelle.dateien.all():
        indexieren(datei)
    baum[quelle.pfad] = nextcloud.NextcloudFehler("Kein Zugriff", status=status)
    ordner_einlesen(quelle)
    assert dateitreffer(admin_nutzer).gesamt == 0
    assert not quelle.dateien.filter(nextcloud_verfuegbar=True).exists()


def test_teilausfall_behaelt_den_letzten_vollstaendigen_stand(quelle, baum, download):
    ordner_einlesen(quelle)
    for datei in quelle.dateien.all():
        indexieren(datei)
    baum[quelle.pfad] = [
        nextcloud.Eintrag("Deutsch", quelle.pfad + "/Deutsch", True),
        nextcloud.Eintrag("Neu.txt", quelle.pfad + "/Neu.txt", False),
    ]
    baum[quelle.pfad + "/Deutsch"] = nextcloud.NextcloudFehler("Vorübergehend ausgefallen")
    assert "ausgefallen" in ordner_einlesen(quelle)
    assert quelle.dateien.filter(nextcloud_verfuegbar=True).count() == 2
    assert not quelle.dateien.filter(dateiname="Neu.txt").exists()
    assert all(a.extrahierter_text for a in quelle.dateien.all())


def test_etags_verhindern_erneute_textextraktion(quelle, baum, download):
    ordner_einlesen(quelle)
    datei = quelle.dateien.first()
    assert indexieren(datei) == "gelesen"
    assert indexieren(datei) == "unverändert"
    assert download[-1][1] == '"stand-1"'
    datei.refresh_from_db()
    assert "Leseförderung" in datei.extrahierter_text


def test_datei_403_entfernt_sie_aus_der_suche(quelle, baum, download, monkeypatch, admin_nutzer):
    ordner_einlesen(quelle)
    datei = quelle.dateien.first()
    indexieren(datei)
    monkeypatch.setattr(nextcloud, "herunterladen", lambda *a, **kw: nextcloud.Download(403))
    assert indexieren(datei) == "entfernt"
    assert dateitreffer(admin_nutzer, datei.dateiname).gesamt == 0


def test_deaktivieren_und_pfadwechsel_blenden_alte_treffer_sofort_aus(
    quelle, baum, download, admin_nutzer
):
    ordner_einlesen(quelle)
    for datei in quelle.dateien.all():
        indexieren(datei)
    quelle.aktiv = False
    quelle.save()
    assert dateitreffer(admin_nutzer).gesamt == 0
    quelle.aktiv = True
    quelle.pfad = "Neuer/Ordner"
    quelle.save()
    assert dateitreffer(admin_nutzer).gesamt == 0
    assert not quelle.dateien.exclude(extrahierter_text="").exists()


def test_laufgrenze_loescht_keine_bestehenden_dateien(quelle, baum, monkeypatch):
    ordner_einlesen(quelle)
    monkeypatch.setattr(nextcloud_ordner, "MAX_ORDNER", 1)
    assert "Laufgrenze" in ordner_einlesen(quelle)
    assert quelle.dateien.filter(nextcloud_verfuegbar=True).count() == 2


@pytest.mark.parametrize(
    "pfad", ["../Geheim", "Konzepte/../Geheim", "https://cloud.example.org", "/"]
)
def test_ungueltige_ordnerpfade_werden_abgelehnt(pfad):
    with pytest.raises(ValidationError):
        NextcloudOrdner(name="Ungültig", pfad=pfad).full_clean()


def test_ueberlappende_aktive_ordner_werden_abgelehnt(quelle):
    with pytest.raises(ValidationError):
        NextcloudOrdner(name="Doppelt", pfad=quelle.pfad + "/Deutsch").full_clean()


def test_laufende_indexierung_kann_keine_deaktivierte_quelle_wieder_freigeben(
    quelle, baum, monkeypatch
):
    ordner_einlesen(quelle)
    datei = quelle.dateien.first()

    def herunterladen(pfad, ziel, etag=""):
        quelle.aktiv = False
        quelle.save()
        ziel.write_text("Soll nicht indiziert werden", encoding="utf-8")
        return nextcloud.Download(200)

    monkeypatch.setattr(nextcloud, "herunterladen", herunterladen)
    assert indexieren(datei) == "übersprungen"
    datei.refresh_from_db()
    assert datei.extrahierter_text == ""
    assert not datei.nextcloud_verfuegbar


def test_dateibudget_arbeitet_auch_bei_regelmaessiger_inventur_alle_dateien_ab(
    quelle, baum, download
):
    baum[quelle.pfad] = [
        nextcloud.Eintrag(name, quelle.pfad + "/" + name, False, etag="stand-1")
        for name in ["A.png", "B.png", "C.txt"]
    ]
    for _ in range(3):
        NextcloudOrdner.objects.filter(pk=quelle.pk).update(
            geprueft_am=timezone.now() - timedelta(minutes=16)
        )
        call_command("nextcloud_indexieren", anzahl=1, stdout=io.StringIO())
    assert quelle.dateien.filter(index_stand__isnull=False).count() == 3
    assert quelle.dateien.get(dateiname="C.txt").extrahierter_text
    assert len(download) == 1  # Bilder werden nur über ihren Namen erfasst.


def test_verwaltung_ist_auf_administration_beschraenkt(client, admin_nutzer, lehrkraft):
    url = reverse("admin:kern_nextcloudordner_add")
    client.force_login(admin_nutzer)
    assert client.get(url).status_code == 200
    lehrkraft.is_staff = True
    lehrkraft.save()
    client.force_login(lehrkraft)
    assert client.get(url).status_code == 403


def test_dateiausschnitte_enthalten_keine_aktiven_html_elemente(quelle, admin_nutzer, client):
    datei = Anhang.objects.create(
        nextcloud_ordner=quelle, nextcloud_pfad=quelle.pfad + "/Test.txt", dateiname="Test.txt",
        nextcloud_link="https://cloud.example.org/apps/files/",
        extrahierter_text='Leseförderung <img src=x onerror="alert(1)"> im Unterricht',
    )
    client.force_login(admin_nutzer)
    antwort = client.get(reverse("suche:suchen"), {"q": "Leseförderung", "gruppe": "dateien"})
    assert antwort.status_code == 200
    assert b"<img src=x" not in antwort.content
    assert b'onerror="alert' not in antwort.content
    assert reverse("kern:anhang_vorschau", args=[datei.pk]).encode() in antwort.content
