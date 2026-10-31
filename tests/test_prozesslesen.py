"""AP07: erlaubte Fassungen, heutige Kontakte, sichere Materialien und druckbarer Text."""

import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from eintragstypen import dienste
from kern import beschluesse, funktionen, prozesslesen
from kern.models import (
    Anhang,
    Besetzungsart,
    Besetzungsmodus,
    Dokument,
    Dokumenttyp,
    Eintrag,
    Funktionsbereich,
    Funktionsbesetzung,
    Schulfunktion,
)
from tests.test_prozessdaten import beispiel, beschluss, schreiben

pytestmark = pytest.mark.django_db


@pytest.fixture
def handbuch():
    typ, _ = Dokumenttyp.objects.get_or_create(
        schluessel="schulhandbuch",
        defaults={"name": "Schulhandbuch", "eintragstypen": ["grundlagenkapitel", "prozess"]},
    )
    return Dokument.objects.create(schluessel="lesetest", titel="Testhandbuch", dokumenttyp=typ)


@pytest.fixture
def funktion():
    return Schulfunktion.objects.create(name="Testberatung", schluessel="demo")


def url(e, name="eintrag", *args):
    return reverse("kern:" + name, args=[e.dokument.schluessel, e.kennung, *args])


def dto(client, e):
    r = client.get(url(e))
    assert r.status_code == 200
    return r.context["prozess"]


def textpdf(r):
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)


def test_lesende_erhalten_nur_freigegebenen_graph_auch_als_pdf(
    client, handbuch, funktion, lesend_nutzer
):
    graph = beispiel()
    graph["knoten"][1]["titel"] = "Gültige Beratungsfrage?"
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    graph["knoten"][1]["titel"] = "Vertrauliche neue Xylophonfrage?"
    e = schreiben(handbuch, graph)
    client.force_login(lesend_nutzer)
    r = client.get(url(e))
    assert r.status_code == 200
    assert "Gültige Beratungsfrage?" in r.content.decode()
    assert "Xylophonfrage" not in r.content.decode()
    daten = r.context["prozess"]["graph"]
    assert daten["knoten"][1]["titel"] == "Gültige Beratungsfrage?"
    pdf = textpdf(client.get(url(e, "prozess_pdf")))
    assert "Gültige Beratungsfrage?" in pdf
    assert "Xylophonfrage" not in pdf
    assert (
        client.get(
            url(e, "prozess_pdf"), {"fassung": e.letzte_version().versionsnummer}
        ).status_code
        == 404
    )


def test_arbeitsstand_und_historische_fassung_sind_getrennt(
    client, handbuch, funktion, admin_nutzer
):
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    alte = e.beschlossene_version().versionsnummer
    graph = beispiel()
    graph["knoten"][1]["titel"] = "Neue zulässige Frage?"
    e = schreiben(handbuch, graph)
    client.force_login(admin_nutzer)
    assert dto(client, e)["graph"]["knoten"][1]["titel"] == "Neue zulässige Frage?"
    alt = client.get(url(e, "version", alte))
    assert alt.context["prozess"]["graph"]["knoten"][1]["titel"] != "Neue zulässige Frage?"
    beschluesse.beschluss_fassen(beschluss(), [e])
    assert client.get(url(e, "version", alte)).context["prozess"]["historisch"]


def test_personalwechsel_aendert_kontakte_aller_fassungen_ohne_neue_version(
    client, handbuch, funktion, lehrkraft, andere_lehrkraft
):
    alt = Funktionsbesetzung.objects.create(funktion=funktion, person=lehrkraft)
    lehrkraft.anzeigename = "Bisheriger Kontakt"
    lehrkraft.save()
    andere_lehrkraft.anzeigename = "Heutiger Kontakt"
    andere_lehrkraft.save()
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    client.force_login(lehrkraft)
    assert dto(client, e)["graph"]["knoten"][2]["kontakt"]["personen"] == ["Bisheriger Kontakt"]
    funktionen.wechseln(alt, andere_lehrkraft, timezone.localdate())
    assert dto(client, e)["graph"]["knoten"][2]["kontakt"]["personen"] == ["Heutiger Kontakt"]
    r = client.get(url(e, "version", 1))
    assert r.context["prozess"]["knoten"][2]["kontakt"]["personen"] == ["Heutiger Kontakt"]
    assert e.versionen.count() == 1
    assert "Kontakte sind aktuell" in r.content.decode()


