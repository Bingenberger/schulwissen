"""AP05: versionierte Graphen, atomare Freigaben und sichere Ressourcenbezüge."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections
from django.urls import reverse

from eintragstypen import dienste
from eintragstypen.formulare import EintragFormular
from eintragstypen.import_json import pruefen_json, uebernehmen_json
from eintragstypen.registry import Feldtyp, registry
from kern import beschluesse, exporte, prozessdaten, vergleich
from kern.models import (
    Anhang,
    Beschluss,
    Dokument,
    Dokumenttyp,
    Eintrag,
    Eintragsversion,
    Funktionsbereich,
    Gremium,
    Schulfunktion,
    Status,
    Zieltyp,
)
from kern.schreibschutz import Schreibkonflikt, schreibstand
from kern.staende import sichtbare_verweise
from suche import dienste as suche

pytestmark = pytest.mark.django_db


def beispiel():
    return {
        "schema_version": 1,
        "knoten": [
            {"id": "s", "art": "start", "titel": "Demoanlass"},
            {"id": "q", "art": "entscheidung", "titel": "Demo: Beratung gewünscht?"},
            {"id": "j", "art": "handlung", "titel": "Demokontakt aufnehmen", "funktion": "demo"},
            {"id": "n", "art": "handlung", "titel": "Demoanlaufstelle klären", "funktion": "demo"},
            {"id": "e", "art": "ende", "titel": "Demoziel erreicht"},
        ],
        "verbindungen": [
            {"id": "sq", "von": "s", "nach": "q"},
            {"id": "qj", "von": "q", "nach": "j", "beschriftung": "Ja"},
            {"id": "qn", "von": "q", "nach": "n", "beschriftung": "Nein"},
            {"id": "je", "von": "j", "nach": "e"},
            {"id": "ne", "von": "n", "nach": "e"},
        ],
    }


@pytest.fixture
def handbuch():
    typ, _ = Dokumenttyp.objects.get_or_create(
        schluessel="schulhandbuch",
        defaults={"name": "Schulhandbuch", "eintragstypen": ["grundlagenkapitel", "prozess"]},
    )
    return Dokument.objects.create(titel="Testhandbuch", schluessel="testhandbuch", dokumenttyp=typ)


@pytest.fixture
def funktion():
    return Schulfunktion.objects.create(name="Demofunktion", schluessel="demo")


def schreiben(handbuch, graph=None, nutzer=None, status=Status.ENTWURF, kennung="PR-01", **kwargs):
    roh = dienste.Rohsatz(
        kennung=kennung,
        eintragstyp="prozess",
        titel="Demoprozess",
        status=status,
        daten={"anlass": "Fiktiver Testablauf", "ablauf": beispiel() if graph is None else graph},
    )
    return dienste.speichern(
        handbuch, dienste.pruefen(handbuch, roh, nutzer=nutzer), nutzer=nutzer, **kwargs
    )


def beschluss():
    g, _ = Gremium.objects.get_or_create(name="Testgremium")
    return Beschluss.objects.create(datum=date(2026, 10, 31), gremium=g, titel="Testfreigabe")


def test_registry_und_migration_ergaenzen_nur_typ(handbuch):
    assert registry.holen("prozess").feld("ablauf").typ == Feldtyp.PROZESSGRAPH
    assert handbuch.dokumenttyp.eintragstypen == ["grundlagenkapitel", "prozess"]
    assert Schulfunktion.objects.count() == 0
    assert Eintrag.objects.count() == 0


def test_diamant_und_mehr_als_zwei_alternativen():
    graph = beispiel()
    graph["verbindungen"].append({"id": "qe", "von": "q", "nach": "e", "beschriftung": "Unklar"})
    assert prozessdaten.freigabehindernisse(prozessdaten.normalisieren(graph)) == []


@pytest.mark.parametrize(
    "fehler",
    [
        "version",
        "boolversion",
        "objekt",
        "knotenliste",
        "kante",
        "doppelt",
        "kantenid",
        "typ",
        "kennungslaenge",
        "zahltext",
        "feld",
        "ruecktyp",
        "url",
        "personen",
        "bereich",
        "menge",
        "groesse",
    ],
)
def test_unsichere_strukturen_werden_schon_im_entwurf_abgelehnt(fehler):
    graph = beispiel()
    if fehler == "version":
        graph["schema_version"] = 2
    elif fehler == "boolversion":
        graph["schema_version"] = True
    elif fehler == "objekt":
        graph = []
    elif fehler == "knotenliste":
        graph["knoten"] = {}
    elif fehler == "kante":
        graph["verbindungen"][0] = []
    elif fehler == "doppelt":
        graph["knoten"].append(copy.deepcopy(graph["knoten"][0]))
    elif fehler == "kantenid":
        graph["verbindungen"][1]["id"] = "sq"
    elif fehler == "typ":
        graph["knoten"][0]["art"] = "javascript"
    elif fehler == "kennungslaenge":
        graph["knoten"][0]["id"] = "a" * 65
    elif fehler == "zahltext":
        graph["knoten"][0]["titel"] = 17
    elif fehler == "feld":
        graph["knoten"][0]["code"] = "alert()"
    elif fehler == "ruecktyp":
        graph["verbindungen"][0]["ruecksprung"] = "ja"
    elif fehler == "url":
        graph["knoten"][0]["verweise"] = [{"typ": "url", "url": "javascript:alert()"}]
    elif fehler == "personen":
        graph["knoten"][0]["person"] = 1
    elif fehler == "bereich":
        graph["knoten"][0]["bereich"] = "jg1"
    elif fehler == "menge":
        graph["knoten"] *= 50
    elif fehler == "groesse":
        graph["knoten"][0]["text"] = "a" * 250001
    with pytest.raises(ValidationError):
        prozessdaten.normalisieren(graph)


@pytest.mark.parametrize(
    "fehler",
    [
        "start",
        "ende",
        "ziel",
        "unerreichbar",
        "titel",
        "funktion",
        "handlung",
        "zweige",
        "label",
        "endkante",
        "startkante",
    ],
)
def test_unvollstaendiger_graph_speichert_nur_als_entwurf(handbuch, funktion, fehler):
    graph = beispiel()
    if fehler == "start":
        graph["knoten"][0]["art"] = "ende"
    elif fehler == "ende":
        graph["knoten"].pop()
    elif fehler == "ziel":
        graph["verbindungen"][0]["nach"] = "fehlt"
    elif fehler == "unerreichbar":
        graph["knoten"].append({"id": "lose", "art": "ende", "titel": "Loser Schritt"})
    elif fehler == "titel":
        graph["knoten"][1]["titel"] = ""
    elif fehler == "funktion":
        graph["knoten"][2].pop("funktion")
    elif fehler == "handlung":
        graph["verbindungen"].pop()
    elif fehler == "zweige":
        graph["verbindungen"][1]["beschriftung"] = ""
    elif fehler == "label":
        graph["verbindungen"][2]["beschriftung"] = " ja "
    elif fehler == "endkante":
        graph["verbindungen"].append({"id": "eq", "von": "e", "nach": "q"})
    elif fehler == "startkante":
        graph["verbindungen"].append({"id": "es", "von": "e", "nach": "s"})
    e = schreiben(handbuch, graph)
    assert e.versionen.count() == 1
    with pytest.raises(ValidationError):
        beschluesse.beschluss_fassen(beschluss(), [e])
    with pytest.raises(ValueError):
        schreiben(handbuch, graph, status=Status.ABGESTIMMT)
    assert e.versionen.count() == 1


def test_ruecksprung_mit_ausgang_ist_gueltig_ohne_ausgang_nicht(handbuch, funktion):
    graph = beispiel()
    graph["verbindungen"][3].update(nach="q", ruecksprung=True, beschriftung="Erneut prüfen")
    assert not prozessdaten.freigabehindernisse(prozessdaten.normalisieren(graph))
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    graph["verbindungen"][3]["ruecksprung"] = False
    assert any(
        "nicht ausdrücklich" in f
        for f in prozessdaten.freigabehindernisse(prozessdaten.normalisieren(graph))
    )
    graph["verbindungen"][3]["ruecksprung"] = True
    graph["verbindungen"][4].update(nach="q", ruecksprung=True, beschriftung="Noch einmal")
    assert any(
        "Kein Ende" in f
        for f in prozessdaten.freigabehindernisse(prozessdaten.normalisieren(graph))
    )


def test_falscher_oder_unbeschrifteter_ruecksprung():
    graph = beispiel()
    graph["verbindungen"][0]["ruecksprung"] = True
    fehler = prozessdaten.freigabehindernisse(prozessdaten.normalisieren(graph))
    assert any("nicht zurück" in f for f in fehler)
    assert any("Beschrifte" in f for f in fehler)


def test_fassung_vergleich_freigabe_und_alter_stand(handbuch, funktion, admin_nutzer):
    e = schreiben(handbuch, nutzer=admin_nutzer)
    alt = e.letzte_version()
    beschluesse.beschluss_fassen(beschluss(), [e], nutzer=admin_nutzer)
    e.refresh_from_db()
    graph = beispiel()
    graph["knoten"][1]["titel"] = "Neue Demofrage?"
    e = schreiben(handbuch, graph, nutzer=admin_nutzer, erwarteter_stand=schreibstand(e))
    neu = e.letzte_version()
    assert e.status == Status.ENTWURF
    assert e.beschlossene_version().pk == alt.pk
    assert alt.daten["ablauf"]["knoten"][1]["titel"] != neu.daten["ablauf"]["knoten"][1]["titel"]
    assert vergleich.vergleichen(alt, neu, nutzer=admin_nutzer).hat_aenderungen
    alt.refresh_from_db()
    with pytest.raises(ValidationError):
        alt.save()
    assert (
        e.verlinkungen.filter(ziel_typ=Zieltyp.SCHULFUNKTION, ziel_id=str(funktion.pk)).count() == 1
    )
    assert all(v["beschriftung"] == "" for v in neu.verlinkungen)


def test_ressourcen_und_id_aenderungen_sind_im_vergleich_sichtbar(handbuch, funktion):
    e = schreiben(handbuch)
    alt = e.letzte_version()
    graph = beispiel()
    graph["verbindungen"][0]["id"] = "anderer-stabiler-schluessel"
    e = schreiben(handbuch, graph)
    d = vergleich.vergleichen(alt, e.letzte_version())
    assert d.hat_aenderungen
    assert "Schrittkennungen" in d.geaenderte_felder[0].nachher


def test_freigabe_mehrerer_eintraege_ist_atomar(handbuch, funktion):
    gut = schreiben(handbuch)
    schlecht = schreiben(
        handbuch, {"schema_version": 1, "knoten": [], "verbindungen": []}, kennung="PR-02"
    )
    b = beschluss()
    with pytest.raises(ValidationError):
        beschluesse.beschluss_fassen(b, [gut, schlecht])
    assert not b.dokumente.exists()
    assert not Eintragsversion.objects.filter(status=Status.BESCHLOSSEN).exists()
    version = schlecht.letzte_version()
    version.status = Status.BESCHLOSSEN
    version.beschluss = b
    with pytest.raises(ValidationError):
        version.save()


def test_fremde_verweise_verraten_keine_metadaten(handbuch, funktion, lehrkraft):
    ziel = Eintrag.objects.create(
        dokument=handbuch,
        kennung="GEHEIM",
        eintragstyp="grundlagenkapitel",
        titel="Vertraulicher Xylophontitel",
    )
    handbuch.kollegiumsweit = False
    handbuch.save()
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [
        {"typ": "eintrag", "dokument": handbuch.schluessel, "kennung": ziel.kennung}
    ]
    with pytest.raises(ValidationError) as vorhanden:
        prozessdaten.referenzen(prozessdaten.normalisieren(graph), nutzer=lehrkraft)
    graph["knoten"][2]["verweise"][0]["kennung"] = "NICHTVORHANDEN"
    with pytest.raises(ValidationError) as fehlt:
        prozessdaten.referenzen(prozessdaten.normalisieren(graph), nutzer=lehrkraft)
    assert vorhanden.value.messages == fehlt.value.messages
    assert "Xylophon" not in str(vorhanden.value)


def test_gueltiger_wissensverweis_und_loeschschutz(handbuch, funktion, admin_nutzer):
    ziel = dienste.speichern(
        handbuch,
        dienste.pruefen(
            handbuch,
            dienste.Rohsatz(
                kennung="K-01",
                eintragstyp="grundlagenkapitel",
                titel="Testwissen",
                daten={"text": "Testinhalt"},
            ),
        ),
    )
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [
        {"typ": "eintrag", "dokument": handbuch.schluessel, "kennung": ziel.kennung}
    ]
    e = schreiben(handbuch, graph)
    with pytest.raises(ValidationError):
        beschluesse.beschluss_fassen(beschluss(), [e])
    beschluesse.beschluss_fassen(beschluss(), [ziel])
    beschluesse.beschluss_fassen(beschluss(), [e], nutzer=admin_nutzer)
    from kern.arbeitsablauf import loeschhindernisse

    assert any("verweisen" in h for h in loeschhindernisse(ziel))
    assert e.letzte_version().verlinkungen[-1]["feld"] == prozessdaten.FELD


def test_dateireferenzen_pruefen_zugang_und_anhaenge(
    handbuch, funktion, admin_nutzer, lehrkraft, tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    a = Anhang.objects.create(
        dokument=handbuch,
        dateiname="Geheimer Dateiname.pdf",
        datei=SimpleUploadedFile("test.pdf", b"%PDF-1.4 test"),
    )
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [{"typ": "anhang", "id": a.pk}]
    e = schreiben(handbuch, graph, nutzer=admin_nutzer)
    assert e.verlinkungen.filter(ziel_typ=Zieltyp.ANHANG).exists()
    handbuch.kollegiumsweit = False
    handbuch.save()
    with pytest.raises(ValidationError, match="Dateiverweis nicht verfügbar"):
        prozessdaten.referenzen(prozessdaten.normalisieren(graph), nutzer=lehrkraft)
    assert sichtbare_verweise(lehrkraft, e.letzte_version().verlinkungen) == [
        v for v in e.letzte_version().verlinkungen if v["ziel_typ"] == Zieltyp.SCHULFUNKTION
    ]


def test_stabile_funktion_bereich_und_archivschutz(handbuch, funktion):
    bereich = Funktionsbereich.objects.create(name="Testbereich", schluessel="testbereich")
    graph = beispiel()
    graph["knoten"][2]["bereich"] = bereich.schluessel
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    funktion.archiviert = True
    with pytest.raises(ValidationError, match="gültigen Prozessfassungen"):
        funktion.save()
    bereich.name = "Andere Zuständigkeit"
    with pytest.raises(ValidationError):
        bereich.save()
    assert e.verlinkungen.filter(ziel_typ=Zieltyp.FUNKTIONSBEREICH).exists()


def test_referenzen_vor_schreiben_erneut_pruefen(handbuch, funktion, admin_nutzer):
    roh = dienste.Rohsatz(
        kennung="PR-01",
        eintragstyp="prozess",
        titel="Test",
        daten={"anlass": "Test", "ablauf": beispiel()},
    )
    vorher = dienste.pruefen(handbuch, roh, nutzer=admin_nutzer)
    funktion.archiviert = True
    funktion.save()
    with pytest.raises(ValidationError, match="Funktion nicht verfügbar"):
        dienste.speichern(handbuch, vorher, nutzer=admin_nutzer)
    assert not handbuch.eintraege.exists()


def test_json_roundtrip_und_ungueltige_importe_sind_schreibfrei(handbuch, funktion, admin_nutzer):
    e = schreiben(handbuch, nutzer=admin_nutzer)
    inhalt = json.loads(exporte.dokument_json(handbuch))
    assert inhalt["eintraege"][0]["daten"]["ablauf"] == e.daten["ablauf"]
    assert uebernehmen_json(inhalt, handbuch, nutzer=admin_nutzer).geschrieben == 1
    assert e.versionen.count() == 2
    inhalt["eintraege"][0]["daten"]["ablauf"]["knoten"].append({"id": "s", "art": "ende"})
    assert not pruefen_json(inhalt, handbuch, nutzer=admin_nutzer).ok
    assert not uebernehmen_json(inhalt, handbuch, nutzer=admin_nutzer).ok
    assert e.versionen.count() == 2


def test_suche_und_lesestand_zeigen_nur_erlaubte_fassung(
    handbuch, funktion, lesend_nutzer, admin_nutzer, client
):
    graph = beispiel()
    graph["knoten"][2]["titel"] = "Silbenbogenfreigabe"
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    graph["knoten"][2]["titel"] = "Xylophongeheimnis"
    e = schreiben(handbuch, graph)
    assert suche.suchen(lesend_nutzer, "Silbenbogenfreigabe", gruppe="eintraege").gesamt == 1
    assert suche.suchen(lesend_nutzer, "Xylophongeheimnis", gruppe="eintraege").gesamt == 0
    client.force_login(lesend_nutzer)
    antwort = client.get(reverse("kern:eintrag", args=[handbuch.schluessel, e.kennung]))
    assert "Silbenbogenfreigabe" in antwort.content.decode()
    assert "Xylophongeheimnis" not in antwort.content.decode()
    assert 'id="prozess-lesedaten"' in antwort.content.decode()
    assert "data-prozess-leser" in antwort.content.decode()
    assert suche.suchen(admin_nutzer, "Xylophongeheimnis", gruppe="eintraege").gesamt == 1


def test_frontend_bearbeitung_bewahrt_graph_ohne_jsonpflicht(handbuch, funktion):
    e = schreiben(handbuch)
    f = EintragFormular(
        {
            "titel": "Neuer Titel",
            "status": "entwurf",
            "f_anlass": "Neuer Anlass",
            "f_ablauf": json.dumps(e.daten["ablauf"]),
        },
        eintragstyp="prozess",
        eintrag=e,
    )
    assert f.is_valid()
    assert not f.fields["f_ablauf"].disabled
    assert f.als_rohsatz(e.kennung).daten["ablauf"] == e.daten["ablauf"]


def test_schreibkonflikt_und_lesender_schreibschutz(
    handbuch, funktion, admin_nutzer, lesend_nutzer
):
    e = schreiben(handbuch)
    stand = schreibstand(e)
    schreiben(handbuch, nutzer=admin_nutzer, erwarteter_stand=stand)
    with pytest.raises(Schreibkonflikt):
        schreiben(handbuch, nutzer=admin_nutzer, erwarteter_stand=stand)
    with pytest.raises(PermissionDenied):
        schreiben(handbuch, nutzer=lesend_nutzer)


def test_graphlabels_sind_text_und_kein_ausfuehrbares_html(
    handbuch, funktion, client, admin_nutzer
):
    graph = beispiel()
    graph["knoten"][1]["titel"] = '<script>alert("Test")</script>'
    e = schreiben(handbuch, graph)
    client.force_login(admin_nutzer)
    antwort = client.get(reverse("kern:eintrag", args=[handbuch.schluessel, e.kennung]))
    assert '<script>alert("Test")</script>' not in antwort.content.decode()
    assert "&lt;script&gt;" in antwort.content.decode()


@pytest.mark.django_db(transaction=True)
def test_freigabe_und_archivierung_der_funktion_konkurrieren_sicher():
    typ, _ = Dokumenttyp.objects.get_or_create(
        schluessel="schulhandbuch",
        defaults={"name": "Schulhandbuch", "eintragstypen": ["grundlagenkapitel", "prozess"]},
    )
    d = Dokument.objects.create(titel="Paralleltest", schluessel="parallel", dokumenttyp=typ)
    f = Schulfunktion.objects.create(name="Demo", schluessel="demo")
    e = schreiben(d)
    b = beschluss()
    start = Barrier(2)

    def ausfuehren(aktion):
        close_old_connections()
        try:
            start.wait(timeout=10)
            try:
                if aktion == "freigabe":
                    beschluesse.beschluss_fassen(
                        Beschluss.objects.get(pk=b.pk), [Eintrag.objects.get(pk=e.pk)]
                    )
                else:
                    obj = Schulfunktion.objects.get(pk=f.pk)
                    obj.archiviert = True
                    obj.save()
                return "gespeichert"
            except ValidationError:
                return "konflikt"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ergebnisse = list(pool.map(ausfuehren, ["freigabe", "archivieren"]))
    assert sorted(ergebnisse) == ["gespeichert", "konflikt"]
    f.refresh_from_db()
    assert f.archiviert != bool(e.beschlossene_version())


def test_personalwechsel_aendert_keine_prozessfassung(
    handbuch, funktion, lehrkraft, andere_lehrkraft
):
    from django.utils import timezone

    from kern import funktionen
    from kern.models import Funktionsbesetzung

    alt = Funktionsbesetzung.objects.create(funktion=funktion, person=lehrkraft)
    e = schreiben(handbuch)
    beschluesse.beschluss_fassen(beschluss(), [e])
    vorher = copy.deepcopy(e.beschlossene_version().daten)
    funktionen.wechseln(alt, andere_lehrkraft, timezone.localdate())
    assert e.versionen.count() == 1
    assert e.beschlossene_version().daten == vorher
    referenz = e.daten["ablauf"]["knoten"][2]["funktion"]
    f = Schulfunktion.objects.get(schluessel=referenz)
    assert funktionen.aufloesen(f.pk).zustaendige[0].person_id == andere_lehrkraft.pk


def test_prozesssuche_indexiert_keine_ressourcenkennungen(
    handbuch, funktion, lesend_nutzer, client
):
    d = Dokument.objects.create(
        titel="Geheimer Ressourcentitel",
        schluessel="ressourcenxylophon",
        dokumenttyp=handbuch.dokumenttyp,
    )
    ziel = dienste.speichern(
        d,
        dienste.pruefen(
            d,
            dienste.Rohsatz(
                kennung="K-01",
                eintragstyp="grundlagenkapitel",
                titel="Vertrauliches Ziel",
                daten={"text": "Testwissen"},
            ),
        ),
    )
    beschluesse.beschluss_fassen(beschluss(), [ziel])
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [
        {"typ": "eintrag", "dokument": d.schluessel, "kennung": ziel.kennung}
    ]
    e = schreiben(handbuch, graph)
    beschluesse.beschluss_fassen(beschluss(), [e])
    d.kollegiumsweit = False
    d.save()
    assert "ressourcenxylophon" not in e.letzte_version().suchtext
    assert suche.suchen(lesend_nutzer, "ressourcenxylophon", gruppe="eintraege").gesamt == 0
    client.force_login(lesend_nutzer)
    html = client.get(
        reverse("kern:eintrag", args=[handbuch.schluessel, e.kennung])
    ).content.decode()
    assert "Geheimer Ressourcentitel" not in html
    assert "Vertrauliches Ziel" not in html
    assert "ressourcenxylophon" not in html


def test_ungueltiger_prozessbeschluss_bleibt_im_formular(handbuch, funktion, admin_nutzer, client):
    e = schreiben(handbuch, {"schema_version": 1, "knoten": [], "verbindungen": []})
    client.force_login(admin_nutzer)
    g, _ = Gremium.objects.get_or_create(name="Testgremium")
    vorher = Beschluss.objects.count()
    antwort = client.post(
        reverse("kern:beschluss_anlegen"),
        {
            "eintrag": [str(e.pk)],
            "speichern": "1",
            "datum": "2026-10-31",
            "gremium": g.pk,
            "titel": "Meine erhaltene Eingabe",
            "text": "Fachliche Prüfung erforderlich",
        },
    )
    assert antwort.status_code == 200
    assert "genau einen Start" in antwort.content.decode()
    assert "Meine erhaltene Eingabe" in antwort.content.decode()
    assert Beschluss.objects.count() == vorher
    assert e.beschlossene_version() is None


def test_referenzauflosung_buendelt_ziele(
    handbuch, funktion, admin_nutzer, django_assert_max_num_queries
):
    graph = beispiel()
    for nummer in range(20):
        ziel = dienste.speichern(
            handbuch,
            dienste.pruefen(
                handbuch,
                dienste.Rohsatz(
                    kennung=f"K-{nummer:02}",
                    eintragstyp="grundlagenkapitel",
                    titel="Testwissen",
                    daten={"text": "Test"},
                ),
            ),
        )
        graph["knoten"][2].setdefault("verweise", []).append(
            {
                "typ": "eintrag",
                "dokument": handbuch.schluessel,
                "kennung": ziel.kennung,
            }
        )
    graph = prozessdaten.normalisieren(graph)
    with django_assert_max_num_queries(10):
        assert len(prozessdaten.referenzen(graph, nutzer=admin_nutzer)) == 21


def test_direkte_versionsanlage_bewahrt_kanonische_referenzhistorie(handbuch, funktion):
    e = Eintrag.objects.create(
        dokument=handbuch,
        kennung="PR-01",
        eintragstyp="prozess",
        titel="Demoprozess",
        daten={"anlass": "Test", "ablauf": beispiel()},
    )
    v = e.version_anlegen()
    assert any(
        r["ziel_typ"] == Zieltyp.SCHULFUNKTION and r["ziel_id"] == str(funktion.pk)
        for r in v.verlinkungen
    )
    beschluesse.beschluss_fassen(beschluss(), [e])
    funktion.archiviert = True
    with pytest.raises(ValidationError):
        funktion.save()


def test_registrierte_nextcloud_datei_ist_als_ressource_referenzierbar(handbuch, funktion):
    a = Anhang.objects.create(
        dokument=handbuch,
        dateiname="Demoformular.pdf",
        nextcloud_pfad="/Demonstration/Demoformular.pdf",
    )
    graph = beispiel()
    graph["knoten"][2]["verweise"] = [{"typ": "anhang", "id": a.pk}]
    e = schreiben(handbuch, graph)
    assert e.verlinkungen.filter(ziel_typ=Zieltyp.ANHANG, ziel_id=str(a.pk)).exists()


def test_anlass_ist_auch_bei_direkter_freigabe_erforderlich(handbuch, funktion):
    roh = dienste.Rohsatz(
        kennung="PR-01", eintragstyp="prozess", titel="Demo", daten={"ablauf": beispiel()}
    )
    e = dienste.speichern(handbuch, dienste.pruefen(handbuch, roh))
    with pytest.raises(ValidationError, match="Anlass und Ziel"):
        beschluesse.beschluss_fassen(beschluss(), [e])
    roh.status = Status.ABGESTIMMT
    assert not dienste.pruefen(handbuch, roh).ok


@pytest.mark.django_db(transaction=True)
def test_parallele_sammelfreigaben_sperren_funktionen_in_gleicher_reihenfolge():
    typ, _ = Dokumenttyp.objects.get_or_create(
        schluessel="schulhandbuch",
        defaults={"name": "Schulhandbuch", "eintragstypen": ["grundlagenkapitel", "prozess"]},
    )
    for name in ["demo", "zweite"]:
        Schulfunktion.objects.create(name=name, schluessel=name)
    auswahl = []
    for nr, namen in enumerate([("demo", "zweite"), ("zweite", "demo")]):
        d = Dokument.objects.create(titel="Test", schluessel=f"parallel-{nr}", dokumenttyp=typ)
        eintraege = []
        for i, name in enumerate(namen):
            graph = beispiel()
            for k in graph["knoten"]:
                if k["art"] == "handlung":
                    k["funktion"] = name
            eintraege.append(schreiben(d, graph, kennung=f"PR-{i:02}").pk)
        auswahl.append((beschluss().pk, eintraege))
    start = Barrier(2)

    def freigeben(daten):
        close_old_connections()
        try:
            b, pks = daten
            start.wait(timeout=10)
            return beschluesse.beschluss_fassen(
                Beschluss.objects.get(pk=b), list(Eintrag.objects.filter(pk__in=pks))
            ).beschlossen
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(freigeben, auswahl)) == [2, 2]
    assert Eintragsversion.objects.filter(status=Status.BESCHLOSSEN).count() == 4
