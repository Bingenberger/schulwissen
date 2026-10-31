"""AP06: echtes Schreiben, rechtegebundene Auswahl, schreibfreie Prüfung und Konflikte."""

import copy
import json

import pytest
from django.urls import reverse

from eintragstypen.formulare import EintragFormular
from kern import prozessdaten, prozesseditor
from kern.models import (
    Anhang,
    Dokument,
    Dokumenttyp,
    Eintrag,
    Funktionsbesetzung,
    Schulfunktion,
    Status,
    Wissensbereich,
    Zugangsregel,
)
from kern.schreibschutz import token_fuer_eintrag
from tests.test_prozessdaten import beispiel, schreiben

pytestmark = pytest.mark.django_db


@pytest.fixture
def handbuch():
    typ, _ = Dokumenttyp.objects.get_or_create(
        schluessel="schulhandbuch",
        defaults={"name": "Schulhandbuch", "eintragstypen": ["grundlagenkapitel", "prozess"]},
    )
    return Dokument.objects.create(schluessel="editor-test", titel="Testhandbuch", dokumenttyp=typ)


@pytest.fixture
def funktion():
    return Schulfunktion.objects.create(schluessel="demo", name="Testfunktion")


def eingabe(graph, token="", **kwargs):
    return {
        "titel": "Testprozess",
        "f_anlass": "Fiktiver Testanlass",
        "status": "entwurf",
        "f_ablauf": json.dumps(graph),
        "ausgangsstand": token,
        **kwargs,
    }


def test_formular_bindet_bearbeitbaren_graph_statt_text(handbuch, funktion):
    graph = beispiel()
    f = EintragFormular(eingabe(graph), eintragstyp="prozess", dokument=handbuch)
    assert f.is_valid()
    assert not f.fields["f_ablauf"].disabled
    assert f.als_rohsatz("PR-01").daten["ablauf"] == prozessdaten.normalisieren(graph)
    html = str(f["f_ablauf"])
    assert "data-prozess-editor" in html
    assert 'type="hidden"' in html
    assert "<textarea" not in html  # Keine technische JSON-Eingabe.


@pytest.mark.parametrize(
    "wert", [None, "", "kein JSON", '{"schema_version":true}', '{"schema_version":2}']
)
def test_fehlender_oder_defekter_graph_wird_nicht_still_ersetzt(handbuch, funktion, wert):
    e = schreiben(handbuch)
    daten = eingabe(beispiel())
    if wert is None:
        daten.pop("f_ablauf")
    else:
        daten["f_ablauf"] = wert
    f = EintragFormular(daten, eintragstyp="prozess", eintrag=e)
    assert not f.is_valid()
    assert "f_ablauf" in f.errors
    e.refresh_from_db()
    assert len(e.daten["ablauf"]["knoten"]) == 5


def test_neuer_prozess_wird_vom_echten_formular_gespeichert(
    client, handbuch, funktion, admin_nutzer
):
    client.force_login(admin_nutzer)
    url = reverse("kern:eintrag_neu", args=[handbuch.schluessel, "prozess"])
    r = client.get(url)
    assert r.status_code == 200
    assert "data-prozess-editor" in r.content.decode()
    assert "prozesseditor.js" in r.content.decode()
    graph = beispiel()
    assert client.post(url, eingabe(graph)).status_code == 302
    e = handbuch.eintraege.get(eintragstyp="prozess")
    assert e.daten["ablauf"] == prozessdaten.normalisieren(graph)
    assert e.versionen.count() == 1
    r = client.get(reverse("kern:eintrag_bearbeiten", args=[handbuch.schluessel, e.kennung]))
    f = r.context["formular"]
    assert json.loads(f["f_ablauf"].value()) == e.daten["ablauf"]


def test_schritt_und_zweige_bleiben_nach_neuladen_erhalten(
    client, handbuch, funktion, admin_nutzer
):
    e = schreiben(handbuch)
    client.force_login(admin_nutzer)
    url = reverse("kern:eintrag_bearbeiten", args=[handbuch.schluessel, e.kennung])
    graph = copy.deepcopy(e.daten["ablauf"])
    graph["knoten"][1]["titel"] = "Andere Testfrage?"
    graph["verbindungen"].append(
        {"id": "dritter-zweig", "von": "q", "nach": "e", "beschriftung": "Unklar"}
    )
    token = client.get(url).context["formular"]["ausgangsstand"].value()
    assert client.post(url, eingabe(graph, token)).status_code == 302
    e.refresh_from_db()
    assert e.daten["ablauf"]["knoten"][1]["id"] == "q"
    assert e.daten["ablauf"]["knoten"][1]["titel"] == "Andere Testfrage?"
    assert e.daten["ablauf"]["verbindungen"][-1]["id"] == "dritter-zweig"
    assert e.versionen.count() == 2


