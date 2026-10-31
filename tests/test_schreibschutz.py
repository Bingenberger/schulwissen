"""AP03: konkurrierende Eingaben, gemeinsame Sperren und bewusste Konfliktauflösung."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from django.db import close_old_connections, connections
from django.test import Client
from django.urls import reverse

from eintragstypen.dienste import Rohsatz, pruefen, speichern
from eintragstypen.import_json import uebernehmen_json
from kern import beschluesse
from kern.models import Beschluss, Dokument, Eintrag, Gremium, Nutzer, Status
from kern.schreibschutz import Schreibkonflikt, dokumentstand, schreibstand, token_fuer_eintrag

pytestmark = pytest.mark.django_db


def schreiben(d, titel="Basis", text="Basistext", kennung="K-90", **kwargs):
    return speichern(
        d,
        pruefen(
            d,
            Rohsatz(
                kennung=kennung,
                eintragstyp="grundlagenkapitel",
                titel=titel,
                daten={"text": f"<p>{text}</p>"},
            ),
        ),
        **kwargs,
    )


@pytest.fixture
def eintrag(dokument):
    return schreiben(dokument)


def url(e, admin=False):
    return (
        reverse("admin:kern_eintrag_change", args=[e.pk])
        if admin
        else reverse("kern:eintrag_bearbeiten", args=[e.dokument.schluessel, e.kennung])
    )


def stand(client, e, admin=False):
    r = client.get(url(e, admin))
    assert r.status_code == 200
    f = r.context["adminform"].form if admin else r.context["formular"]
    return f["ausgangsstand"].value()


def daten(token, titel="Meine Eingabe", text="Mein Text"):
    return {
        "ausgangsstand": token,
        "titel": titel,
        "f_text": f"<p>{text}</p>",
        "status": Status.ENTWURF,
    }


def admindaten(token, titel="Meine Verwaltungsänderung"):
    return {
        "ausgangsstand": token,
        "titel": titel,
        "daten": json.dumps({"text": "<p>Mein Verwaltungstext</p>"}),
        "status": Status.ENTWURF,
        "position": 10,
        "verlinkungen-TOTAL_FORMS": "0",
        "verlinkungen-INITIAL_FORMS": "0",
    }


def test_zwei_offene_formulare_ueberschreiben_sich_nicht(
    client, admin_nutzer, redaktion_nutzer, eintrag
):
    a = Client()
    a.force_login(redaktion_nutzer)
    client.force_login(admin_nutzer)
    alter_stand = stand(client, eintrag)
    anderer_stand = stand(a, eintrag)
    assert (
        a.post(url(eintrag), daten(anderer_stand, "Kollegin", "Erste Änderung")).status_code == 302
    )
    anzahl = eintrag.versionen.count()
    r = client.post(url(eintrag), daten(alter_stand))
    assert r.status_code == 409
    assert r.context["formular"]["titel"].value() == "Meine Eingabe"
    assert r.context["formular"]["f_text"].value() == "<p>Mein Text</p>"
    assert r.context["formular"].konfliktvergleich.alt.titel == "Kollegin"
    assert r.context["formular"].konfliktvergleich.neu.titel == "Meine Eingabe"
    eintrag.refresh_from_db()
    assert eintrag.titel == "Kollegin" and eintrag.versionen.count() == anzahl


def test_aufloesen_braucht_bestaetigung_und_den_geprueften_aktuellen_stand(
    client, admin_nutzer, eintrag
):
    client.force_login(admin_nutzer)
    token = stand(client, eintrag)
    schreiben(eintrag.dokument, "Kollegin")
    r = client.post(url(eintrag), daten(token))
    aktuell = r.context["formular"].konfliktstand
    post = {**daten(token), "aktion": "konflikt_loesen", "aktueller_stand": aktuell}
    assert client.post(url(eintrag), post).status_code == 409
    r = client.post(url(eintrag), {**post, "konflikt_geprueft": "on"})
    assert r.status_code == 302
    eintrag.refresh_from_db()
    assert eintrag.titel == "Meine Eingabe"
    assert eintrag.versionen.count() == 3


def test_dritte_aenderung_blockiert_auch_eine_bestaetigte_konfliktaufloesung(
    client, admin_nutzer, eintrag
):
    client.force_login(admin_nutzer)
    token = stand(client, eintrag)
    schreiben(eintrag.dokument, "Kollegin")
    r = client.post(url(eintrag), daten(token))
    aktuell = r.context["formular"].konfliktstand
    schreiben(eintrag.dokument, "Noch eine Änderung")
    r = client.post(
        url(eintrag),
        {
            **daten(token),
            "aktion": "konflikt_loesen",
            "aktueller_stand": aktuell,
            "konflikt_geprueft": "on",
        },
    )
    assert r.status_code == 409
    eintrag.refresh_from_db()
    assert eintrag.titel == "Noch eine Änderung" and eintrag.versionen.count() == 3


@pytest.mark.parametrize("art", ["fehlend", "kaputt", "fremder_nutzer", "fremder_eintrag"])
def test_signierter_stand_ist_verpflichtend_und_an_konto_und_eintrag_gebunden(
    client, admin_nutzer, redaktion_nutzer, eintrag, art
):
    client.force_login(admin_nutzer)
    tokens = {
        "fehlend": "",
        "kaputt": "kaputt",
        "fremder_nutzer": token_fuer_eintrag(redaktion_nutzer, eintrag),
        "fremder_eintrag": token_fuer_eintrag(
            admin_nutzer, schreiben(eintrag.dokument, kennung="K-91")
        ),
    }
    assert client.post(url(eintrag), daten(tokens[art])).status_code == 409
    eintrag.refresh_from_db()
    assert eintrag.titel == "Basis" and eintrag.versionen.count() == 1


def test_metadaten_aenderung_ohne_neue_fassung_wird_erkannt(client, admin_nutzer, eintrag):
    client.force_login(admin_nutzer)
    token = stand(client, eintrag)
    Eintrag.objects.filter(pk=eintrag.pk).update(position=999)
    assert client.post(url(eintrag), daten(token)).status_code == 409
    eintrag.refresh_from_db()
    assert eintrag.position == 999 and eintrag.titel == "Basis"


def test_freigabe_waehrend_der_bearbeitung_bleibt_unveraendert(client, admin_nutzer, eintrag):
    client.force_login(admin_nutzer)
    token = stand(client, eintrag)
    b = Beschluss.objects.create(
        datum=date(2026, 10, 31), gremium=Gremium.objects.create(name="Konferenz"), titel="Freigabe"
    )
    beschluesse.beschluss_fassen(b, [eintrag], nutzer=admin_nutzer)
    assert client.post(url(eintrag), daten(token)).status_code == 409
    v = eintrag.beschlossene_version()
    assert v.titel == "Basis" and v.status == Status.BESCHLOSSEN
    assert eintrag.versionen.count() == 1


def test_neuanlage_darf_nie_einen_vorhandenen_eintrag_uebernehmen(eintrag):
    with pytest.raises(Schreibkonflikt):
        schreiben(eintrag.dokument, erwarteter_stand=None)
    assert eintrag.versionen.count() == 1


def test_entfernter_eintrag_wird_vom_schreibdienst_nicht_wiederhergestellt(eintrag):
    erwartet = schreibstand(eintrag)
    d = eintrag.dokument
    eintrag.delete()
    with pytest.raises(Schreibkonflikt):
        schreiben(d, erwarteter_stand=erwartet)
    assert not d.eintraege.filter(kennung="K-90").exists()


def test_verwaltung_behaelt_eingabe_bei_konflikt(client, admin_nutzer, eintrag):
    client.force_login(admin_nutzer)
    token = stand(client, eintrag, True)
    schreiben(eintrag.dokument, "Neue Fassung")
    r = client.post(url(eintrag, True), admindaten(token))
    assert r.status_code == 200
    f = r.context["adminform"].form
    assert f.errors and f["titel"].value() == "Meine Verwaltungsänderung"
    assert f["aktueller_stand"].value()
    assert "Neue Fassung" in r.content.decode()
    assert eintrag.versionen.count() == 2
    post = {
        **admindaten(token),
        "konflikt_geprueft": "on",
        "aktueller_stand": f["aktueller_stand"].value(),
    }
    assert client.post(url(eintrag, True), post).status_code == 302
    eintrag.refresh_from_db()
    assert eintrag.titel == "Meine Verwaltungsänderung"


def test_verwaltung_kann_neue_aenderung_nicht_mit_alter_bestaetigung_ueberschreiben(
    client, admin_nutzer, eintrag
):
    client.force_login(admin_nutzer)
    token = stand(client, eintrag, True)
    schreiben(eintrag.dokument, "Erste Änderung")
    f = client.post(url(eintrag, True), admindaten(token)).context["adminform"].form
    schreiben(eintrag.dokument, "Zweite Änderung")
    r = client.post(
        url(eintrag, True),
        {
            **admindaten(token),
            "konflikt_geprueft": "on",
            "aktueller_stand": f["aktueller_stand"].value(),
        },
    )
    assert r.status_code == 200 and r.context["adminform"].form.errors
    eintrag.refresh_from_db()
    assert eintrag.titel == "Zweite Änderung"


def importinhalt(e):
    return {
        "dokument": e.dokument.schluessel,
        "eintraege": [
            {
                "kennung": e.kennung,
                "eintragstyp": "grundlagenkapitel",
                "titel": "Importtext",
                "daten": {"text": "<p>Import</p>"},
            }
        ],
    }


def test_importvorschau_erkennt_fremde_aenderungen_und_wird_erneuert(client, admin_nutzer, eintrag):
    client.force_login(admin_nutzer)
    adresse = reverse("kern:json_import", args=[eintrag.dokument.schluessel])
    inhalt = json.dumps(importinhalt(eintrag))
    r = client.post(adresse, {"inhalt": inhalt, "aktion": "vorschau"})
    token = r.context["formular"]["ausgangsstand"].value()
    schreiben(eintrag.dokument, "Zwischenzeitlich geschrieben")
    r = client.post(adresse, {"inhalt": inhalt, "aktion": "uebernehmen", "ausgangsstand": token})
    assert r.status_code == 409
    eintrag.refresh_from_db()
    assert eintrag.titel == "Zwischenzeitlich geschrieben"
    neu = r.context["formular"]["ausgangsstand"].value()
    assert neu != token
    assert (
        client.post(
            adresse, {"inhalt": inhalt, "aktion": "uebernehmen", "ausgangsstand": neu}
        ).status_code
        == 302
    )
    eintrag.refresh_from_db()
    assert eintrag.titel == "Importtext"


@pytest.mark.parametrize("manipuliert", [False, True])
def test_import_braucht_zum_inhalt_passende_vorschau(client, admin_nutzer, eintrag, manipuliert):
    client.force_login(admin_nutzer)
    adresse = reverse("kern:json_import", args=[eintrag.dokument.schluessel])
    inhalt = importinhalt(eintrag)
    r = client.post(adresse, {"inhalt": json.dumps(inhalt), "aktion": "vorschau"})
    token = r.context["formular"]["ausgangsstand"].value() if manipuliert else ""
    inhalt["eintraege"][0]["titel"] = "Anderer Inhalt"
    r = client.post(
        adresse, {"inhalt": json.dumps(inhalt), "aktion": "uebernehmen", "ausgangsstand": token}
    )
    assert r.status_code == 409
    eintrag.refresh_from_db()
    assert eintrag.titel == "Basis"


def test_json_import_verwirft_das_gesamte_paket_bei_standkonflikt(eintrag):
    erwartet = dokumentstand(eintrag.dokument)
    inhalt = importinhalt(eintrag)
    inhalt["eintraege"].append(
        {"kennung": "K-92", "eintragstyp": "grundlagenkapitel", "titel": "Neu", "daten": {}}
    )
    schreiben(eintrag.dokument, "Neuere Eingabe")
    with pytest.raises(Schreibkonflikt):
        uebernehmen_json(inhalt, eintrag.dokument, erwarteter_stand=erwartet)
    assert not eintrag.dokument.eintraege.filter(kennung="K-92").exists()


@pytest.mark.django_db(transaction=True)
def test_echte_konkurrierende_verbindungen_lassen_nur_eine_aenderung_zu(dokument, admin_nutzer):
    e = schreiben(dokument)
    erwartet = schreibstand(e)
    start = Barrier(2)

    def worker(titel):
        close_old_connections()
        try:
            d = Dokument.objects.get(pk=dokument.pk)
            u = Nutzer.objects.get(pk=admin_nutzer.pk)
            start.wait(timeout=10)
            try:
                schreiben(d, titel=titel, erwarteter_stand=erwartet, nutzer=u)
                return "gespeichert"
            except Schreibkonflikt:
                return "Konflikt"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(worker, "Eine Eingabe")
        b = pool.submit(worker, "Andere Eingabe")
        assert sorted([a.result(timeout=20), b.result(timeout=20)]) == ["Konflikt", "gespeichert"]
    assert e.versionen.count() == 2


def test_doppelte_uebermittlung_eines_bearbeitungsformulars_speichert_nur_einmal(
    client, admin_nutzer, eintrag
):
    client.force_login(admin_nutzer)
    token = stand(client, eintrag)
    assert client.post(url(eintrag), daten(token)).status_code == 302
    assert client.post(url(eintrag), daten(token)).status_code == 409
    assert eintrag.versionen.count() == 2


@pytest.mark.django_db(transaction=True)
def test_zwei_neuanlagen_erhalten_unterschiedliche_kennungen(dokument, admin_nutzer):
    start = Barrier(2)
    adresse = reverse("kern:eintrag_neu", args=[dokument.schluessel, "grundlagenkapitel"])

    def worker(titel):
        close_old_connections()
        try:
            u = Nutzer.objects.get(pk=admin_nutzer.pk)
            c = Client()
            c.force_login(u)
            start.wait(timeout=10)
            return c.post(
                adresse, {"titel": titel, "f_text": "<p>Neu</p>", "status": Status.ENTWURF}
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(worker, "Paralleler Eintrag A")
        b = pool.submit(worker, "Paralleler Eintrag B")
        assert [a.result(timeout=20), b.result(timeout=20)] == [302, 302]
    neu = list(dokument.eintraege.filter(titel__startswith="Paralleler Eintrag"))
    assert len(neu) == 2 and neu[0].kennung != neu[1].kennung
    assert all(e.versionen.count() == 1 for e in neu)


def test_entfernte_eintraege_behalten_die_eingabe_ohne_wiederherstellung(
    client, admin_nutzer, eintrag
):
    client.force_login(admin_nutzer)
    token = stand(client, eintrag)
    adresse = url(eintrag)
    pk = eintrag.pk
    eintrag.delete()
    r = client.post(adresse, daten(token))
    assert r.status_code == 409
    assert r.context["formular"]["titel"].value() == "Meine Eingabe"
    assert r.context["formular"].eintrag_entfernt
    assert "Eintrag wurde entfernt" in r.content.decode()
    assert "Geprüfte Eingabe speichern" not in r.content.decode()
    assert not Eintrag.objects.filter(pk=pk).exists()


def test_entfernter_eintrag_ist_ohne_gueltigen_kontogebundenen_nachweis_nicht_rekonstruierbar(
    client, admin_nutzer, redaktion_nutzer, eintrag
):
    token = token_fuer_eintrag(redaktion_nutzer, eintrag)
    adresse = url(eintrag)
    eintrag.delete()
    client.force_login(admin_nutzer)
    assert client.post(adresse, daten(token)).status_code == 404
