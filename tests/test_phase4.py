"""Nextcloud-Synchronisation, echte OIDC-Tokenprüfung und Fachtrennung."""

import io
import json
import time
from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import requests
from django.core.management import call_command
from django.urls import reverse
from joserfc import jwt
from joserfc.jwk import RSAKey

from deutsch.auswertungen import abdeckungsmatrix
from eintragstypen.dienste import Rohsatz, pruefen
from fachdaten.importe import importieren
from fachdaten.models import Fach, Kompetenzerwartung
from kern.models import Anhang, Dokument, Dokumenttyp, OIDCIdentitaet
from kern.nextcloud_index import indexieren

pytestmark = pytest.mark.django_db


@pytest.fixture
def remote(settings):
    settings.NEXTCLOUD_URL = "https://cloud.example.org"
    settings.NEXTCLOUD_NUTZER = "technik"
    settings.NEXTCLOUD_PASSWORT = "app-passwort"
    settings.NEXTCLOUD_MAX_BYTES = 1024
    return settings


@pytest.fixture
def nc_anhang(dokument):
    return Anhang.objects.create(
        dokument=dokument,
        eintrag=dokument.eintraege.get(kennung="2.4"),
        dateiname="Konzept.txt",
        nextcloud_pfad="Konzepte/Konzept.txt",
    )


