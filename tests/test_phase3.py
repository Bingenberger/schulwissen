"""Abnahme von Planung, neuen Dokumenttypen und Datenrundläufen."""

import io
import json
from datetime import date

import pytest
from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from openpyxl import load_workbook
from pypdf import PdfReader

from deutsch.import_xlsx import uebernehmen
from eintragstypen.dienste import Rohsatz, pruefen, speichern
from eintragstypen.import_json import pruefen_json, uebernehmen_json
from kern import beschluesse, exporte
from kern.models import (
    Beschluss,
    Dokument,
    Dokumenttyp,
    Eintrag,
    Gremium,
    PersoenlicherFortschritt,
    Status,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def inhalt(dokument):
    return {
        "dokument": dokument.schluessel,
        "eintraege": [
            {
                "kennung": "NEU",
                "eintragstyp": "grundlagenkapitel",
                "titel": "Neues Kapitel",
                "daten": {"text": "<p>Unser Konzept</p>"},
                "eltern": "2",
                "position": 70,
            }
        ],
    }


def test_json_vorschau_schreibt_nichts(dokument, inhalt):
    vorher = Eintrag.objects.count()
    bericht = pruefen_json(inhalt, dokument)
    assert bericht.ok, bericht.als_text()
    assert Eintrag.objects.count() == vorher
    assert not dokument.eintraege.filter(kennung="NEU").exists()


def test_json_import_aktualisiert_ohne_doppelte_eintraege(dokument, inhalt, admin_nutzer):
    for _ in range(2):
        bericht = uebernehmen_json(inhalt, dokument, admin_nutzer)
        assert bericht.ok, bericht.als_text()
    eintrag = dokument.eintraege.get(kennung="NEU")
    assert eintrag.eltern.kennung == "2"
    assert eintrag.position == 70
    assert eintrag.versionen.count() == 2
    assert eintrag.suchtext


@pytest.mark.parametrize(
    "aenderung",
    [
        {"kennung": ["falsch"]},
        {"eintragstyp": "unbekannt"},
        {"daten": []},
        {"status": {}},
        {"eltern": "FEHLER"},
        {"position": -1},
        {"position": True},
        {"fremdes_feld": "nicht übergehen"},
        {"daten": {"unbekannt": "nicht übergehen"}},
        {"eltern": "unbekannt"},
        {"titel": "x" * 301},
        {"fassung_stand": []},
    ],
)
def test_json_fehler_sind_atomar(dokument, inhalt, aenderung):
    inhalt["eintraege"].append({**inhalt["eintraege"][0], "kennung": "FEHLER", **aenderung})
    vorher = Eintrag.objects.count()
    bericht = uebernehmen_json(inhalt, dokument)
    assert not bericht.ok
    assert Eintrag.objects.count() == vorher


def test_json_erkennt_kreis_ueber_bestehende_kapitel(dokument, inhalt):
    inhalt["eintraege"] = [
        {"kennung": "2", "eintragstyp": "grundlagenkapitel", "titel": "Kreis", "eltern": "2.1"}
    ]
    assert not uebernehmen_json(inhalt, dokument).ok
    assert dokument.eintraege.get(kennung="2").eltern_id is None


def test_json_vorwaertsverweise(dokument, kompetenzen):
    inhalt = {
        "dokument": dokument.schluessel,
        "eintraege": [
            {
                "kennung": "V-3-11",
                "eintragstyp": "vorhaben",
                "titel": "Zuerst",
                "daten": {"jahrgang": 3},
                "bezug_rituale": ["R-11"],
                "eltern": "K-11",
            },
            {"kennung": "R-11", "eintragstyp": "ritual", "titel": "Später", "daten": {}},
            {
                "kennung": "K-11",
                "eintragstyp": "grundlagenkapitel",
                "titel": "Kapitel",
                "daten": {},
            },
        ],
    }
    bericht = uebernehmen_json(inhalt, dokument)
    assert bericht.ok, bericht.als_text()
    e = dokument.eintraege.get(kennung="V-3-11")
    assert e.eltern.kennung == "K-11"
    assert e.verlinkungen.get(feld="bezug_rituale").ziel_id == str(
        dokument.eintraege.get(kennung="R-11").pk
    )
    assert e.letzte_version().verlinkungen


def test_json_abstimmen_verlangt_vollstaendigkeit(dokument, inhalt):
    inhalt["eintraege"][0].update(status="abgestimmt", eintragstyp="vorhaben", daten={})
    assert not uebernehmen_json(inhalt, dokument).ok


def test_json_richtext_wird_gesaeubert(dokument, inhalt):
    inhalt["eintraege"][0]["daten"]["text"] = "<p>Inhalt</p><script>alert(1)</script>"
    assert uebernehmen_json(inhalt, dokument).ok
    assert "<script" not in dokument.eintraege.get(kennung="NEU").daten["text"]


def test_json_oberflaeche_zeigt_vorschau_vor_import(client, admin_nutzer, dokument, inhalt):
    client.force_login(admin_nutzer)
    url = reverse("kern:json_import", args=[dokument.schluessel])
    datei = SimpleUploadedFile("import.json", json.dumps(inhalt).encode(), "application/json")
    antwort = client.post(url, {"datei": datei, "aktion": "vorschau"})
    assert antwort.status_code == 200
    assert b"Gepr" in antwort.content
    assert not dokument.eintraege.filter(kennung="NEU").exists()
    stand = antwort.context["formular"]["ausgangsstand"].value()
    antwort = client.post(
        url, {"inhalt": json.dumps(inhalt), "aktion": "uebernehmen", "ausgangsstand": stand}
    )
    assert antwort.status_code == 302
    assert dokument.eintraege.filter(kennung="NEU").exists()


def test_json_command_vorschau(dokument, inhalt, tmp_path):
    pfad = tmp_path / "import.json"
    pfad.write_text(json.dumps(inhalt))
    call_command("eintraege_importieren", str(pfad), vorschau=True, stdout=io.StringIO())
    assert not dokument.eintraege.filter(kennung="NEU").exists()


def test_neue_dokumenttypen_anlegen_und_bearbeiten(client, admin_nutzer):
    client.force_login(admin_nutzer)
    for typ, eintragstyp in [("konzept", "grundlagenkapitel"), ("protokoll", "tagesordnungspunkt")]:
        dt = Dokumenttyp.objects.get(schluessel=typ)
        antwort = client.post(
            reverse("kern:dokument_neu"),
            {
                "titel": typ,
                "schluessel": typ,
                "dokumenttyp": dt.pk,
            },
        )
        assert antwort.status_code == 302
        dokument = Dokument.objects.get(schluessel=typ)
        url = reverse("kern:eintrag_neu", args=[typ, eintragstyp])
        assert client.get(url).status_code == 200
        assert (
            client.post(
                url, {"titel": "Inhalt", "f_text": "<p>Text</p>", "status": "entwurf"}
            ).status_code
            == 302
        )
        assert dokument.eintraege.filter(eintragstyp=eintragstyp).exists()
        seite = client.get(reverse("kern:dokument", args=[typ]))
        assert b"Abdeckungsmatrix" not in seite.content
    assert (
        Dokument.objects.get(schluessel="protokoll")
        .eintraege.filter(eintragstyp="protokollkopf")
        .exists()
    )


def test_protokolldatum_wird_validiert(client, admin_nutzer):
    dt = Dokumenttyp.objects.get(schluessel="protokoll")
    dokument = Dokument.objects.create(titel="Konferenz", schluessel="konferenz", dokumenttyp=dt)
    client.force_login(admin_nutzer)
    url = reverse("kern:eintrag_neu", args=[dokument.schluessel, "protokollkopf"])
    antwort = client.post(
        url,
        {
            "titel": "Konferenz",
            "status": "abgestimmt",
            "f_datum": "2026-11-09",
            "f_gremium": "Lehrerkonferenz",
        },
    )
    assert antwort.status_code == 302
    assert dokument.eintraege.get().daten["datum"] == "2026-11-09"
    assert client.post(url, {"titel": "Falsch", "f_datum": "kein Datum"}).status_code == 200
    assert dokument.eintraege.count() == 1


@pytest.fixture
def plan_eintrag(dokument, lehrkraft):
    return speichern(
        dokument,
        pruefen(
            dokument,
            Rohsatz(
                kennung="V-3-10",
                eintragstyp="vorhaben",
                titel="Planbares Vorhaben",
                daten={"jahrgang": 3, "quartal": "Q1"},
            ),
        ),
        nutzer=lehrkraft,
    )


def planwahl(dokument, eintrag):
    return {
        "dokument": dokument.schluessel,
        "schuljahr": "2026/27",
        "klasse": "3b",
        "eintrag": eintrag.pk,
        "notiz": "Meine private Erinnerung",
        "erledigt": "on",
    }


def test_planung_ist_privat_und_idempotent(
    client, lehrkraft, andere_lehrkraft, dokument, plan_eintrag
):
    url = reverse("kern:planung")
    daten = planwahl(dokument, plan_eintrag)
    client.force_login(lehrkraft)
    for _ in range(2):
        assert client.post(url, daten).status_code == 302
    f = PersoenlicherFortschritt.objects.get()
    assert f.nutzer == lehrkraft
    assert f.erledigt_am
    zeitpunkt = f.erledigt_am
    client.post(url, daten)
    f.refresh_from_db()
    assert f.erledigt_am == zeitpunkt
    client.force_login(andere_lehrkraft)
    antwort = client.get(url, daten)
    assert antwort.status_code == 200
    assert b"Meine private Erinnerung" not in antwort.content
    client.force_login(lehrkraft)
    daten.pop("erledigt")
    client.post(url, daten)
    f.refresh_from_db()
    assert not f.erledigt
    assert f.erledigt_am is None
    assert PersoenlicherFortschritt not in admin.site._registry


def test_planung_trennt_schuljahre_und_klassen(client, lehrkraft, dokument, plan_eintrag):
    client.force_login(lehrkraft)
    daten = planwahl(dokument, plan_eintrag)
    url = reverse("kern:planung")
    client.post(url, daten)
    for zusatz in [{"klasse": "3c"}, {"schuljahr": "2027/28"}]:
        antwort = client.get(url, {**daten, **zusatz})
        assert b"Meine private Erinnerung" not in antwort.content


def test_planung_sperrt_fremden_jahrgang(client, lehrkraft, dokument, plan_eintrag):
    client.force_login(lehrkraft)
    daten = {**planwahl(dokument, plan_eintrag), "klasse": "1a"}
    assert client.post(reverse("kern:planung"), daten).status_code == 403
    assert not PersoenlicherFortschritt.objects.exists()


@pytest.mark.parametrize("rolle", ["lehrkraft", "lesend_nutzer"])
def test_import_export_und_dokumentanlage_nur_administration(client, request, rolle, dokument):
    client.force_login(request.getfixturevalue(rolle))
    for url in [
        reverse("kern:dokument_neu"),
        reverse("kern:json_import", args=[dokument.schluessel]),
        *[reverse("kern:export", args=[dokument.schluessel, f]) for f in ["json", "xlsx", "pdf"]],
    ]:
        assert client.get(url).status_code == 403


def test_lesende_haben_keine_planung(client, lesend_nutzer):
    client.force_login(lesend_nutzer)
    assert client.get(reverse("kern:planung")).status_code == 403


def test_xlsx_rundlauf_mit_verweisen_und_richtext(importierter_arbeitsplan, tmp_path):
    dokument = importierter_arbeitsplan
    vorher = {
        e.kennung: (e.daten, list(e.verlinkungen.values_list("feld", "ziel_id")))
        for e in dokument.eintraege.filter(eintragstyp__in=["ritual", "vorhaben"])
    }
    pfad = tmp_path / "export.xlsx"
    pfad.write_bytes(exporte.dokument_xlsx(dokument))
    bericht = uebernehmen(pfad, dokument, mit_beispielen=True)
    assert bericht.ok, bericht.als_text()
    for e in dokument.eintraege.filter(eintragstyp__in=["ritual", "vorhaben"]):
        assert e.daten == vorher[e.kennung][0]
        assert list(e.verlinkungen.values_list("feld", "ziel_id")) == vorher[e.kennung][1]


def test_xlsx_text_wird_nicht_zur_formel(dokument, plan_eintrag):
    plan_eintrag.titel = "=1+1"
    plan_eintrag.save()
    mappe = load_workbook(io.BytesIO(exporte.dokument_xlsx(dokument)), data_only=False)
    assert mappe["Vorhaben"]["B2"].value == "=1+1"
    assert mappe["Vorhaben"]["B2"].data_type == "s"
    mappe.close()


def test_json_export_rundlauf_enthaelt_fassungen_und_gliederung(importierter_arbeitsplan):
    dokument = importierter_arbeitsplan
    daten = json.loads(exporte.dokument_json(dokument))
    assert daten["schema_version"] == 1
    assert daten["metadaten"]["titel"] == dokument.titel
    assert any(e["fassungen"] for e in daten["eintraege"])
    bericht = uebernehmen_json(daten, dokument)
    assert bericht.ok, bericht.als_text()


@pytest.fixture
def beschlossen_mit_entwurf(dokument, kompetenzen, admin_nutzer):
    e = speichern(
        dokument,
        pruefen(
            dokument,
            Rohsatz(
                kennung="PDF-1",
                eintragstyp="grundlagenkapitel",
                titel="Gültiger Titel",
                daten={"text": "<p>Verbindlicher Inhalt</p>"},
                status=Status.ABGESTIMMT,
            ),
        ),
        nutzer=admin_nutzer,
    )
    b = Beschluss.objects.create(
        datum=date(2026, 10, 30),
        titel="Freigabe",
        gremium=Gremium.objects.create(name="Lehrerkonferenz"),
    )
    beschluesse.beschluss_fassen(b, [e], nutzer=admin_nutzer)
    speichern(
        dokument,
        pruefen(
            dokument,
            Rohsatz(
                kennung=e.kennung,
                eintragstyp=e.eintragstyp,
                titel="Neuer Entwurfstitel",
                daten={"text": "<p>Noch nicht gültiger Inhalt</p>"},
            ),
        ),
        nutzer=admin_nutzer,
    )
    e.refresh_from_db()
    return e


def test_pdf_bewahrt_beschlossenen_stand_bei_neuem_entwurf(
    client, admin_nutzer, beschlossen_mit_entwurf
):
    e = beschlossen_mit_entwurf
    client.force_login(admin_nutzer)
    antwort = client.get(reverse("kern:export", args=[e.dokument.schluessel, "pdf"]))
    assert antwort.status_code == 200
    assert antwort.content.startswith(b"%PDF-")
    reader = PdfReader(io.BytesIO(antwort.content))
    text = "\n".join(p.extract_text() for p in reader.pages)
    assert "Gültiger Titel" in text
    assert "Verbindlicher Inhalt" in text
    assert "Neuer Entwurfstitel" not in text
    assert "Noch nicht gültiger Inhalt" not in text
    assert "Abdeckungsmatrix" in text
    assert "Lehrerkonferenz" in text


def test_pdf_beschlussvorlage_auswahl_und_aenderungen(
    client, redaktion_nutzer, beschlossen_mit_entwurf
):
    e = beschlossen_mit_entwurf
    e.status = Status.ABGESTIMMT
    e.save()
    client.force_login(redaktion_nutzer)
    url = reverse("kern:vorlage_pdf")
    assert client.get(url).status_code == 400
    antwort = client.get(url, {"eintrag": e.pk})
    assert antwort.status_code == 200
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(antwort.content)).pages)
    assert "Neuer Entwurfstitel" in text
    assert "Verbindlicher" in text
    assert "Änderungen" in text