def test_unvollstaendiger_entwurf_und_sprungziele(client, handbuch, funktion, admin_nutzer):
    client.force_login(admin_nutzer)
    graph = beispiel()
    graph["verbindungen"][1]["nach"] = ""
    pruefurl = reverse("kern:prozess_pruefen", args=[handbuch.schluessel])
    antwort = client.post(pruefurl, eingabe(graph))
    assert antwort.status_code == 200 and not antwort.json()["ok"]
    assert any(m["schritt"] == "q" for m in antwort.json()["meldungen"])
    assert any("bei Schritt 2" in m["text"] for m in antwort.json()["meldungen"])
    assert not handbuch.eintraege.exists()
    url = reverse("kern:eintrag_neu", args=[handbuch.schluessel, "prozess"])
    assert client.post(url, eingabe(graph)).status_code == 302
    e = handbuch.eintraege.get()
    assert e.status == Status.ENTWURF
    assert e.daten["ablauf"]["verbindungen"][1]["nach"] == ""


def test_pruefung_ist_schreibfrei_und_veraendert_keinen_status(
    client, handbuch, funktion, admin_nutzer
):
    e = schreiben(handbuch)
    client.force_login(admin_nutzer)
    token = token_fuer_eintrag(admin_nutzer, e)
    r = client.post(
        reverse("kern:prozess_pruefen", args=[handbuch.schluessel]),
        eingabe(
            beispiel(),
            token,
            kennung=e.kennung,
            status="beschlossen",
        ),
    )
    assert r.status_code == 200 and r.json()["ok"]
    e.refresh_from_db()
    assert e.status == Status.ENTWURF
    assert e.versionen.count() == 1


def test_fehler_beim_abstimmen_erhalten_eingabe_und_sprungziele(
    client, handbuch, funktion, admin_nutzer
):
    client.force_login(admin_nutzer)
    graph = beispiel()
    graph["knoten"][2].pop("funktion")
    r = client.post(
        reverse("kern:eintrag_neu", args=[handbuch.schluessel, "prozess"]),
        eingabe(graph, status="abgestimmt"),
    )
    assert r.status_code == 200
    assert not handbuch.eintraege.exists()
    assert json.loads(r.context["formular"]["f_ablauf"].value())["knoten"][2]["id"] == "j"
    assert any(
        m["schritt"] == "j" for m in r.context["formular"].fields["f_ablauf"].widget.meldungen
    )


def test_zwei_autoren_behalten_ihre_graphen_bei_konflikt(client, handbuch, funktion, admin_nutzer):
    e = schreiben(handbuch)
    client.force_login(admin_nutzer)
    url = reverse("kern:eintrag_bearbeiten", args=[handbuch.schluessel, e.kennung])
    token = client.get(url).context["formular"]["ausgangsstand"].value()
    erster = beispiel()
    erster["knoten"][1]["titel"] = "Erste Frage?"
    eigener = beispiel()
    eigener["knoten"][1]["titel"] = "Meine erhaltene Frage?"
    assert client.post(url, eingabe(erster, token)).status_code == 302
    r = client.post(url, eingabe(eigener, token))
    assert r.status_code == 409
    assert (
        json.loads(r.context["formular"]["f_ablauf"].value())["knoten"][1]["titel"]
        == "Meine erhaltene Frage?"
    )
    e.refresh_from_db()
    assert e.daten["ablauf"]["knoten"][1]["titel"] == "Erste Frage?"
    assert e.versionen.count() == 2
    neuer_token = r.context["formular"].konfliktstand
    r = client.post(
        url,
        eingabe(
            eigener,
            token,
            aktion="konflikt_loesen",
            konflikt_geprueft="on",
            aktueller_stand=neuer_token,
        ),
    )
    assert r.status_code == 302
    e.refresh_from_db()
    assert e.daten["ablauf"]["knoten"][1]["titel"] == "Meine erhaltene Frage?"


@pytest.mark.parametrize("endpoint", ["prozess_pruefen", "prozess_ziele"])
def test_lesende_haben_keine_editor_api(client, handbuch, lesend_nutzer, endpoint):
    client.force_login(lesend_nutzer)
    url = reverse(f"kern:{endpoint}", args=[handbuch.schluessel])
    r = (
        client.post(url, eingabe(beispiel()))
        if endpoint == "prozess_pruefen"
        else client.get(url, {"q": "Test"})
    )
    assert r.status_code == 403


