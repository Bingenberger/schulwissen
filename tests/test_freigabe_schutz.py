"""Regressionen: freigegebene Fassungen, Auswertungen und Verwaltung."""

import json
from datetime import date

import pytest
from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from deutsch import auswertungen
from eintragstypen.dienste import Rohsatz, pruefen, speichern
from kern import beschluesse, rechte
from kern.models import Beschluss, Gremium, Nutzer, Status, Verlinkung, Zieltyp

pytestmark = pytest.mark.django_db


def schreiben(dokument, kennung, typ, titel, daten, verweise=None, status=Status.ENTWURF):
    befund = pruefen(
        dokument,
        Rohsatz(
            kennung=kennung,
            eintragstyp=typ,
            titel=titel,
            daten=daten,
            verweise=verweise or {},
            status=status,
        ),
    )
    assert befund.ok, befund.fehler
    return speichern(dokument, befund)


def freigeben(eintrag, nummer):
    gremium, _ = Gremium.objects.get_or_create(name="Prüfkonferenz")
    beschluss = Beschluss.objects.create(
        datum=date(2026, 10, 30), gremium=gremium, titel=f"Freigabe {nummer}"
    )
    beschluesse.beschluss_fassen(beschluss, [eintrag])
    return eintrag.beschlossene_version()


@pytest.fixture
def historie(dokument):
    e = schreiben(
        dokument,
        "K-90",
        "grundlagenkapitel",
        "Älterer gültiger Titel",
        {"text": "<p>Älterer gültiger Inhalt</p>"},
    )
    erste = freigeben(e, 1)
    e = schreiben(
        dokument, e.kennung, e.eintragstyp, "Gültiger Titel", {"text": "<p>Gültiger Inhalt</p>"}
    )
    zweite = freigeben(e, 2)
    e = schreiben(
        dokument,
        e.kennung,
        e.eintragstyp,
        "VERTRAULICHER ENTWURF",
        {"text": "<p>VERTRAULICHER INHALT</p>"},
    )
    return e, erste, zweite, e.letzte_version()


def test_lesende_bekommen_keine_entwuerfe_in_fassungen(client, lesend_nutzer, historie):
    e, erste, zweite, entwurf = historie
    client.force_login(lesend_nutzer)
    antwort = client.get(reverse("kern:fassungen", args=[e.dokument.schluessel, e.kennung]))
    assert antwort.status_code == 200
    assert {v.pk for v in antwort.context["versionen"]} == {erste.pk, zweite.pk}
    assert "VERTRAULICH" not in antwort.content.decode()
    url = reverse("kern:version", args=[e.dokument.schluessel, e.kennung, entwurf.versionsnummer])
    assert client.get(url).status_code == 404


def test_lesende_duerfen_freigegebene_historie_vergleichen(client, lesend_nutzer, historie):
    e, erste, zweite, _ = historie
    client.force_login(lesend_nutzer)
    url = reverse("kern:vergleich", args=[e.dokument.schluessel, e.kennung])
    antwort = client.get(url)
    assert antwort.status_code == 200
    assert antwort.context["alt"].pk == erste.pk
    assert antwort.context["neu"].pk == zweite.pk
    assert "VERTRAULICH" not in antwort.content.decode()
    assert {v.pk for v in antwort.context["versionen"]} == {erste.pk, zweite.pk}


@pytest.mark.parametrize("parameter", ["alt", "neu"])
def test_gezielte_entwurfsvergleiche_werden_abgewiesen(client, lesend_nutzer, historie, parameter):
    e, _, _, entwurf = historie
    client.force_login(lesend_nutzer)
    url = reverse("kern:vergleich", args=[e.dokument.schluessel, e.kennung])
    assert client.get(url, {parameter: entwurf.versionsnummer}).status_code == 404


def test_aenderungsuebersicht_ist_fuer_lesende_gesperrt(client, lesend_nutzer, historie):
    e = historie[0]
    client.force_login(lesend_nutzer)
    assert client.get(reverse("kern:aenderungen", args=[e.dokument.schluessel])).status_code == 403
    antwort = client.get(reverse("kern:dokument", args=[e.dokument.schluessel]))
    assert "Änderungen seit Beschluss" not in antwort.content.decode()