def test_pdf_leeres_dokument(client, admin_nutzer, dokument):
    client.force_login(admin_nutzer)
    antwort = client.get(reverse("kern:export", args=[dokument.schluessel, "pdf"]))
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(antwort.content)).pages)
    assert "noch keine Inhalte beschlossen" in text
    assert "Rahmenbedingungen" not in text


def test_json_verweise_pruefen_vor_jeder_speicherung(dokument, kompetenzen):
    inhalt = {
        "dokument": dokument.schluessel,
        "eintraege": [
            {
                "kennung": "V-3-11",
                "eintragstyp": "vorhaben",
                "titel": "Ungültiger Verweis",
                "kompetenzen_schwerpunkt": ["UNBEKANNT"],
                "daten": {"jahrgang": 3},
            }
        ],
    }
    assert not uebernehmen_json(inhalt, dokument).ok
    assert not dokument.eintraege.filter(kennung="V-3-11").exists()


@pytest.mark.parametrize("wert", [float("nan"), float("inf"), -float("inf")])
def test_json_zahlen_muessen_endlich_sein(dokument, wert):
    inhalt = {
        "dokument": dokument.schluessel,
        "eintraege": [
            {
                "kennung": "R-12",
                "eintragstyp": "ritual",
                "titel": "Kein gültiger Takt",
                "daten": {"minuten_je_einheit": wert},
            }
        ],
    }
    assert not uebernehmen_json(inhalt, dokument).ok


