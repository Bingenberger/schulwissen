"""AP10: Aufgaben, kanonische Fassungen, Formularzweck und sichere PDF-Einstiege."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from eintragstypen import dienste
from eintragstypen.import_json import pruefen_json, uebernehmen_json
from kern import beschluesse, funktionen, handbuch
from kern.models import Anhang, Dokument, FreigegebeneDatei, Funktionsbesetzung
from suche import dienste as suche
from tests import test_prozesslesen
from tests.test_prozessdaten import beispiel, beschluss
from tests.test_prozesslesen import url

handbuch_dokument = test_prozesslesen.handbuch
funktion = test_prozesslesen.funktion
pytestmark = pytest.mark.django_db


def schreiben(
    d, kennung="H-01", titel="Fiktive Kurzantwort", daten=None, typ="grundlagenkapitel", **meta
):
    roh = dienste.Rohsatz(
        kennung=kennung,
        eintragstyp=typ,
        titel=titel,
        daten=daten or {"text": "<p>Nur zur Bedienprüfung. Keine echte Schulregel.</p>"},
    )
    return dienste.speichern(d, dienste.pruefen(d, roh), metadaten=meta)


def frei(e):
    beschluesse.beschluss_fassen(beschluss(), [e])
    return e


def formular(d, funktion, key="F-01", aufgabe="fahrten"):
    e = schreiben(
        d,
        kennung=key,
        titel="Fiktive Ausflugsvorlage",
        inhaltsart="formular",
        aufgabe=aufgabe,
        kurzantwort="Verwendungszweck: Nur eine fiktive Bedienprüfung.",
        suchbegriffe="Exkursion Ausflugsantrag",
        pflege_funktion=funktion,
    )
    Anhang.objects.create(
        eintrag=e,
        dokument=d,
        dateiname="Freigegebene Demo.pdf",
        mimetype="application/pdf",
        verwendung="verbindlich",
        dateiversion="Fiktive PDF-Fassung 1",
        datei=SimpleUploadedFile("demo.pdf", b"%PDF-1.4\nAusdruecklich fiktive PDF-Pruefbytes"),
    )
    return frei(e)


@pytest.mark.parametrize("aufgabe", ["fahrten", "abwesenheit", "it", "material"])
def test_aufgabeneinstieg_fuehrt_zu_einer_quelle_mit_kontakt_und_formular(
    client, handbuch_dokument, funktion, lehrkraft, aufgabe
):
    Funktionsbesetzung.objects.create(funktion=funktion, person=lehrkraft)
    f = formular(handbuch_dokument, funktion, aufgabe=aufgabe)
    g = beispiel()
    g["knoten"][2]["verweise"] = [
        {"typ": "eintrag", "dokument": handbuch_dokument.schluessel, "kennung": f.kennung}
    ]
    e = frei(
        schreiben(
            handbuch_dokument,
            kennung="PR-01",
            titel="Fiktiver schulischer Ablauf",
            typ="prozess",
            daten={"anlass": "Fiktive Prüfung", "ablauf": g},
            aufgabe=aufgabe,
            kurzantwort="Ausdrücklich fiktive erste Orientierung.",
        )
    )
    client.force_login(lehrkraft)
    r = client.get(reverse("kern:handbuch"), {"aufgabe": aufgabe})
    assert r.status_code == 200
    assert len(r.context["karten"]) == 2
    prozess = next(k for k in r.context["karten"] if k["prozess"])
    assert prozess["bezug"][0]["url"] == url(f, "version", 1)
    assert prozess["kontakte"][0]["personen"] == [lehrkraft.anzeigename]
    r = client.get(reverse("kern:formulare"), {"aufgabe": aufgabe})
    karte = r.context["karten"][0]
    assert karte["url"] == url(f, "version", 1)
    assert karte["bezug"][0]["url"] == url(e, "version", 1)
    assert karte["anlagen"][0]["pdf"]
    antwort = client.get(karte["anlagen"][0]["url"])
    assert b"".join(antwort.streaming_content).startswith(b"%PDF-1.4")
    assert (
        client.get(reverse("kern:export", args=[handbuch_dokument.schluessel, "json"])).status_code
        == 403
    )


def test_synonyme_und_kurzantwort_sind_in_allen_einstiegen_dieselbe_fassung(
    client, handbuch_dokument, funktion, lehrkraft
):
    f = formular(handbuch_dokument, funktion)
    n = f.versionen.count()
    f = schreiben(
        handbuch_dokument,
        kennung=f.kennung,
        titel="NichtausgebenEntwurfstitel",
        kurzantwort="NichtausgebenKurzantwort",
        suchbegriffe="NichtausgebenSynonym",
        inhaltsart="information",
        aufgabe="it",
    )
    client.force_login(lehrkraft)
    for route in ["handbuch", "formulare"]:
        r = client.get(reverse("kern:" + route), {"q": "Exkursion"})
        assert r.context["karten"][0]["url"] == url(f, "version", 1)
        assert "Nichtausgeben" not in r.content.decode()
        assert not client.get(reverse("kern:" + route), {"q": "NichtausgebenSynonym"}).context[
            "karten"
        ]
    r = client.get(reverse("suche:suchen"), {"q": "Exkursion"})
    assert "Fiktive Ausflugsvorlage" in r.content.decode()
    assert "Nichtausgeben" not in r.content.decode()
    vorschlaege = suche.vorschlaege(lehrkraft, "Exkursion")
    assert vorschlaege[0].url == url(f, "version", 1)
    assert not suche.vorschlaege(lehrkraft, "NichtausgebenEntwurfstitel")
    assert not suche.suchen(lehrkraft, "Nichtausgeben", gruppe="eintraege").gesamt
    assert f.versionen.count() == n + 1


def test_gesperrte_dokumente_geben_keine_karten_aufgabenzaehlung_oder_suchtreffer(
    client, handbuch_dokument, funktion, lesend_nutzer
):
    formular(handbuch_dokument, funktion)
    handbuch_dokument.kollegiumsweit = False
    handbuch_dokument.save()
    client.force_login(lesend_nutzer)
    for route in ["handbuch", "formulare"]:
        r = client.get(reverse("kern:" + route))
        assert r.context["seite"].paginator.count == 0
        assert all(b["anzahl"] == 0 for b in r.context["bereiche"])
        assert "Fiktive Ausflugsvorlage" not in r.content.decode()
    assert not suche.suchen(lesend_nutzer, "Exkursion", gruppe="handbuch").gesamt


def test_zukuenftige_und_abgelaufene_formulare_verdraengen_heutige_nicht(
    client, handbuch_dokument, funktion, lesend_nutzer
):
    f = formular(handbuch_dokument, funktion)
    f = schreiben(
        handbuch_dokument,
        kennung=f.kennung,
        titel="Späteres Formular",
        inhaltsart="formular",
        kurzantwort="Späterer Zweck",
        wirksam_ab=timezone.localdate() + timedelta(days=1),
        wirksam_bis=timezone.localdate() + timedelta(days=2),
    )
    frei(f)
    client.force_login(lesend_nutzer)
    assert (
        client.get(reverse("kern:formulare")).context["karten"][0]["titel"]
        == "Fiktive Ausflugsvorlage"
    )
    with patch(
        "django.utils.timezone.localdate", return_value=timezone.localdate() + timedelta(days=3)
    ):
        assert not client.get(reverse("kern:formulare")).context["karten"]


def test_aktuelle_besetzung_auch_bei_unveraenderter_formularfassung(
    client, handbuch_dokument, funktion, lehrkraft, andere_lehrkraft
):
    alt = Funktionsbesetzung.objects.create(funktion=funktion, person=lehrkraft)
    f = formular(handbuch_dokument, funktion)
    client.force_login(lehrkraft)
    n = f.versionen.count()
    funktionen.wechseln(alt, andere_lehrkraft, timezone.localdate())
    karte = client.get(reverse("kern:formulare")).context["karten"][0]
    assert karte["kontakte"][0]["personen"] == [andere_lehrkraft.anzeigename]
    assert f.versionen.count() == n


def test_formularverzeichnis_zeigt_gepruefte_bytes_trotz_originalaenderung(
    client, handbuch_dokument, funktion, lesend_nutzer
):
    f = formular(handbuch_dokument, funktion)
    a = f.anhaenge.get()
    with a.datei.storage.open(a.datei.name, "wb") as datei:
        datei.write(b"Neuere Entwurfsdatei")
    client.force_login(lesend_nutzer)
    m = client.get(reverse("kern:formulare")).context["karten"][0]["anlagen"][0]
    assert "Original hat sich geändert" in m["pruefhinweis"]
    assert b"".join(client.get(m["url"]).streaming_content).startswith(b"%PDF-1.4")


def test_prozessbezug_verraet_keinen_privaten_oder_neueren_prozess(
    client, handbuch_dokument, funktion, lehrkraft
):
    f = formular(handbuch_dokument, funktion)
    privat = Dokument.objects.create(
        schluessel="privat",
        titel="NichtausgebenPrivatdokument",
        dokumenttyp=handbuch_dokument.dokumenttyp,
        kollegiumsweit=False,
    )
    g = beispiel()
    g["knoten"][2]["verweise"] = [
        {"typ": "eintrag", "dokument": handbuch_dokument.schluessel, "kennung": f.kennung}
    ]
    frei(
        schreiben(
            privat,
            kennung="PR-01",
            titel="NichtausgebenPrivatprozess",
            typ="prozess",
            daten={"anlass": "Privat", "ablauf": g},
        )
    )
    client.force_login(lehrkraft)
    r = client.get(reverse("kern:formulare"))
    assert not r.context["karten"][0]["bezug"]
    assert "Nichtausgeben" not in r.content.decode()


def test_private_dateiquelle_bleibt_auch_im_formularverzeichnis_geschuetzt(
    client, handbuch_dokument, funktion, lesend_nutzer
):
    f = formular(handbuch_dokument, funktion)
    k = FreigegebeneDatei.objects.get(version=f.letzte_version())
    privat = Dokument.objects.create(
        schluessel="dateiprivat",
        titel="Geheim",
        dokumenttyp=handbuch_dokument.dokumenttyp,
        kollegiumsweit=False,
    )
    a = k.original
    a.dokument = privat
    a.save()
    client.force_login(lesend_nutzer)
    r = client.get(reverse("kern:formulare"))
    assert "Freigegebene Demo.pdf" not in r.content.decode()
    assert not r.context["karten"][0]["anlagen"][0]["url"]


def test_formular_ohne_zweck_oder_verbindliche_datei_wird_nicht_freigegeben(handbuch_dokument):
    e = schreiben(handbuch_dokument, inhaltsart="formular")
    with pytest.raises(ValidationError, match="Verwendungszweck"):
        frei(e)
    e = schreiben(handbuch_dokument, inhaltsart="formular", kurzantwort="Fiktiver Zweck")
    with pytest.raises(ValidationError, match="Dateifassung"):
        frei(e)
    assert e.beschlossene_version() is None


def test_paginierung_und_aufgabenfilter_sind_vor_zaehlung_angewandt(
    client, handbuch_dokument, lehrkraft
):
    for n in range(14):
        frei(
            schreiben(
                handbuch_dokument, kennung=f"H-{n:02d}", aufgabe="it", kurzantwort="Fiktive Hilfe"
            )
        )
    frei(schreiben(handbuch_dokument, kennung="H-MAT", aufgabe="material"))
    client.force_login(lehrkraft)
    r = client.get(reverse("kern:handbuch"), {"aufgabe": "it"})
    assert r.context["seite"].paginator.count == 14
    assert len(r.context["karten"]) == 12
    assert (
        len(client.get(reverse("kern:handbuch"), {"aufgabe": "it", "seite": 2}).context["karten"])
        == 2
    )
    assert next(b["anzahl"] for b in r.context["bereiche"] if b["key"] == "it") == 14


def test_aufgabe_und_synonyme_ueber_json_rundlauf(handbuch_dokument, lehrkraft):
    from kern.exporte import dokument_json

    e = schreiben(
        handbuch_dokument,
        aufgabe="it",
        kurzantwort="Fiktive Kurzantwort",
        suchbegriffe="Rechner kaputt Support",
    )
    daten = json.loads(dokument_json(handbuch_dokument))
    bericht = uebernehmen_json(daten, handbuch_dokument, nutzer=lehrkraft)
    assert bericht.ok, bericht.als_text()
    e.refresh_from_db()
    assert e.aufgabe == "it"
    assert e.suchbegriffe == "Rechner kaputt Support"
    assert e.letzte_version().kurzantwort == "Fiktive Kurzantwort"
    daten["eintraege"][0]["wissensangaben"]["aufgabe"] = "unbekannt"
    assert not pruefen_json(daten, handbuch_dokument, nutzer=lehrkraft).ok


def test_html_in_kurzantwort_und_synonymen_wird_escaped(client, handbuch_dokument, lehrkraft):
    frei(
        schreiben(
            handbuch_dokument,
            kurzantwort='<script>alert("x")</script>',
            suchbegriffe="<img src=x onerror=alert(1)>",
        )
    )
    client.force_login(lehrkraft)
    r = client.get(reverse("kern:handbuch"))
    assert '<script>alert("x")</script>' not in r.content.decode()
    assert "&lt;script&gt;" in r.content.decode()


def test_anonyme_einstiege_sind_geschuetzt(client):
    assert client.get(reverse("kern:handbuch")).status_code == 302
    assert client.get(reverse("kern:formulare")).status_code == 302


def test_aufnahmevorlage_enthaelt_nur_zehn_nicht_freigabefaehige_entwuerfe(
    handbuch_dokument, admin_nutzer
):
    from pathlib import Path

    handbuch_dokument.schluessel = "aufnahme-schulhandbuch"
    handbuch_dokument.save()
    inhalt = json.loads(Path("docs/beispiele/ap10-aufnahmeplan.json").read_text())
    bericht = pruefen_json(inhalt, handbuch_dokument, nutzer=admin_nutzer)
    assert bericht.ok, bericht.als_text()
    assert len(bericht.saetze) == 10
    assert all(s.roh.status == "entwurf" for s in bericht.saetze)
    uebernehmen_json(inhalt, handbuch_dokument, nutzer=admin_nutzer)
    assert handbuch.menge(admin_nutzer).count() == 0
    e = handbuch_dokument.eintraege.first()
    with pytest.raises(ValidationError):
        frei(e)


def test_neue_formularklassifikation_im_entwurf_zieht_keine_alte_info_ins_handbuch(
    client, handbuch_dokument, lehrkraft
):
    from kern.models import Dokumenttyp

    d = Dokument.objects.create(
        schluessel="konzept",
        titel="Allgemeines Konzept",
        dokumenttyp=Dokumenttyp.objects.get(schluessel="konzept"),
    )
    e = frei(schreiben(d, kurzantwort="Gültige Information"))
    schreiben(d, inhaltsart="formular", kurzantwort="Künftiger Formularzweck")
    client.force_login(lehrkraft)
    assert not client.get(reverse("kern:handbuch")).context["karten"]
    assert e.beschlossene_version().inhaltsart == "ungeklaert"


def test_vorhandene_konzeptquelle_wird_durch_bestaetigte_aufgabe_ohne_kopie_erreichbar(
    client, handbuch_dokument, lehrkraft
):
    from kern.models import Dokumenttyp

    d = Dokument.objects.create(
        schluessel="alltagskonzept",
        titel="Bestehendes Konzept",
        dokumenttyp=Dokumenttyp.objects.get(schluessel="konzept"),
    )
    e = frei(
        schreiben(
            d, aufgabe="it", kurzantwort="Fiktive bestätigte Kurzantwort", suchbegriffe="Demohilfe"
        )
    )
    client.force_login(lehrkraft)
    k = client.get(reverse("kern:handbuch"), {"aufgabe": "it"}).context["karten"][0]
    assert k["url"] == url(e, "version", 1)
    assert k["dokument"] == "Bestehendes Konzept"
    assert handbuch_dokument.eintraege.count() == 0