def http_antwort(monkeypatch, handler):
    original_stream = httpx.stream

    @contextmanager
    def stream(method, url, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with client.stream(method, url, **kwargs) as antwort:
                yield antwort

    monkeypatch.setattr(httpx, "stream", stream)
    return original_stream


def test_nextcloud_etag_verhindert_erneutes_lesen(remote, nc_anhang, monkeypatch):
    anfragen = []

    def handler(request):
        anfragen.append(request)
        if request.headers.get("If-None-Match") == '"etag-1"':
            return httpx.Response(304)
        return httpx.Response(
            200,
            content=b"Mathematik und Geometrie",
            headers={"ETag": '"etag-1"', "Content-Type": "text/plain"},
        )

    http_antwort(monkeypatch, handler)
    assert indexieren(nc_anhang) == "gelesen"
    erster_stand = nc_anhang.index_stand
    assert "Geometrie" in nc_anhang.extrahierter_text
    assert indexieren(nc_anhang) == "unverändert"
    assert nc_anhang.index_stand == erster_stand
    assert anfragen[-1].headers["If-None-Match"] == '"etag-1"'
    assert not nc_anhang.datei


@pytest.mark.parametrize("status", [403, 404, 410])
def test_nextcloud_entfernte_dateien_verlieren_suchtext(remote, nc_anhang, monkeypatch, status):
    nc_anhang.extrahierter_text = "Nicht mehr freigegebener Text"
    nc_anhang.save()
    http_antwort(monkeypatch, lambda request: httpx.Response(status))
    assert indexieren(nc_anhang) == "entfernt"
    nc_anhang.refresh_from_db()
    assert nc_anhang.extrahierter_text == ""
    assert nc_anhang.index_fehler
    nc_anhang.eintrag.refresh_from_db()
    assert "Nicht mehr freigegebener Text" not in nc_anhang.eintrag.suchtext


def test_nextcloud_ausfall_behaelt_letzten_guten_stand(remote, nc_anhang, monkeypatch):
    nc_anhang.extrahierter_text = "Letzter lesbarer Stand"
    nc_anhang.save()
    http_antwort(monkeypatch, lambda request: httpx.Response(503))
    assert indexieren(nc_anhang) == "fehlgeschlagen"
    nc_anhang.refresh_from_db()
    assert nc_anhang.extrahierter_text == "Letzter lesbarer Stand"
    assert nc_anhang.nextcloud_geprueft_am


def test_nextcloud_stream_ist_begrenzt(remote, nc_anhang, monkeypatch):
    http_antwort(monkeypatch, lambda request: httpx.Response(200, content=b"x" * 2048))
    assert indexieren(nc_anhang) == "fehlgeschlagen"
    assert nc_anhang.index_stand is None
    assert nc_anhang.nextcloud_etag == ""


def test_nextcloud_folgt_keinen_redirects(remote, nc_anhang, monkeypatch):
    anfragen = []

    def handler(request):
        anfragen.append(request.url)
        return httpx.Response(302, headers={"Location": "https://fremd.example.org/geheim"})

    http_antwort(monkeypatch, handler)
    assert indexieren(nc_anhang) == "fehlgeschlagen"
    assert len(anfragen) == 1


def test_nextcloud_kommando_verarbeitet_auch_spaetere_dateien(remote, nc_anhang, monkeypatch):
    zweiter = Anhang.objects.create(
        dokument=nc_anhang.dokument, dateiname="Z.txt", nextcloud_pfad="Z.txt"
    )
    http_antwort(monkeypatch, lambda request: httpx.Response(200, content=b"Lesbarer Text"))
    call_command("nextcloud_indexieren", anzahl=1, stdout=io.StringIO())
    call_command("nextcloud_indexieren", anzahl=1, stdout=io.StringIO())
    zweiter.refresh_from_db()
    assert zweiter.index_stand


@pytest.fixture
def oidc_provider(settings, monkeypatch):
    settings.OIDC_ISSUER = "https://cloud.example.org"
    settings.OIDC_DISCOVERY_URL = "https://cloud.example.org/discovery"
    settings.OIDC_CLIENT_ID = "schulwissen"
    settings.OIDC_CLIENT_SECRET = "test-secret"
    settings.OEFFENTLICHE_URL = "http://testserver"
    key = RSAKey.generate_key(2048, parameters={"kid": "test"})
    daten = {
        "nonce": "",
        "sub": "nextcloud-123",
        "iss": settings.OIDC_ISSUER,
        "aud": settings.OIDC_CLIENT_ID,
        "key": key,
        "token_anfragen": [],
    }

    def request(session, method, url, **kwargs):
        if url.endswith("/discovery"):
            body = {
                "issuer": settings.OIDC_ISSUER,
                "authorization_endpoint": settings.OIDC_ISSUER + "/authorize",
                "token_endpoint": settings.OIDC_ISSUER + "/token",
                "jwks_uri": settings.OIDC_ISSUER + "/jwks",
                "id_token_signing_alg_values_supported": ["RS256"],
            }
        elif url.endswith("/jwks"):
            body = {"keys": [key.as_dict(private=False)]}
        elif url.endswith("/token"):
            daten["token_anfragen"].append(kwargs)
            claims = {
                "iss": daten["iss"],
                "sub": daten["sub"],
                "aud": daten["aud"],
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
                "nonce": daten["nonce"],
                "email": "leitung@example.org",
            }
            body = {
                "access_token": "ein-token",
                "token_type": "Bearer",
                "id_token": jwt.encode({"alg": "RS256", "kid": "test"}, claims, daten["key"]),
            }
        else:
            raise AssertionError(f"Unerwarteter externer Aufruf: {url}")
        antwort = requests.Response()
        antwort.status_code = 200
        antwort._content = json.dumps(body).encode()
        antwort.headers["Content-Type"] = "application/json"
        return antwort

    monkeypatch.setattr(requests.sessions.Session, "request", request)
    return daten


def oidc_start(client, provider, verbinden=False):
    antwort = (
        client.post(reverse("kern:oidc_verbinden"))
        if verbinden
        else client.get(reverse("kern:oidc_anmelden"))
    )
    assert antwort.status_code == 302
    parameter = parse_qs(urlparse(antwort.url).query)
    assert parameter["code_challenge_method"] == ["S256"]
    assert parameter["code_challenge"]
    provider["nonce"] = parameter["nonce"][0]
    return parameter["state"][0]


def test_oidc_verknuepfung_und_login_mit_signiertem_token(client, lehrkraft, oidc_provider):
    client.force_login(lehrkraft)
    state = oidc_start(client, oidc_provider, verbinden=True)
    antwort = client.get(reverse("kern:oidc_callback"), {"state": state, "code": "test-code"})
    assert antwort.status_code == 302
    assert OIDCIdentitaet.objects.get().nutzer == lehrkraft
    client.logout()
    state = oidc_start(client, oidc_provider)
    antwort = client.get(reverse("kern:oidc_callback"), {"state": state, "code": "test-code"})
    assert antwort.status_code == 302
    assert int(client.session["_auth_user_id"]) == lehrkraft.pk
    assert "code_verifier" in oidc_provider["token_anfragen"][-1]["data"]
    assert (
        client.get(reverse("kern:oidc_callback"), {"state": state, "code": "test-code"}).status_code
        == 403
    )


@pytest.mark.parametrize("fehler", ["nonce", "iss", "aud", "key"])
def test_oidc_falsche_token_werden_abgelehnt(client, lehrkraft, oidc_provider, fehler):
    OIDCIdentitaet.objects.create(
        nutzer=lehrkraft, issuer="https://cloud.example.org", subject=oidc_provider["sub"]
    )
    state = oidc_start(client, oidc_provider)
    oidc_provider[fehler] = RSAKey.generate_key(2048) if fehler == "key" else "falsch"
    antwort = client.get(reverse("kern:oidc_callback"), {"state": state, "code": "test-code"})
    assert antwort.status_code in (302, 403)
    assert "_auth_user_id" not in client.session


def test_oidc_keine_automatische_kontouebernahme(client, admin_nutzer, oidc_provider):
    state = oidc_start(client, oidc_provider)
    assert (
        client.get(reverse("kern:oidc_callback"), {"state": state, "code": "test-code"}).status_code
        == 403
    )
    assert not OIDCIdentitaet.objects.exists()
    assert "_auth_user_id" not in client.session


def test_oidc_state_pruefung_vor_tokenabruf(client, oidc_provider):
    oidc_start(client, oidc_provider)
    assert (
        client.get(reverse("kern:oidc_callback"), {"state": "fremd", "code": "x"}).status_code
        == 403
    )
    assert not oidc_provider["token_anfragen"]


def test_oidc_deaktiviert_ohne_konfiguration(client, settings):
    settings.OIDC_ISSUER = ""
    assert client.get(reverse("kern:oidc_anmelden")).status_code == 404
    assert b"Mit Nextcloud anmelden" not in client.get(reverse("kern:anmelden")).content


def test_alle_zehn_faecher_der_primarstufe_sind_vorhanden():
    """Die zehn Lehrpläne des Sammelbands – mit ihren amtlichen Namen."""
    assert set(Fach.objects.values_list("name", flat=True)) == {
        "Deutsch",
        "Englisch",
        "Evangelische Religionslehre",
        "Katholische Religionslehre",
        "Kunst",
        "Mathematik",
        "Musik",
        "Praktische Philosophie",
        "Sachunterricht",
        "Sport",
    }
    # Jedes Fach kennt seine Kompetenzbereiche, sonst scheitert der Import.
    assert all(fach.bereiche for fach in Fach.objects.all())


@pytest.fixture
def mathematik_datei(tmp_path):
    fach = Fach.objects.get(schluessel="mathematik")
    fach.bereiche = {"ZA": "Testbereich Zahlen"}
    fach.save()
    pfad = tmp_path / "testkompetenzen.json"
    pfad.write_text(
        json.dumps(
            [
                {
                    "id": "M-ZA1.01S",
                    "bereich": "ZA",
                    "bereichName": "Testbereich Zahlen",
                    "schwerpunktNr": 1,
                    "schwerpunkt": "Testschwerpunkt",
                    "stufe": "S",
                    "text": "Synthetische Testkompetenz, keine Lehrplanvorgabe.",
                }
            ]
        )
    )
    return pfad


def test_fachimport_und_suche_getrennt(client, lehrkraft, mathematik_datei):
    bericht = importieren(mathematik_datei, fach="mathematik")
    assert not bericht.fehler, bericht.als_text()
    client.force_login(lehrkraft)
    antwort = client.get(reverse("fachdaten:uebersicht"), {"fach": "mathematik"})
    assert "Synthetische Testkompetenz" in antwort.content.decode()
    assert (
        "Synthetische Testkompetenz"
        not in client.get(reverse("fachdaten:uebersicht")).content.decode()
    )


def test_fachimport_ueberschreibt_keine_fremden_kennungen(kompetenzen, mathematik_datei):
    daten = json.loads(mathematik_datei.read_text())
    daten[0]["id"] = "SC2.02D"
    mathematik_datei.write_text(json.dumps(daten))
    assert importieren(mathematik_datei, fach="mathematik").fehler
    assert Kompetenzerwartung.objects.get(pk="SC2.02D").fach == "deutsch"


def test_falscher_progressionspartner_rollt_alles_zurueck(mathematik_datei):
    daten = json.loads(mathematik_datei.read_text())
    daten[0]["progressionspartner"] = "UNBEKANNT"
    mathematik_datei.write_text(json.dumps(daten))
    assert importieren(mathematik_datei, fach="mathematik").fehler
    assert not Kompetenzerwartung.objects.filter(fach="mathematik").exists()


def test_fachfremde_verweise_werden_abgelehnt(dokument, mathematik_datei):
    assert not importieren(mathematik_datei, fach="mathematik").fehler
    bericht = pruefen(
        dokument,
        Rohsatz(
            kennung="V-3-90",
            eintragstyp="vorhaben",
            titel="Falsches Fach",
            verweise={"kompetenzen_schwerpunkt": ["M-ZA1.01S"]},
        ),
    )
    assert not bericht.ok


def test_arbeitsplan_fuer_mathematik(client, admin_nutzer, mathematik_datei):
    client.force_login(admin_nutzer)
    typ = Dokumenttyp.objects.get(schluessel="arbeitsplan")
    antwort = client.post(
        reverse("kern:dokument_neu"),
        {
            "titel": "Arbeitsplan Mathematik",
            "schluessel": "arbeitsplan-mathematik",
            "dokumenttyp": typ.pk,
            "fach": "mathematik",
        },
    )
    assert antwort.status_code == 302
    dok = Dokument.objects.get(schluessel="arbeitsplan-mathematik")
    assert dok.fach == "mathematik" and dok.ist_arbeitsplan
    antwort = client.get(reverse("kern:eintrag_neu", args=[dok.schluessel, "vorhaben"]))
    assert 'name="fach" value="mathematik"' in antwort.content.decode()
    assert "Testbereich Zahlen" in antwort.content.decode()


def test_oidc_unicode_state_wird_abgewiesen(client, oidc_provider):
    oidc_start(client, oidc_provider)
    assert (
        client.get(reverse("kern:oidc_callback"), {"state": "ungültig", "code": "x"}).status_code
        == 403
    )
    assert not oidc_provider["token_anfragen"]


def test_arbeitsplan_fuer_ein_zweites_fach_anlegen(client, admin_nutzer, lehrplanverzeichnis):
    """Abnahme aus PHASE4.md: „Arbeitsplan Mathematik anlegen“.

    Der Dokumenttyp „Arbeitsplan“ ist fachoffen. Nach dem Anlegen muss die
    Kompetenzauswahl die Erwartungen des gewählten Fachs anbieten – und keine
    aus einem anderen.
    """
    from fachdaten import lehrplan

    for fach, pfad in lehrplan.vorhandene_dateien():
        assert not importieren(pfad, fach=fach).fehler
    client.force_login(admin_nutzer)

    antwort = client.post(
        reverse("kern:dokument_neu"),
        {
            "titel": "Arbeitsplan Mathematik",
            "schluessel": "arbeitsplan-mathematik",
            "dokumenttyp": Dokumenttyp.objects.get(schluessel="arbeitsplan").pk,
            "fach": "mathematik",
            "kollegiumsweit": "on",
            "gueltig_ab_schuljahr": "",
        },
    )

    assert antwort.status_code == 302, antwort.context["formular"].errors if antwort.context else ""
    dokument = Dokument.objects.get(schluessel="arbeitsplan-mathematik")
    assert dokument.fach == "mathematik"
    assert dokument.ist_arbeitsplan

    # Die Auswahl im Dokument bietet Mathematik an, nicht Deutsch.
    treffer = client.get(
        reverse("fachdaten:suche"), {"fach": "mathematik", "q": "Zahlenraum"}
    ).content.decode()
    assert 'data-kennung="MA-' in treffer
    assert 'data-kennung="SZ' not in treffer

    # Die Abdeckungsmatrix des neuen Dokuments rechnet mit Mathematik – und
    # ordnet die Bereiche wie der Lehrplan, nicht nach den Deutsch-Kürzeln.
    antwort = client.get(reverse("deutsch:abdeckung", args=[dokument.schluessel]))
    assert antwort.status_code == 200
    seite = antwort.content.decode()
    assert "Zahlen und Operationen" in seite
    assert "Sprechen und Zuhören" not in seite

    matrix = abdeckungsmatrix(dokument, fach="mathematik")
    assert [zeile.bereich for zeile in matrix.schwerpunkte][:6] == [
        "PL",
        "MO",
        "KO",
        "AR",
        "DA",
        "ZO",
    ]
    assert len(matrix.zeilen) == 136