def test_lehrkraft_sieht_weiter_arbeitsstand(client, lehrkraft, historie):
    e, _, _, entwurf = historie
    client.force_login(lehrkraft)
    assert (
        client.get(
            reverse("kern:version", args=[e.dokument.schluessel, e.kennung, entwurf.versionsnummer])
        ).status_code
        == 200
    )
    antwort = client.get(reverse("kern:vergleich", args=[e.dokument.schluessel, e.kennung]))
    assert antwort.context["neu"].pk == entwurf.pk
    assert "VERTRAULICH" in antwort.content.decode()


def test_arbeitsgruppe_allein_gibt_keine_entwurfsrechte(db):
    nutzer = Nutzer.objects.create_user(email="ohne-rolle@example.org", anzeigename="Ohne Rolle")
    nutzer.groups.add(Group.objects.create(name="Nur eine Arbeitsgruppe"))
    assert rechte.ist_nur_lesend(nutzer)
    assert not rechte.darf_arbeitsstand_lesen(nutzer)


@pytest.fixture
def fachstaende(dokument, kompetenzen):
    r = schreiben(
        dokument,
        "R-90",
        "ritual",
        "Gültiges Ritual",
        {
            "einheiten_pro_woche": 2,
            "minuten_je_einheit": 15,
            "auspraegung_jg3": "<p>Gültige Ausprägung</p>",
            "leistung_bereich": "Sonstige Leistungen",
            "leistung_feststellung": "<p>Gültige Beobachtung</p>",
        },
        {"kompetenzen_schwerpunkt": ["LE1.03S", "LE1.03K"]},
    )
    freigeben(r, 1)
    v = schreiben(
        dokument,
        "V-3-90",
        "vorhaben",
        "Gültiges Vorhaben",
        {
            "jahrgang": 3,
            "quartal": "Q1",
            "zeitumfang_std": 12,
            "klassenarbeit": True,
            "leistung_bereich": "Schriftliche Arbeiten",
            "leistung_form": "<p>Gültige Prüfung</p>",
        },
        {"kompetenzen_schwerpunkt": ["SC2.02D"]},
    )
    freigeben(v, 2)
    r = schreiben(
        dokument,
        r.kennung,
        r.eintragstyp,
        "GEHEIMES RITUAL",
        {
            "einheiten_pro_woche": 5,
            "minuten_je_einheit": 45,
            "auspraegung_jg3": "<p>GEHEIME AUSPRÄGUNG</p>",
        },
        {"kompetenzen_schwerpunkt": ["SZ1.01D"]},
    )
    v = schreiben(
        dokument,
        v.kennung,
        v.eintragstyp,
        "GEHEIMES VORHABEN",
        {
            "jahrgang": 4,
            "quartal": "Q4",
            "zeitumfang_std": 99,
            "leistung_bereich": "formativ (ohne Bewertung)",
        },
        {"kompetenzen_schwerpunkt": ["SZ1.01D"]},
    )
    schreiben(dokument, "V-3-91", "vorhaben", "NIE FREIGEGEBEN", {"jahrgang": 3, "quartal": "Q2"})
    return dokument, r, v


def test_abdeckung_verwendet_gueltige_verweise(fachstaende):
    d, _, _ = fachstaende
    matrix = auswertungen.abdeckungsmatrix(d, nur_beschlossene=True)
    assert matrix.zeile("SC2.02D").abdeckung == "schwerpunkt"
    assert matrix.zeile("SZ1.01D").abdeckung == "fehlt"
    assert matrix.zeile("SC2.02D").als_schwerpunkt[0].titel == "Gültiges Vorhaben"
    arbeitsstand = auswertungen.abdeckungsmatrix(d)
    assert arbeitsstand.zeile("SC2.02D").abdeckung == "fehlt"
    assert arbeitsstand.zeile("SZ1.01D").abdeckung == "schwerpunkt"


def test_fahrplan_verwendet_gueltigen_jahrgang_und_quartal(fachstaende):
    d, _, _ = fachstaende
    plan = auswertungen.fahrplan(d, 3, nur_beschlossene=True)
    assert plan.stunden_gesamt == 12
    assert [v.titel for v in plan.quartale[0].vorhaben] == ["Gültiges Vorhaben"]
    assert plan.rituale[0]["auspraegung"] == "<p>Gültige Ausprägung</p>"
    assert not auswertungen.fahrplan(d, 4, nur_beschlossene=True).anzahl_vorhaben


