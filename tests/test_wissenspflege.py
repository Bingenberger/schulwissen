"""AP09: zeitliche Lesefassungen, Rollenpflege und unveränderliche Anlagen."""

import hashlib
import io
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from eintragstypen import dienste
from kern import beschluesse, dateifassungen, funktionen, prozesse
from kern.models import (
    Anhang,
    FreigegebeneDatei,
    Funktionsbesetzung,
    Kommentar,
    Status,
)
from kern.schreibschutz import schreibstand
from kern.staende import gueltige_versionen, lesestand
from tests import test_prozesslesen
from tests.test_prozessdaten import beschluss, schreiben
from tests.test_prozesslesen import url
from tests.test_prozessveroeffentlichung import freigabedaten

handbuch = test_prozesslesen.handbuch
funktion = test_prozesslesen.funktion
pytestmark = pytest.mark.django_db


def pflegen(e, **metadaten):
    roh = dienste.Rohsatz(
        kennung=e.kennung, eintragstyp=e.eintragstyp, titel=e.titel, daten=e.daten
    )
    return dienste.speichern(e.dokument, dienste.pruefen(e.dokument, roh), metadaten=metadaten)


def text(e, titel):
    roh = dienste.Rohsatz(kennung=e.kennung, eintragstyp=e.eintragstyp, titel=titel, daten=e.daten)
    return dienste.speichern(e.dokument, dienste.pruefen(e.dokument, roh))


@pytest.mark.parametrize("nutzer", ["lesend_nutzer", "lehrkraft"])
def test_zukuenftige_freigabe_verdraengt_aktuelle_nicht(handbuch, funktion, request, nutzer):
    heute = timezone.localdate()
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    alt = e.beschlossene_version().pk
    e = text(e, "Künftige Regel")
    e = pflegen(e, wirksam_ab=heute + timedelta(days=2))
    beschluesse.beschluss_fassen(beschluss(), [e])
    neu = e.letzte_version().pk
    e.refresh_from_db()
    assert e.beschlossene_version().pk == alt
    assert lesestand(request.getfixturevalue(nutzer), e).titel == "Demoprozess"
    assert prozesse.menge(request.getfixturevalue(nutzer)).get(pk=e.pk).lese_titel == "Demoprozess"
    with patch("django.utils.timezone.localdate", return_value=heute + timedelta(days=2)):
        assert e.beschlossene_version().pk == neu
        assert lesestand(request.getfixturevalue(nutzer), e).titel == "Künftige Regel"
        assert (
            prozesse.menge(request.getfixturevalue(nutzer)).get(pk=e.pk).lese_titel
            == "Künftige Regel"
        )


def test_abgelaufene_neue_fassung_reaktiviert_keine_alte_regel(handbuch, funktion):
    heute = timezone.localdate()
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    e = text(e, "Zeitlich befristete Nachfolge")
    e = pflegen(e, wirksam_ab=heute + timedelta(days=1), wirksam_bis=heute + timedelta(days=2))
    beschluesse.beschluss_fassen(beschluss(), [e])
    with patch("django.utils.timezone.localdate", return_value=heute + timedelta(days=3)):
        assert e.beschlossene_version() is None
        assert not gueltige_versionen().filter(eintrag=e).exists()


def test_einzige_zukuenftige_fassung_nicht_als_aktuelle_lesefassung(
    client, handbuch, funktion, lesend_nutzer
):
    e = pflegen(schreiben(handbuch), wirksam_ab=timezone.localdate() + timedelta(days=3))
    beschluesse.beschluss_fassen(beschluss(), [e])
    client.force_login(lesend_nutzer)
    assert client.get(url(e)).status_code == 403
    assert not client.get(reverse("kern:prozesse")).context["karten"]


def test_prueftermin_beendet_keine_gueltigkeit_und_rolle_wechselt_ohne_kopieren(
    client, handbuch, funktion, lehrkraft, andere_lehrkraft
):
    alt = Funktionsbesetzung.objects.create(funktion=funktion, person=lehrkraft)
    e = pflegen(
        schreiben(handbuch),
        pflege_funktion=funktion,
        pruefen_am=timezone.localdate() - timedelta(days=1),
    )
    beschluesse.beschluss_fassen(beschluss(), [e])
    n = e.versionen.count()
    client.force_login(lehrkraft)
    r = client.get(reverse("kern:wissenspflege"))
    assert r.context["karten"][0]["pflege"]["personen"] == [lehrkraft.anzeigename]
    funktionen.wechseln(alt, andere_lehrkraft, timezone.localdate())
    r = client.get(reverse("kern:wissenspflege"))
    assert r.context["karten"][0]["pflege"]["personen"] == [andere_lehrkraft.anzeigename]
    assert e.versionen.count() == n
    assert e.beschlossene_version()