@pytest.mark.parametrize("fall", ["team", "vertretung", "inaktiv", "abgelaufen", "bereich"])
def test_zustaendigkeiten_werden_exakt_aufgeloest(
    client, handbuch, funktion, lehrkraft, andere_lehrkraft, fall
):
    graph = beispiel()
    if fall == "team":
        funktion.besetzungsmodus = Besetzungsmodus.TEAM
        funktion.save()
    b = Funktionsbesetzung.objects.create(funktion=funktion, person=lehrkraft)
    if fall == "team":
        Funktionsbesetzung.objects.create(funktion=funktion, person=andere_lehrkraft)
    elif fall == "vertretung":
        Funktionsbesetzung.objects.create(
            funktion=funktion,
            person=andere_lehrkraft,
            art=Besetzungsart.VERTRETUNG,
            vertretung_aktiv=True,
        )
    elif fall == "inaktiv":
        lehrkraft.is_active = False
        lehrkraft.save()
    elif fall == "abgelaufen":
        b.gueltig_ab = timezone.localdate() - timedelta(days=5)
        b.gueltig_bis = timezone.localdate() - timedelta(days=1)
        b.save()
    elif fall == "bereich":
        scope = Funktionsbereich.objects.create(
            name="Anderer Geltungsbereich", schluessel="anderer"
        )
        graph["knoten"][2]["bereich"] = scope.schluessel
    e = schreiben(handbuch, graph)
    client.force_login(andere_lehrkraft)
    k = dto(client, e)["knoten"][2]["kontakt"]
    if fall == "team":
        assert len(k["personen"]) == 2
    elif fall == "vertretung":
        assert k["personen"] == [andere_lehrkraft.anzeigename] and "Vertretung" in k["status"]
    else:
        assert not k["personen"]
    if fall == "bereich":
        assert k["bereich"] == "Anderer Geltungsbereich" and "nicht besetzt" in k["status"]


def wissen(d, kennung="K-01", titel="Freigegebenes Testwissen"):
    return dienste.speichern(
        d,
        dienste.pruefen(
            d,
            dienste.Rohsatz(
                kennung=kennung,
                eintragstyp="grundlagenkapitel",
                titel=titel,
                daten={"text": "Testwissen"},
            ),
        ),
    )


def test_gueltiger_prozess_verlinkt_gueltige_zielversion_statt_neuem_entwurf(
    client, handbuch, funktion, lehrkraft
):
    ziel = wissen(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [ziel])
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [
        {"typ": "eintrag", "dokument": handbuch.schluessel, "kennung": ziel.kennung}
    ]
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    wissen(handbuch, titel="Neuer Zielentwurf")
    client.force_login(lehrkraft)
    m = dto(client, e)["knoten"][2]["materialien"][0]
    assert m["label"] == "K-01 · Freigegebenes Testwissen"
    assert m["url"] == url(ziel, "version", 1)


def test_entzogener_zielzugang_verraet_keine_metadaten_oder_rohreferenzen(
    client, handbuch, funktion, lesend_nutzer
):
    d = Dokument.objects.create(
        schluessel="geheimer-ressourcenordner",
        titel="Geschützter Dokumenttitel",
        dokumenttyp=handbuch.dokumenttyp,
    )
    ziel = wissen(d, titel="Geschützter Xylophontitel")
    beschluesse.beschluss_fassen(beschluss(), [ziel])
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [
        {"typ": "eintrag", "dokument": d.schluessel, "kennung": ziel.kennung}
    ]
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    d.kollegiumsweit = False
    d.save()
    client.force_login(lesend_nutzer)
    r = client.get(url(e))
    assert r.context["prozess"]["knoten"][2]["materialien"][0]["url"] == ""
    for geheim in [
        "geheimer-ressourcenordner",
        "Geschützter Dokumenttitel",
        "Geschützter Xylophontitel",
    ]:
        assert geheim not in r.content.decode()
        assert geheim not in textpdf(client.get(url(e, "prozess_pdf")))