def test_ritualprogression_und_zeitbudget_verwenden_gueltigen_inhalt(fachstaende):
    d, _, _ = fachstaende
    assert auswertungen.zeitbudget(d, nur_beschlossene=True).minuten_durch_rituale == 30
    assert auswertungen.zeitbudget(d).minuten_durch_rituale == 225
    progression = auswertungen.ritualprogressionen(d, nur_beschlossene=True)[0]
    assert progression.ritual.titel == "Gültiges Ritual"
    assert progression.spalten[2].auspraegung == "<p>Gültige Ausprägung</p>"


def test_leistung_und_progressionspaare_beruecksichtigen_gueltige_fassungen(fachstaende):
    d, _, _ = fachstaende
    leistung = auswertungen.leistungsuebersicht(d, nur_beschlossene=True)
    assert leistung.jahrgaenge[2].klassenarbeiten == 1
    assert leistung.jahrgaenge[2].zeilen[0].form == "<p>Gültige Prüfung</p>"
    assert not leistung.jahrgaenge[3].zeilen
    paar = next(
        p for p in auswertungen.progressionspaare(d, nur_beschlossene=True) if p.sep.pk == "LE1.03S"
    )
    assert paar.beide_abgedeckt


@pytest.mark.parametrize(
    "ansicht",
    ["abdeckung", "fahrplan", "ritualprogression", "zeitbudget", "leistung", "progressionspaare"],
)
@pytest.mark.parametrize("stand", ["", "entwurf"])
def test_lesende_sehen_in_auswertungen_nur_gueltiges(
    client, lesend_nutzer, fachstaende, ansicht, stand
):
    d, _, _ = fachstaende
    client.force_login(lesend_nutzer)
    args = [d.schluessel, 3] if ansicht == "fahrplan" else [d.schluessel]
    antwort = client.get(reverse("deutsch:" + ansicht, args=args), {"stand": stand})
    assert antwort.status_code == 200
    assert antwort.context["nur_beschlossene"]
    text = antwort.content.decode()
    assert "GEHEIM" not in text
    assert "NIE FREIGEGEBEN" not in text


def admin_daten(eintrag=None):
    return {
        "titel": "Änderung aus der Verwaltung",
        "status": Status.ENTWURF,
        "daten": json.dumps({"text": "<p>Neue Fassung</p><script>boese()</script>"}),
        "position": 10,
        "verlinkungen-TOTAL_FORMS": "0",
        "verlinkungen-INITIAL_FORMS": "0",
    }


def test_verwaltung_nutzt_pruefung_suchindex_und_fassungen(client, admin_nutzer, historie):
    e, _, gueltig, _ = historie
    client.force_login(admin_nutzer)
    vorher = e.versionen.count()
    antwort = client.post(reverse("admin:kern_eintrag_change", args=[e.pk]), admin_daten(e))
    assert antwort.status_code == 302
    e.refresh_from_db()
    assert e.status == Status.ENTWURF
    assert e.versionen.count() == vorher + 1
    assert e.letzte_version().autor == admin_nutzer
    assert "<script" not in e.daten["text"]
    assert "Neue Fassung" in e.suchtext
    gueltig.refresh_from_db()
    assert gueltig.titel == "Gültiger Titel"
    assert gueltig.daten["text"] == "<p>Gültiger Inhalt</p>"


def test_verwaltung_legt_geprueften_eintrag_mit_fassung_an(client, admin_nutzer, dokument):
    client.force_login(admin_nutzer)
    daten = {
        **admin_daten(),
        "dokument": dokument.pk,
        "kennung": "K-92",
        "eintragstyp": "grundlagenkapitel",
    }
    antwort = client.post(reverse("admin:kern_eintrag_add"), daten)
    assert antwort.status_code == 302
    e = dokument.eintraege.get(kennung="K-92")
    assert e.versionen.count() == 1
    assert e.erstellt_von == admin_nutzer