def test_pflegefelder_sind_snapshot_und_gemeinsam_schreibgeschuetzt(
    client, handbuch, funktion, admin_nutzer
):
    e = pflegen(schreiben(handbuch), quelle="Geprüfte Quelle 1", pflege_funktion=funktion)
    beschluesse.beschluss_fassen(beschluss(), [e])
    v = e.beschlossene_version()
    stand = schreibstand(e)
    client.force_login(admin_nutzer)
    r = client.get(url(e, "wissenspflege_bearbeiten"))
    daten = {
        "stand": r.context["formular"]["stand"].value(),
        "inhaltsart": "regel",
        "verbindlichkeit": "verbindlich",
        "quelle": "Geprüfte Quelle 2",
        "pflege_funktion": funktion.pk,
    }
    e = pflegen(e, quelle="Zwischenzeitliche Quelle")
    assert schreibstand(e) != stand
    r = client.post(url(e, "wissenspflege_bearbeiten"), daten)
    assert r.status_code == 409
    assert r.context["formular"]["quelle"].value() == "Geprüfte Quelle 2"
    v.refresh_from_db()
    assert v.quelle == "Geprüfte Quelle 1"


@pytest.mark.parametrize(
    "felder",
    [
        {"wirksam_ab": "2027-02-01", "wirksam_bis": "2027-01-01"},
        {"geprueft_am": "2099-01-01"},
        {"geprueft_am": "2020-02-01", "pruefen_am": "2020-01-01"},
    ],
)
def test_unzulaessige_datumsangaben_bleiben_im_formular(
    client, handbuch, funktion, admin_nutzer, felder
):
    e = schreiben(handbuch)
    client.force_login(admin_nutzer)
    r = client.get(url(e, "wissenspflege_bearbeiten"))
    daten = {
        "stand": r.context["formular"]["stand"].value(),
        "inhaltsart": "information",
        "verbindlichkeit": "orientierung",
        **felder,
    }
    n = e.versionen.count()
    r = client.post(url(e, "wissenspflege_bearbeiten"), daten)
    assert r.status_code == 200
    assert r.context["formular"].errors
    assert e.versionen.count() == n


def test_unberechtigte_pflege_und_verdeckte_nachfolge_ohne_titelleck(
    client, handbuch, funktion, lehrkraft, admin_nutzer
):
    e = schreiben(handbuch, nutzer=admin_nutzer)
    client.force_login(lehrkraft)
    assert client.get(url(e, "wissenspflege_bearbeiten")).status_code == 403
    handbuch.kollegiumsweit = False
    handbuch.save()
    assert (
        client.get(reverse("kern:wissenspflege"), {"ansicht": "alle"})
        .context["seite"]
        .paginator.count
        == 0
    )


def test_fehler_melden_und_erledigen_in_pflegeuebersicht(client, handbuch, funktion, lehrkraft):
    e = schreiben(handbuch, nutzer=lehrkraft)
    client.force_login(lehrkraft)
    assert (
        client.post(
            url(e, "kommentar_anlegen"),
            {"text": "Hier fehlt eine Erläuterung.", "fehlerhinweis": "on"},
        ).status_code
        == 302
    )
    r = client.get(reverse("kern:wissenspflege"), {"ansicht": "fehler"})
    assert r.context["karten"][0]["fehler"] == 1
    c = Kommentar.objects.get(eintrag=e)
    client.post(url(e, "kommentar_erledigen", c.pk))
    assert not client.get(reverse("kern:wissenspflege"), {"ansicht": "fehler"}).context["karten"]


def normative(e, inhalt=b"Freigegebener Dateistand"):
    return Anhang.objects.create(
        eintrag=e,
        dokument=e.dokument,
        dateiname="Verbindliches Formular.pdf",
        verwendung="verbindlich",
        datei=SimpleUploadedFile("formular.pdf", inhalt),
    )


def test_normative_anlage_bleibt_bytegenau_und_geaendertes_original_erkennbar(
    client, handbuch, funktion, lesend_nutzer
):
    e = schreiben(handbuch)
    a = normative(e)
    beschluesse.beschluss_fassen(beschluss(), [e])
    k = FreigegebeneDatei.objects.get(version=e.letzte_version(), original=a)
    assert k.sha256 == hashlib.sha256(b"Freigegebener Dateistand").hexdigest()
    # Same-path mutation without a new database timestamp must still be detected.
    with a.datei.storage.open(a.datei.name, "wb") as f:
        f.write(b"Inzwischen veraendert")
    client.force_login(lesend_nutzer)
    r = client.get(reverse("kern:dateifassung", args=[k.pk]))
    assert b"".join(r.streaming_content) == b"Freigegebener Dateistand"
    assert r["Cache-Control"] == "private, no-store"
    assert "Original hat sich geändert" in dateifassungen.karte(k, lesend_nutzer)["pruefhinweis"]
    assert (
        "Original hat sich geändert"
        in client.get(url(e, "version", k.version.versionsnummer)).content.decode()
    )


