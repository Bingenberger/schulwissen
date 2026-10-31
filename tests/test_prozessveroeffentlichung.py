"""AP08: gültige Einstiege, Suche, konkrete Freigabe und Pilotvorlage."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from eintragstypen.import_json import pruefen_json, uebernehmen_json
from kern import beschluesse, prozesse
from kern.models import (
    Anhang,
    Beschluss,
    Eintrag,
    Gremium,
    Schulfunktion,
    Status,
    Zugangsregel,
)
from suche import dienste as suche
from tests import test_prozesslesen
from tests.test_prozessdaten import beispiel, beschluss, schreiben
from tests.test_prozesslesen import url

handbuch = test_prozesslesen.handbuch
funktion = test_prozesslesen.funktion

pytestmark = pytest.mark.django_db


def freigabedaten(client, e):
    r = client.get(url(e, "prozess_freigeben"))
    assert r.status_code == 200
    g, _ = Gremium.objects.get_or_create(name="Schulleitung")
    return {
        "stand": r.context["formular"]["stand"].value(),
        "datum": timezone.localdate().isoformat(),
        "gremium": g.pk,
        "text": "Ausdrücklich fiktive Freigabe nach fachlicher Bedienprüfung.",
        "geprueft": "on",
        "material_geprueft": "on",
    }


def gruppe(nutzer, q):
    return suche.suchen(nutzer, q, gruppe="prozesse").gruppen[0]


@pytest.mark.parametrize("rolle", ["lehrkraft", "lesend_nutzer", "admin_nutzer"])
def test_portal_und_suche_zeigen_gueltige_fassung_statt_neuerem_entwurf(
    client, handbuch, funktion, request, rolle
):
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    nummer = e.beschlossene_version().versionsnummer
    graph = beispiel()
    graph["knoten"][0]["titel"] = "GeheimerXylophonEntwurf"
    e = schreiben(handbuch, graph)
    Eintrag.objects.filter(pk=e.pk).update(titel="GeheimerXylophonTitel")
    nutzer = request.getfixturevalue(rolle)
    client.force_login(nutzer)
    r = client.get(reverse("kern:prozesse"))
    assert r.status_code == 200
    assert r.context["karten"][0]["titel"] == "Demoprozess"
    assert r.context["karten"][0]["url"] == url(e, "version", nummer)
    assert "GeheimerXylophon" not in r.content.decode()
    treffer = gruppe(nutzer, "Demoprozess").treffer
    assert treffer[0].url == url(e, "version", nummer)
    assert gruppe(nutzer, "GeheimerXylophon").gesamt == 0
    assert not suche.vorschlaege(nutzer, "GeheimerXylophon")
    assert suche.vorschlaege(nutzer, "Demoprozess")[0].url == url(e, "version", nummer)
    assert client.get(url(e, "version", nummer)).context["version"].titel == "Demoprozess"


def test_arbeitsstaende_sind_explizit_und_nicht_fuer_lesende(
    client, handbuch, funktion, lehrkraft, lesend_nutzer
):
    e = schreiben(handbuch)
    client.force_login(lehrkraft)
    assert client.get(reverse("kern:prozesse")).context["seite"].paginator.count == 0
    r = client.get(reverse("kern:prozesse"), {"stand": "arbeit"})
    assert r.context["karten"][0]["url"] == url(e)
    assert "Entwürfe lesen" in r.content.decode()
    client.force_login(lesend_nutzer)
    assert client.get(reverse("kern:prozesse"), {"stand": "arbeit"}).status_code == 403


def test_suche_nach_anlass_und_aktuellem_funktionsnamen_ohne_neue_version(
    handbuch, funktion, lehrkraft
):
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    anzahl = e.versionen.count()
    funktion.name = "Sonderpädagogische Beratung"
    funktion.save()
    assert gruppe(lehrkraft, "Sonderpädagogische").gesamt == 1
    assert gruppe(lehrkraft, "Fiktiver Testablauf").gesamt == 1
    assert suche.vorschlaege(lehrkraft, "Sonderpädagogische")[0].zusatz == "Prozess"
    assert e.versionen.count() == anzahl
    assert not next(
        g for g in suche.suchen(lehrkraft, "Demoprozess").gruppen if g.schluessel == "eintraege"
    ).treffer


def test_gesperrte_und_archivierte_prozesse_verschwinden_aus_aller_suche(
    client, handbuch, funktion, lehrkraft
):
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    handbuch.kollegiumsweit = False
    handbuch.save()
    client.force_login(lehrkraft)
    assert client.get(reverse("kern:prozesse")).context["seite"].paginator.count == 0
    assert gruppe(lehrkraft, "Demoprozess").gesamt == 0
    assert not suche.vorschlaege(lehrkraft, "Demoprozess")
    handbuch.kollegiumsweit = True
    handbuch.save()
    Eintrag.objects.filter(pk=e.pk).update(status=Status.ARCHIVIERT)
    assert gruppe(lehrkraft, "Demoprozess").gesamt == 0


def test_filter_zaehlung_und_blaettern_nutzen_veroeffentlichte_staende(
    client, handbuch, funktion, lehrkraft
):
    for n in range(13):
        e = schreiben(handbuch, kennung=f"PR-{n:02}")
        beschluesse.beschluss_fassen(beschluss(), [e])
    schreiben(handbuch, kennung="PR-NICHT-FREI")
    client.force_login(lehrkraft)
    r = client.get(reverse("kern:prozesse"))
    assert len(r.context["karten"]) == 12
    assert r.context["seite"].paginator.count == 13
    assert len(client.get(reverse("kern:prozesse"), {"seite": 2}).context["karten"]) == 1
    assert gruppe(lehrkraft, "Demoprozess").gesamt == 13
    assert suche.suchen(lehrkraft, "Demoprozess", gruppe="prozesse", status="entwurf").gesamt == 0


def test_freigabe_dokumentiert_pruefer_und_unveraenderlichen_schnappschuss(
    client, handbuch, funktion, admin_nutzer
):
    e = schreiben(handbuch)
    client.force_login(admin_nutzer)
    daten = freigabedaten(client, e)
    anzahl = e.versionen.count()
    r = client.post(url(e, "prozess_freigeben"), daten)
    assert r.status_code == 302
    e.refresh_from_db()
    v = e.beschlossene_version()
    assert e.status == Status.BESCHLOSSEN
    assert v.beschluss.erstellt_von == admin_nutzer
    assert v.beschluss.gremium.name == "Schulleitung"
    assert v.beschluss.text == daten["text"]
    assert e.versionen.count() == anzahl
    assert client.post(url(e, "prozess_freigeben"), daten).status_code == 409
    assert Beschluss.objects.count() == 1


def test_freigaberecht_ist_vom_bearbeitungsrecht_getrennt(client, handbuch, funktion, lehrkraft):
    e = schreiben(handbuch, nutzer=lehrkraft)
    client.force_login(lehrkraft)
    assert client.get(url(e, "prozess_freigeben")).status_code == 403
    assert client.post(url(e, "prozess_freigeben"), {}).status_code == 403
    Zugangsregel.objects.create(nutzer=lehrkraft, dokument=handbuch, freigeben=True)
    assert client.post(url(e, "prozess_freigeben"), freigabedaten(client, e)).status_code == 302


@pytest.mark.parametrize(
    "art",
    ["unvollstaendig", "funktion_archiviert", "zukuenftig", "bestaetigung_fehlt", "token_falsch"],
)
def test_unzulaessige_freigabe_schreibt_nichts(client, handbuch, funktion, admin_nutzer, art):
    graph = beispiel()
    if art == "unvollstaendig":
        graph["verbindungen"] = []
    e = schreiben(handbuch, graph)
    client.force_login(admin_nutzer)
    daten = freigabedaten(client, e)
    if art == "funktion_archiviert":
        Schulfunktion.objects.filter(pk=funktion.pk).update(archiviert=True)
    if art == "zukuenftig":
        daten["datum"] = (timezone.localdate() + timedelta(days=1)).isoformat()
    if art == "bestaetigung_fehlt":
        daten.pop("geprueft")
    if art == "token_falsch":
        daten["stand"] = "manipuliert"
    r = client.post(url(e, "prozess_freigeben"), daten)
    assert r.status_code in (200, 409)
    assert r.context["formular"].errors
    assert Beschluss.objects.count() == 0
    assert e.beschlossene_version() is None


def test_freigabe_konflikt_erhaelt_nachweis_und_akzeptiert_keinen_neueren_stand(
    client, handbuch, funktion, admin_nutzer
):
    e = schreiben(handbuch)
    client.force_login(admin_nutzer)
    daten = freigabedaten(client, e)
    graph = beispiel()
    graph["knoten"][0]["titel"] = "Zwischenzeitlich geändert"
    schreiben(handbuch, graph)
    r = client.post(url(e, "prozess_freigeben"), daten)
    assert r.status_code == 409
    assert r.context["formular"]["text"].value() == daten["text"]
    assert Beschluss.objects.count() == 0


def test_materialaenderung_waehrend_pruefung_verhindert_freigabe(
    client, handbuch, funktion, admin_nutzer
):
    a = Anhang.objects.create(
        dokument=handbuch, dateiname="Demo.pdf", nextcloud_link="https://example.org/demo.pdf"
    )
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [{"typ": "anhang", "id": a.pk}]
    e = schreiben(handbuch, graph)
    client.force_login(admin_nutzer)
    daten = freigabedaten(client, e)
    a.nextcloud_link = "https://example.org/geaendert.pdf"
    a.save()
    assert client.post(url(e, "prozess_freigeben"), daten).status_code == 409
    assert Beschluss.objects.count() == 0
    daten = freigabedaten(client, e)
    daten.pop("material_geprueft")
    assert client.post(url(e, "prozess_freigeben"), daten).context["formular"].errors
    daten["material_geprueft"] = "on"
    assert client.post(url(e, "prozess_freigeben"), daten).status_code == 302
    assert "Materialien und deren Fassung" in Beschluss.objects.get().text
    r = client.get(url(e, "version", e.letzte_version().versionsnummer))
    assert "Veränderlicher Materiallink" in r.content.decode()
    a.save()
    r = client.get(url(e, "version", e.letzte_version().versionsnummer))
    assert "Datei seit der Freigabe geändert" in r.content.decode()


def test_fiktive_importvorlage_ist_vollstaendig_und_durchlaeuft_freigabe(handbuch, admin_nutzer):
    handbuch.schluessel = "demo-prozesswerkzeug"
    handbuch.save()
    Schulfunktion.objects.create(schluessel="demo-materialdienst", name="Demo-Materialdienst")
    material = json.loads(Path("docs/beispiele/prozesswerkzeug-demo-material.json").read_text())
    uebernehmen_json(material, handbuch, nutzer=admin_nutzer)
    inhalt = json.loads(Path("docs/beispiele/prozesswerkzeug-demo.json").read_text())
    pruefung = pruefen_json(inhalt, handbuch, nutzer=admin_nutzer)
    assert pruefung.ok, pruefung.als_text()
    uebernehmen_json(inhalt, handbuch, nutzer=admin_nutzer)
    beschluesse.beschluss_fassen(
        beschluss(), [handbuch.eintraege.get(kennung="DEMO-INFO")], nutzer=admin_nutzer
    )
    e = handbuch.eintraege.get(kennung="PR-DEMO-01")
    beschluesse.beschluss_fassen(beschluss(), [e], nutzer=admin_nutzer)
    assert prozesse.suchen(prozesse.menge(admin_nutzer), "Demomaterial").count() == 1


def test_prozessanhaenge_bleiben_in_dateisuche(handbuch, funktion, lehrkraft):
    e = schreiben(handbuch)
    Anhang.objects.create(
        eintrag=e,
        dokument=handbuch,
        dateiname="Xylophondatei.pdf",
        extrahierter_text="Xylophondatei",
    )
    assert suche.suchen(lehrkraft, "Xylophondatei", gruppe="dateien").gesamt == 1


def test_anonyme_prozesszugriffe_sind_geschuetzt(client, handbuch, funktion):
    e = schreiben(handbuch)
    assert client.get(reverse("kern:prozesse")).status_code == 302
    assert client.get(url(e, "prozess_freigeben")).status_code == 302