def test_nur_zugaengliche_unveraenderte_dateien_erscheinen(
    client, handbuch, funktion, lesend_nutzer, tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    a = Anhang.objects.create(
        dokument=handbuch,
        dateiname="Testformular.pdf",
        datei=SimpleUploadedFile("test.pdf", b"test"),
    )
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [{"typ": "anhang", "id": a.pk}]
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    client.force_login(lesend_nutzer)
    assert dto(client, e)["knoten"][2]["materialien"][0]["url"]
    a.dateiname = "Neuer geheimer Dateiname.pdf"
    a.save()
    r = client.get(url(e))
    assert "Neuer geheimer" not in r.content.decode()
    assert not r.context["prozess"]["knoten"][2]["materialien"][0]["url"]


@pytest.mark.parametrize(
    "urlwert",
    [
        "javascript:alert(1)",
        "data:text/html,test",
        "//example.org/test",
        "https://user:pass@example.org/test",
        "ftp://example.org/test",
    ],
)
def test_unsichere_dateilinks_werden_nicht_ausgegeben(handbuch, funktion, admin_nutzer, urlwert):
    a = Anhang.objects.create(dokument=handbuch, dateiname="Datei", nextcloud_link=urlwert)
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [{"typ": "anhang", "id": a.pk}]
    e = schreiben(handbuch, graph)
    assert not prozesslesen.aufbereiten(e, e.daten, admin_nutzer)["knoten"][2]["materialien"][0][
        "url"
    ]


def test_nextcloud_pfad_braucht_sichere_konfiguration(handbuch, funktion, admin_nutzer, settings):
    a = Anhang.objects.create(
        dokument=handbuch, dateiname="Formular.pdf", nextcloud_pfad="/Demo/Formular.pdf"
    )
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [{"typ": "anhang", "id": a.pk}]
    e = schreiben(handbuch, graph)
    settings.NEXTCLOUD_URL = ""
    assert not prozesslesen.aufbereiten(e, e.daten, admin_nutzer)["knoten"][2]["materialien"][0][
        "url"
    ]
    settings.NEXTCLOUD_URL = "https://cloud.example.org"
    assert prozesslesen.aufbereiten(e, e.daten, admin_nutzer)["knoten"][2]["materialien"][0][
        "url"
    ].startswith("https://cloud.example.org/")


def test_kreis_bleibt_endlich_und_wird_als_ruecksprung_ausgegeben(
    client, handbuch, funktion, lehrkraft
):
    graph = beispiel()
    graph["verbindungen"][3].update(nach="q", ruecksprung=True, beschriftung="Erneut prüfen")
    e = schreiben(handbuch, graph)
    client.force_login(lehrkraft)
    p = dto(client, e)
    assert len(p["knoten"]) == 5
    assert p["knoten"][2]["folgen"][0]["ruecksprung"]
    assert "Rücksprung" in textpdf(client.get(url(e, "prozess_pdf")))


def test_text_ist_ohne_javascript_vollstaendig(client, handbuch, funktion, lehrkraft):
    e = schreiben(handbuch)
    client.force_login(lehrkraft)
    r = client.get(url(e))
    for k in beispiel()["knoten"]:
        assert k["titel"] in r.content.decode()
    assert "data-lesetext" in r.content.decode()
    assert "<div data-lesetext><h3>Alle Schritte als Text</h3>" in r.content.decode()


def test_defekter_graph_zeigt_neutralen_hinweis(client, handbuch, lehrkraft):
    e = Eintrag.objects.create(
        dokument=handbuch,
        kennung="PR-01",
        titel="Defekt",
        eintragstyp="prozess",
        daten={"ablauf": {"schema_version": 99, "geheimes_feld": "Nicht ausgeben"}},
    )
    client.force_login(lehrkraft)
    r = client.get(url(e))
    assert r.status_code == 200
    assert "derzeit nicht lesbar" in r.content.decode()
    assert "Nicht ausgeben" not in r.content.decode()


def test_eingeschraenkter_prozess_sperrt_auch_pdf(client, handbuch, funktion, lesend_nutzer):
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    handbuch.kollegiumsweit = False
    handbuch.save()
    client.force_login(lesend_nutzer)
    assert client.get(url(e, "prozess_pdf")).status_code in (403, 404)


def test_lesen_und_drucken_erzeugen_keinen_verlauf(client, handbuch, funktion, lehrkraft):
    e = schreiben(handbuch)
    client.force_login(lehrkraft)
    vorher = e.versionen.count()
    r = client.get(url(e))
    textpdf(client.get(url(e, "prozess_pdf")))
    assert e.versionen.count() == vorher
    assert "no-store" in client.get(url(e, "prozess_pdf"))["Cache-Control"]
    assert r.context["prozess"]["knoten"][2]["kontakt"]["personen"] == []