def test_normative_prozessreferenz_verwendet_kopie_statt_live_material(
    client, handbuch, funktion, lesend_nutzer
):
    a = Anhang.objects.create(
        dokument=handbuch,
        dateiname="Normative Demo.pdf",
        verwendung="verbindlich",
        datei=SimpleUploadedFile("normativ.pdf", b"Original"),
    )
    from tests.test_prozessdaten import beispiel

    graph = beispiel()
    graph["knoten"][2]["verweise"] = [{"typ": "anhang", "id": a.pk}]
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    k = FreigegebeneDatei.objects.get(original=a)
    a.beschreibung = "Neue Quelldatei"
    a.save()
    client.force_login(lesend_nutzer)
    r = client.get(url(e))
    dto = r.context["prozess"]["knoten"][2]["materialien"][0]
    assert dto["url"] == reverse("kern:dateifassung", args=[k.pk])
    assert "Original hat sich geändert" in dto["pruefhinweis"]


def test_externe_normative_anlage_ohne_kopie_blockiert_gesamte_freigabe(handbuch, funktion):
    e = schreiben(handbuch)
    Anhang.objects.create(
        eintrag=e,
        dokument=handbuch,
        dateiname="Live.pdf",
        verwendung="verbindlich",
        nextcloud_link="https://example.org/datei.pdf",
        dateiversion="Nextcloud-Version 17",
    )
    with pytest.raises(ValidationError, match="Dateikopie"):
        beschluesse.beschluss_fassen(beschluss(), [e])
    assert e.beschlossene_version() is None
    assert not FreigegebeneDatei.objects.exists()


def test_nextcloud_nachweis_und_gepruefte_kopie_werden_gesichert(handbuch, funktion):
    e = schreiben(handbuch)
    a = normative(e)
    a.nextcloud_link = "https://example.org/nextcloud/datei.pdf"
    a.dateiversion = "Nextcloud-Version 17 vom 31.10.2026"
    a.save()
    beschluesse.beschluss_fassen(beschluss(), [e])
    assert FreigegebeneDatei.objects.get(original=a).dateiversion == a.dateiversion


def test_freigabekopie_beachtet_beide_dokumentzugaenge(client, handbuch, funktion, lesend_nutzer):
    e = schreiben(handbuch)
    a = normative(e)
    beschluesse.beschluss_fassen(beschluss(), [e])
    k = FreigegebeneDatei.objects.get(original=a)
    handbuch.kollegiumsweit = False
    handbuch.save()
    client.force_login(lesend_nutzer)
    assert client.get(reverse("kern:dateifassung", args=[k.pk])).status_code == 404
    client.logout()
    assert client.get(reverse("kern:dateifassung", args=[k.pk])).status_code == 302


def test_routineinfo_ohne_konferenz_fachlich_freigeben(client, handbuch, admin_nutzer):
    roh = dienste.Rohsatz(
        kennung="INFO-1",
        eintragstyp="grundlagenkapitel",
        titel="Fiktive Orientierung",
        daten={"text": "<p>Geprüfte Information.</p>"},
    )
    e = dienste.speichern(handbuch, dienste.pruefen(handbuch, roh), nutzer=admin_nutzer)
    client.force_login(admin_nutzer)
    daten = freigabedaten(client, e)
    daten["freigabeart"] = "fachlich"
    r = client.post(url(e, "prozess_freigeben"), daten)
    assert r.status_code == 302
    v = e.beschlossene_version()
    assert v.beschluss.freigabeart == "fachlich"
    assert "Fachlich freigegeben" in v.beschluss.herkunft


def test_pdf_enthaelt_fassungsbezogene_wissensangaben(client, handbuch, funktion, admin_nutzer):
    e = pflegen(
        schreiben(handbuch),
        quelle="Fachquelle der freigegebenen Fassung",
        verbindlichkeit="orientierung",
    )
    beschluesse.beschluss_fassen(beschluss(), [e])
    client.force_login(admin_nutzer)
    r = client.get(url(e, "prozess_pdf"))
    t = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
    assert "Fachquelle der freigegebenen Fassung" in t
    assert "Zur Orientierung" in t