@pytest.mark.parametrize(
    "aenderung",
    [
        {"status": Status.BESCHLOSSEN},
        {"status": Status.ARCHIVIERT},
        {"status": Status.ABGESTIMMT, "daten": "{}"},
        {"daten": '{"unbekannt": "kein Schemafeld"}'},
        {"daten": '["kein Objekt"]'},
    ],
)
def test_verwaltung_verhindert_ungepruefte_aenderungen(client, admin_nutzer, dokument, aenderung):
    e = schreiben(dokument, "V-3-92", "vorhaben", "Unfertig", {"jahrgang": 3})
    client.force_login(admin_nutzer)
    daten = {**admin_daten(), "daten": '{"jahrgang": 3}', **aenderung}
    vorher = e.versionen.count()
    antwort = client.post(reverse("admin:kern_eintrag_change", args=[e.pk]), daten)
    assert antwort.status_code == 200
    assert antwort.context["adminform"].form.errors
    e.refresh_from_db()
    assert e.titel == "Unfertig"
    assert e.versionen.count() == vorher


def test_verwaltung_bearbeitung_eines_beschlossenen_eintrags_erzeugt_entwurf(
    client, admin_nutzer, historie
):
    e, _, gueltig, _ = historie
    # Einen bereits freigegebenen Arbeitsstand im Admin öffnen.
    gueltig = freigeben(e, 3)
    client.force_login(admin_nutzer)
    vorher = e.versionen.count()
    daten = {**admin_daten(), "status": Status.BESCHLOSSEN}
    assert client.post(reverse("admin:kern_eintrag_change", args=[e.pk]), daten).status_code == 302
    e.refresh_from_db()
    assert e.status == Status.ENTWURF
    assert e.versionen.count() == vorher + 1
    gueltig.refresh_from_db()
    assert gueltig.status == Status.BESCHLOSSEN
    assert gueltig.titel == "VERTRAULICHER ENTWURF"


@pytest.mark.parametrize("ziel", ["eintragsversion", "beschluss", "verlinkung"])
def test_verwaltung_sperrt_direkte_historien_und_verweisaenderungen(
    client, admin_nutzer, historie, ziel
):
    e, _, gueltig, _ = historie
    obj = gueltig if ziel == "eintragsversion" else gueltig.beschluss
    if ziel == "verlinkung":
        obj = Verlinkung.objects.create(
            von_eintrag=e, ziel_typ=Zieltyp.EINTRAG, ziel_id=str(e.pk), art="verweist_auf"
        )
    client.force_login(admin_nutzer)
    url = reverse("admin:kern_" + ziel + "_change", args=[obj.pk])
    assert client.get(url).status_code == 200
    assert client.post(url, {"titel": "Manipuliert", "status": Status.ENTWURF}).status_code == 403
    assert (
        client.post(
            reverse("admin:kern_" + ziel + "_delete", args=[obj.pk]), {"post": "yes"}
        ).status_code
        == 403
    )


def test_verwaltung_metadaten_bleiben_bearbeitbar(client, admin_nutzer, arbeitsgruppe, historie):
    e = historie[0]
    client.force_login(admin_nutzer)
    daten = {
        **admin_daten(),
        "verantwortlich_gruppe": arbeitsgruppe.pk,
        "eltern": e.dokument.eintraege.get(kennung="2").pk,
        "position": 70,
    }
    assert client.post(reverse("admin:kern_eintrag_change", args=[e.pk]), daten).status_code == 302
    e.refresh_from_db()
    assert e.verantwortlich_gruppe == arbeitsgruppe
    assert e.eltern.kennung == "2" and e.position == 70


def test_lesende_mit_verwaltungsrechten_sehen_keine_rohdaten(client, lesend_nutzer, historie):
    e = historie[0]
    lesend_nutzer.is_staff = True
    lesend_nutzer.save()
    lesend_nutzer.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="kern", codename__in=["view_eintrag", "change_eintrag"]
        )
    )
    client.force_login(lesend_nutzer)
    assert client.get(reverse("admin:kern_eintrag_change", args=[e.pk])).status_code == 403


def test_verwaltung_kann_optionale_metadaten_leeren(client, admin_nutzer, historie):
    e = historie[0]
    e.verantwortlich_text = "Bisher zuständig"
    e.fassung_stand = date(2026, 1, 1)
    e.save()
    client.force_login(admin_nutzer)
    daten = {**admin_daten(), "verantwortlich_text": "", "fassung_stand": ""}
    assert client.post(reverse("admin:kern_eintrag_change", args=[e.pk]), daten).status_code == 302
    e.refresh_from_db()
    assert e.verantwortlich_text == ""
    assert e.fassung_stand is None