def test_planung_mit_freiem_klassennamen(client, lehrkraft, dokument, plan_eintrag):
    client.force_login(lehrkraft)
    daten = {**planwahl(dokument, plan_eintrag), "klasse": "Lerngruppe", "jahrgang": 3}
    assert client.post(reverse("kern:planung"), daten).status_code == 302
    assert PersoenlicherFortschritt.objects.get().klasse == "lerngruppe"


def test_pdf_abdeckung_nutzt_beschlossene_verweise(dokument, kompetenzen, admin_nutzer):
    e = speichern(
        dokument,
        pruefen(
            dokument,
            Rohsatz(
                kennung="R-20",
                eintragstyp="ritual",
                titel="Ritual",
                verweise={"kompetenzen_schwerpunkt": ["SC2.02D"]},
            ),
        ),
        nutzer=admin_nutzer,
    )
    # Freigabe für den Prüffall unmittelbar anlegen; fachliche Vollständigkeit
    # gehört zu den Beschlusstests. Hier zählt allein die Quellfassung der Matrix.
    b = Beschluss.objects.create(
        datum=date(2026, 10, 30), titel="Freigabe", gremium=Gremium.objects.create(name="Konferenz")
    )
    v = e.letzte_version()
    v.status = Status.BESCHLOSSEN
    v.beschluss = b
    v.save()
    e.status = Status.BESCHLOSSEN
    e.save()
    speichern(
        dokument,
        pruefen(
            dokument,
            Rohsatz(
                kennung=e.kennung,
                eintragstyp=e.eintragstyp,
                titel="Entwurf",
                verweise={"kompetenzen_schwerpunkt": ["SC2.03D"]},
            ),
        ),
        nutzer=admin_nutzer,
    )
    matrix = {
        z.erwartung.pk: z
        for z in exporte.abdeckung_des_stands(exporte.beschlossener_stand(dokument))
    }
    assert matrix["SC2.02D"].abdeckung == "schwerpunkt"
    assert matrix["SC2.03D"].abdeckung == "fehlt"