def test_json_rundlauf_erhaelt_wissensangaben_als_entwurf(handbuch, funktion, admin_nutzer):
    import json

    from eintragstypen.import_json import uebernehmen_json
    from kern import exporte

    e = pflegen(
        schreiben(handbuch),
        inhaltsart="regel",
        verbindlichkeit="verbindlich",
        pflege_funktion=funktion,
        quelle="Fachquelle 17",
        wirksam_ab=timezone.localdate(),
        pruefen_am=timezone.localdate() + timedelta(days=30),
    )
    daten = json.loads(exporte.dokument_json(handbuch))
    assert daten["eintraege"][0]["wissensangaben"]["pflege_funktion"] == funktion.schluessel
    bericht = uebernehmen_json(daten, handbuch, nutzer=admin_nutzer)
    assert bericht.ok, bericht.als_text()
    e.refresh_from_db()
    assert e.quelle == "Fachquelle 17"
    assert e.letzte_version().pruefen_am == e.pruefen_am
    assert e.status == Status.ENTWURF


def test_vergleich_erkennt_reine_gueltigkeitsaenderung(handbuch, funktion):
    from kern import vergleich

    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    alt = e.beschlossene_version()
    e = pflegen(e, wirksam_bis=timezone.localdate() + timedelta(days=7))
    v = vergleich.vergleichen(alt, e.letzte_version())
    assert any(f.schluessel == "wissen_wirksam_bis" for f in v.geaenderte_felder)
    assert beschluesse.aenderungen_seit_beschluss(handbuch)["geaendert"]


def test_korrupte_freigabekopie_wird_nicht_ausgeliefert(client, handbuch, funktion, lesend_nutzer):
    e = schreiben(handbuch)
    a = normative(e)
    beschluesse.beschluss_fassen(beschluss(), [e])
    k = FreigegebeneDatei.objects.get(original=a)
    FreigegebeneDatei.objects.filter(pk=k.pk).update(inhalt=b"Manipuliert")
    client.force_login(lesend_nutzer)
    assert client.get(reverse("kern:dateifassung", args=[k.pk])).status_code == 403


def test_ungueltige_zweite_anlage_rollt_auch_erste_kopie_zurueck(handbuch, funktion):
    e = schreiben(handbuch)
    normative(e)
    Anhang.objects.create(
        eintrag=e,
        dokument=handbuch,
        dateiname="Ohne Kopie.pdf",
        verwendung="verbindlich",
        nextcloud_link="https://example.org/ohne.pdf",
    )
    with pytest.raises(ValidationError):
        beschluesse.beschluss_fassen(beschluss(), [e])
    assert not FreigegebeneDatei.objects.exists()
    assert e.beschlossene_version() is None


def test_lesekonto_hat_keinen_pflegezugriff(client, lesend_nutzer):
    client.force_login(lesend_nutzer)
    assert client.get(reverse("kern:wissenspflege")).status_code == 403


def test_pflegeuebersicht_verliert_keine_aktuelle_pruefung_durch_zukuenftige_fassung(
    client, handbuch, funktion, lehrkraft
):
    heute = timezone.localdate()
    e = pflegen(schreiben(handbuch), pflege_funktion=funktion, pruefen_am=heute - timedelta(days=1))
    beschluesse.beschluss_fassen(beschluss(), [e])
    e = text(e, "Erst später gültige Regel")
    e = pflegen(e, wirksam_ab=heute + timedelta(days=5), pruefen_am=heute + timedelta(days=90))
    beschluesse.beschluss_fassen(beschluss(), [e])
    client.force_login(lehrkraft)
    r = client.get(reverse("kern:wissenspflege"))
    assert r.context["karten"][0]["eintrag"].titel == "Demoprozess"
    assert r.context["karten"][0]["eintrag"].pruefen_am == heute - timedelta(days=1)


def test_dateiaenderung_zwischen_standpruefung_und_kopie_rollt_freigabe_zurueck(
    client, handbuch, funktion, admin_nutzer
):
    e = schreiben(handbuch)
    a = normative(e)
    client.force_login(admin_nutzer)
    daten = freigabedaten(client, e)
    original_fassen = beschluesse.beschluss_fassen

    def waehrend_freigabe(*args, **kwargs):
        with a.datei.storage.open(a.datei.name, "wb") as f:
            f.write(b"Parallel geaenderte Bytes")
        return original_fassen(*args, **kwargs)

    with patch("kern.beschluesse.beschluss_fassen", side_effect=waehrend_freigabe):
        r = client.post(url(e, "prozess_freigeben"), daten)
    assert r.status_code == 409
    assert e.beschlossene_version() is None
    assert not FreigegebeneDatei.objects.exists()