def test_fremder_bereich_sperrt_editor_und_pruefung(client, handbuch, lehrkraft):
    b = Wissensbereich.objects.create(
        name="Geschützter Bereich", schluessel="geschuetzt", kollegiumsweit=False
    )
    handbuch.bereich = b
    handbuch.save()
    client.force_login(lehrkraft)
    for name in ["prozess_pruefen", "prozess_ziele"]:
        url = reverse(f"kern:{name}", args=[handbuch.schluessel])
        r = (
            client.post(url, eingabe(beispiel()))
            if name == "prozess_pruefen"
            else client.get(url, {"q": "Test"})
        )
        assert r.status_code == 404


def test_materialsuche_zeigt_keine_fremden_metadaten(
    client, handbuch, funktion, admin_nutzer, lehrkraft
):
    erlaubtes = Eintrag.objects.create(
        dokument=handbuch,
        kennung="K-01",
        eintragstyp="grundlagenkapitel",
        titel="Testmaterial erlaubt",
    )
    geheim = Dokument.objects.create(
        schluessel="geheim",
        titel="Vertraulicher Dokumenttitel",
        dokumenttyp=handbuch.dokumenttyp,
        kollegiumsweit=False,
    )
    Eintrag.objects.create(
        dokument=geheim,
        kennung="X-01",
        eintragstyp="grundlagenkapitel",
        titel="Testmaterial geheim",
    )
    Anhang.objects.create(
        dokument=geheim, dateiname="Testmaterial geheim.pdf", nextcloud_pfad="/Test/geheim.pdf"
    )
    # Bestehender, der Lehrkraft ausdrücklich zum Bearbeiten zugewiesener Prozess.
    e = schreiben(handbuch)
    Zugangsregel.objects.create(dokument=handbuch, nutzer=lehrkraft, bearbeiten=True)
    client.force_login(lehrkraft)
    r = client.get(
        reverse("kern:prozess_ziele", args=[handbuch.schluessel]),
        {"q": "Testmaterial", "kennung": e.kennung},
    )
    assert r.status_code == 200
    assert [x["wert"]["kennung"] for x in r.json()["treffer"]] == [erlaubtes.kennung]
    assert "geheim" not in r.content.decode()


def test_kontaktvorschau_vergibt_keine_rechte_oder_kontoemails(funktion, lehrkraft):
    lehrkraft.anzeigename = "Testkontakt"
    lehrkraft.save()
    Funktionsbesetzung.objects.create(funktion=funktion, person=lehrkraft)
    vorher = set(lehrkraft.groups.values_list("pk", flat=True))
    opts = prozesseditor.optionen()
    assert "Testkontakt" in json.dumps(opts)
    assert lehrkraft.email not in json.dumps(opts)
    assert set(lehrkraft.groups.values_list("pk", flat=True)) == vorher


def test_widget_serialisiert_labels_sicher(handbuch, funktion, admin_nutzer):
    funktion.name = '</script><script>alert("Test")</script>'
    funktion.save()
    f = EintragFormular(eintragstyp="prozess", dokument=handbuch, nutzer=admin_nutzer)
    html = str(f["f_ablauf"])
    assert '</script><script>alert("Test")</script>' not in html
    assert "\\u003C/script\\u003E" in html


def test_kreispruefung_hat_ein_bearbeitbares_sprungziel():
    graph = beispiel()
    graph["verbindungen"][3]["nach"] = "q"
    graph = prozessdaten.normalisieren(graph)
    texte = prozessdaten.freigabehindernisse(graph)
    ausgabe = prozesseditor.meldungen(texte, graph)
    assert any(m["schritt"] == "j" and "nicht ausdrücklich" in m["text"] for m in ausgabe)


def test_vorhandene_materialien_sind_nicht_auf_eine_suchseite_begrenzt(handbuch, lehrkraft):
    Eintrag.objects.bulk_create(
        [
            Eintrag(
                dokument=handbuch,
                kennung=f"K-{i:02}",
                eintragstyp="grundlagenkapitel",
                titel=f"Material {i:02}",
            )
            for i in range(25)
        ]
    )
    graph = beispiel()
    refs = [
        {"typ": "eintrag", "dokument": handbuch.schluessel, "kennung": f"K-{i:02}"}
        for i in range(25)
    ]
    graph["knoten"][2]["verweise"] = refs[:20]
    graph["knoten"][3]["verweise"] = refs[20:]
    assert len(prozesseditor.referenztexte(lehrkraft, graph)) == 25


def test_verbindung_ohne_quellschritt_hat_korrigierbares_ziel(
    client, handbuch, funktion, admin_nutzer
):
    graph = beispiel()
    graph["verbindungen"][0]["von"] = "nicht-mehr-vorhanden"
    client.force_login(admin_nutzer)
    r = client.post(reverse("kern:prozess_pruefen", args=[handbuch.schluessel]), eingabe(graph))
    assert any(
        m["verbindung"] == "sq" and "Verbindung 1:" in m["text"] for m in r.json()["meldungen"]
    )
    assert not handbuch.eintraege.exists()
