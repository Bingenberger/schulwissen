"""AP02: Dokument-/Bereichsgrenzen durchgängig und unabhängig von Arbeitsgruppen."""

from datetime import date

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse

from eintragstypen.dienste import Rohsatz, pruefen, speichern
from kern import beschluesse, rechte
from kern.models import (
    Anhang,
    Beschluss,
    Dokument,
    Gremium,
    Status,
    Wissensbereich,
    Zugangsregel,
)
from kern.staende import sichtbare_anhaenge
from suche import dienste

pytestmark = pytest.mark.django_db


def schreiben(dokument, kennung="K-01", titel="Xylophonfundus", **kwargs):
    return speichern(
        dokument,
        pruefen(
            dokument,
            Rohsatz(
                kennung=kennung,
                eintragstyp="grundlagenkapitel",
                titel=titel,
                daten={"text": "Xylophonfundus"},
            ),
        ),
        **kwargs,
    )


def freigeben(*eintraege):
    gremium, _ = Gremium.objects.get_or_create(name="Testkonferenz")
    b = Beschluss.objects.create(
        datum=date(2026, 10, 31),
        gremium=gremium,
        titel="Xylophonbeschluss",
        text="Geschützter Beschlusstext",
    )
    beschluesse.beschluss_fassen(b, eintraege)
    return b


@pytest.fixture
def verborgen(dokument):
    d = Dokument.objects.create(
        schluessel="geschuetzt",
        titel="Xylophondokument",
        dokumenttyp=dokument.dokumenttyp,
        fach="mathematik",
        kollegiumsweit=False,
    )
    e = schreiben(d)
    freigeben(e)
    return d, e


def test_bisheriger_arbeitsplan_bleibt_lesbar(dokument, lehrkraft, lesend_nutzer):
    assert rechte.darf_dokument_lesen(lehrkraft, dokument)
    assert rechte.darf_dokument_lesen(lesend_nutzer, dokument)


@pytest.mark.parametrize("rolle", ["lehrkraft", "redaktion_nutzer", "lesend_nutzer"])
def test_geschuetztes_dokument_erscheint_in_keinem_einstieg(client, request, rolle, verborgen):
    d, e = verborgen
    u = request.getfixturevalue(rolle)
    client.force_login(u)
    for url in [
        reverse("kern:startseite"),
        reverse("kern:dokumente"),
        reverse("suche:suchen") + "?q=Xylophonfundus",
        reverse("suche:vorschlaege") + "?q=Xylophonfundus",
        reverse("kern:beschluesse"),
    ]:
        antwort = client.get(url)
        assert antwort.status_code == 200
        assert "Xylophondokument" not in antwort.content.decode()
        assert "Xylophonbeschluss" not in antwort.content.decode()
        assert "Xylophonfundus" not in antwort.content.decode() if "q=" not in url else True
    assert dienste.suchen(u, "Xylophonfundus", gruppe="eintraege").gesamt == 0
    assert dienste.vorschlaege(u, "Xylophonfundus") == []
    assert not rechte.darf_lesen(u, e)


@pytest.mark.parametrize(
    "ansicht",
    [
        "kern:dokument",
        "kern:eintrag",
        "kern:fassungen",
        "kern:vergleich",
        "kern:eintrag_bearbeiten",
        "kern:anhang_hochladen",
        "kern:nextcloud_waehlen",
        "kern:nextcloud_verlinken",
        "kern:aenderungen",
        "deutsch:abdeckung",
        "deutsch:zeitbudget",
        "deutsch:leistung",
        "deutsch:ritualprogression",
        "deutsch:progressionspaare",
    ],
)
def test_direkte_wege_zeigen_keine_geschuetzten_inhalte(client, lehrkraft, verborgen, ansicht):
    d, e = verborgen
    client.force_login(lehrkraft)
    args = (
        [d.schluessel]
        if ansicht in ["kern:dokument", "kern:aenderungen"] or ansicht.startswith("deutsch:")
        else [d.schluessel, e.kennung]
    )
    url = reverse(ansicht, args=args)
    antwort = (
        client.post(url)
        if ansicht in ["kern:anhang_hochladen", "kern:nextcloud_verlinken"]
        else client.get(url)
    )
    assert antwort.status_code in (403, 404)
    assert "Xylophonfundus" not in antwort.content.decode()


def test_leseregel_gibt_lesenden_keine_entwurfsrechte(client, lesend_nutzer, verborgen):
    d, e = verborgen
    Zugangsregel.objects.create(dokument=d, nutzer=lesend_nutzer, lesen=True)
    schreiben(d, e.kennung, "Geheimer Arbeitsstand")
    client.force_login(lesend_nutzer)
    antwort = client.get(reverse("kern:eintrag", args=[d.schluessel, e.kennung]))
    assert antwort.status_code == 200
    assert "Xylophonfundus" in antwort.content.decode()
    assert "Geheimer Arbeitsstand" not in antwort.content.decode()
    assert not rechte.darf_bearbeiten(lesend_nutzer, e)
    assert not rechte.darf_beschliessen(lesend_nutzer, d)


def test_bereichs_und_dokumentgrenzen_gelten_unabhaengig(lehrkraft, verborgen):
    d, e = verborgen
    bereich = Wissensbereich.objects.create(
        name="Geschützter Bereich", schluessel="intern", kollegiumsweit=False
    )
    d.bereich = bereich
    d.save()
    regel = Zugangsregel.objects.create(
        dokument=d, nutzer=lehrkraft, lesen=True, bearbeiten=True, freigeben=True
    )
    assert not rechte.darf_lesen(lehrkraft, e)
    assert not rechte.darf_bearbeiten(lehrkraft, e)
    Zugangsregel.objects.create(bereich=bereich, nutzer=lehrkraft, lesen=True)
    assert rechte.darf_lesen(lehrkraft, e)
    assert rechte.darf_bearbeiten(lehrkraft, e)
    regel.lesen = False
    regel.save()
    assert not rechte.darf_lesen(lehrkraft, e)


def test_arbeitsgruppen_geben_nur_ueber_explizite_regeln_zugang(
    lehrkraft, arbeitsgruppe, verborgen
):
    d, e = verborgen
    lehrkraft.groups.add(arbeitsgruppe)
    e.verantwortlich_gruppe = arbeitsgruppe
    e.erstellt_von = lehrkraft
    e.status = Status.ENTWURF
    e.save()
    assert not rechte.darf_lesen(lehrkraft, e)
    assert not rechte.darf_bearbeiten(lehrkraft, e)
    Zugangsregel.objects.create(dokument=d, gruppe=arbeitsgruppe, lesen=True)
    assert rechte.darf_bearbeiten(lehrkraft, e)
    lehrkraft.groups.remove(arbeitsgruppe)
    assert not rechte.darf_lesen(lehrkraft, e)


def test_redaktion_bearbeitet_nur_zugewiesene_dokumente(client, redaktion_nutzer, dokument):
    deutsch = schreiben(dokument)
    fremd = Dokument.objects.create(
        schluessel="mathe", titel="Mathematik", fach="mathematik", dokumenttyp=dokument.dokumenttyp
    )
    mathe = schreiben(fremd)
    assert rechte.darf_bearbeiten(redaktion_nutzer, deutsch)
    assert not rechte.darf_bearbeiten(redaktion_nutzer, mathe)
    assert not rechte.darf_status_setzen(redaktion_nutzer, mathe, Status.ABGESTIMMT)
    client.force_login(redaktion_nutzer)
    assert (
        client.get(
            reverse("kern:eintrag_bearbeiten", args=[fremd.schluessel, mathe.kennung])
        ).status_code
        == 403
    )
    assert (
        client.post(
            reverse("kern:eintrag_bearbeiten", args=[fremd.schluessel, mathe.kennung]),
            {"titel": "Übernahme"},
        ).status_code
        == 403
    )
    assert not rechte.darf_beschliessen(redaktion_nutzer, dokument)


def test_bereichsredaktion_und_freigabe_sind_getrennt(lehrkraft, dokument):
    bereich = Wissensbereich.objects.create(name="Deutsch", schluessel="deutsch")
    dokument.bereich = bereich
    dokument.save()
    e = schreiben(dokument)
    regel = Zugangsregel.objects.create(bereich=bereich, nutzer=lehrkraft, bearbeiten=True)
    assert rechte.darf_bearbeiten(lehrkraft, e)
    assert rechte.darf_status_setzen(lehrkraft, e, Status.ABGESTIMMT)
    assert not rechte.darf_beschliessen(lehrkraft, dokument)
    regel.bearbeiten = False
    regel.freigeben = True
    regel.save()
    assert not rechte.darf_bearbeiten(lehrkraft, e)
    assert rechte.darf_beschliessen(lehrkraft, dokument)


def test_freigabepruefung_erfolgt_auch_im_gemeinsamen_dienst(lehrkraft, dokument, verborgen):
    d, e = verborgen
    b = Beschluss.objects.create(
        datum=date(2026, 10, 31), gremium=Gremium.objects.first(), titel="Neue Freigabe"
    )
    Zugangsregel.objects.create(dokument=dokument, nutzer=lehrkraft, freigeben=True)
    with pytest.raises(PermissionDenied):
        beschluesse.beschluss_fassen(b, [e], nutzer=lehrkraft)
    assert b.dokumente.count() == 0


def test_freigabeauswahl_verweigert_fremde_ids(client, lehrkraft, dokument, verborgen):
    d, e = verborgen
    Zugangsregel.objects.create(dokument=dokument, nutzer=lehrkraft, freigeben=True)
    client.force_login(lehrkraft)
    assert client.get(reverse("kern:beschluss_anlegen"), {"eintrag": e.pk}).status_code == 403
    assert (
        client.post(
            reverse("kern:beschluss_anlegen"), {"eintrag": e.pk, "speichern": "1"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("eintragsbezug", [True, False])
def test_dateien_werden_auch_fuer_lehrkraefte_geschuetzt(
    client, settings, tmp_path, lehrkraft, verborgen, eintragsbezug
):
    settings.MEDIA_ROOT = tmp_path
    d, e = verborgen
    a = Anhang.objects.create(
        dokument=d,
        eintrag=e if eintragsbezug else None,
        dateiname="Xylophondatei.txt",
        extrahierter_text="Geheimer Dateitext",
        datei=SimpleUploadedFile("geschuetzt.txt", b"Geheimer Dateitext"),
    )
    client.force_login(lehrkraft)
    assert client.get(a.datei.url).status_code == 404
    assert dienste.suchen(lehrkraft, "Geheimer Dateitext", gruppe="dateien").gesamt == 0
    assert not sichtbare_anhaenge(lehrkraft, Anhang.objects.filter(pk=a.pk)).exists()
    Zugangsregel.objects.create(dokument=d, nutzer=lehrkraft, lesen=True)
    assert client.get(a.datei.url).status_code == 200
    assert dienste.suchen(lehrkraft, "Geheimer Dateitext", gruppe="dateien").gesamt == 1
    client.logout()
    assert client.get(a.datei.url).status_code == 302


def test_beschluesse_ueber_mehrere_dokumente_sind_nicht_teilweise_sichtbar(
    client, lehrkraft, dokument, verborgen
):
    d, e = verborgen
    offen = schreiben(dokument, "K-98", "Offene Quelle")
    b = freigeben(offen, e)
    client.force_login(lehrkraft)
    assert client.get(reverse("kern:beschluss", args=[b.pk])).status_code == 404
    assert dienste.suchen(lehrkraft, "Xylophonbeschluss", gruppe="beschluesse").gesamt == 0
    for url in [
        reverse("kern:eintrag", args=[dokument.schluessel, offen.kennung]),
        reverse("kern:fassungen", args=[dokument.schluessel, offen.kennung]),
        reverse(
            "kern:version",
            args=[dokument.schluessel, offen.kennung, offen.beschlossene_version().versionsnummer],
        ),
    ]:
        r = client.get(url)
        assert r.status_code == 200
        assert "Xylophonbeschluss" not in r.content.decode()
    beschluesse.beschluss_zuruecknehmen(b)
    assert client.get(reverse("kern:beschluss", args=[b.pk])).status_code == 404
    assert set(b.dokumente.values_list("pk", flat=True)) == {d.pk, dokument.pk}


def test_leseregel_widerruf_wirkt_sofort_auch_fuer_eigene_entwuerfe(client, lehrkraft, verborgen):
    d, e = verborgen
    schreiben(d, "K-02", "Mein geschützter Entwurf", nutzer=lehrkraft)
    regel = Zugangsregel.objects.create(dokument=d, nutzer=lehrkraft, lesen=True)
    client.force_login(lehrkraft)
    assert (
        "Mein geschützter Entwurf" in client.get(reverse("kern:eigene_entwuerfe")).content.decode()
    )
    regel.delete()
    assert (
        "Mein geschützter Entwurf"
        not in client.get(reverse("kern:eigene_entwuerfe")).content.decode()
    )


def test_planung_verraet_und_aendert_keine_geschuetzten_plaene(client, lehrkraft, verborgen):
    d, e = verborgen
    client.force_login(lehrkraft)
    r = client.get(reverse("kern:planung"))
    assert "Xylophondokument" not in r.content.decode()
    r = client.post(
        reverse("kern:planung"),
        {
            "dokument": d.schluessel,
            "klasse": "3b",
            "jahrgang": 3,
            "schuljahr": "2026/27",
            "eintrag": e.pk,
            "erledigt": "on",
        },
    )
    assert not e.fortschritt.exists()
    assert "Xylophonfundus" not in r.content.decode()


@pytest.mark.parametrize(
    "modell",
    [
        "dokument",
        "zugangsregel",
        "wissensbereich",
        "anhang",
        "eintrag",
        "eintragsversion",
        "beschluss",
        "kommentar",
        "verlinkung",
        "nutzer",
        "group",
    ],
)
def test_staff_und_django_rechte_umgehen_keine_zugaenge(client, lehrkraft, modell, verborgen):
    lehrkraft.is_staff = True
    lehrkraft.save()
    lehrkraft.user_permissions.add(*Permission.objects.all())
    client.force_login(lehrkraft)
    app = "auth" if modell == "group" else "kern"
    r = client.get(reverse(f"admin:{app}_{modell}_changelist"))
    assert r.status_code == 403
    assert "Xylophon" not in r.content.decode()


def test_regeln_muessen_ziel_und_empfaenger_eindeutig_benennen(dokument, lehrkraft):
    with pytest.raises(ValidationError):
        Zugangsregel(dokument=dokument, nutzer=lehrkraft).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        Zugangsregel.objects.create(
            dokument=dokument,
            nutzer=lehrkraft,
            gruppe=Group.objects.create(name="Team"),
            lesen=True,
        )


def test_administration_behaelt_zugang(admin_nutzer, verborgen):
    d, e = verborgen
    assert rechte.darf_dokument_lesen(admin_nutzer, d)
    assert rechte.darf_bearbeiten(admin_nutzer, e)
    assert rechte.darf_beschliessen(admin_nutzer, d)


def test_freigabe_ohne_bearbeitungsrecht_hat_einen_vollstaendigen_workflow(
    client, lehrkraft, dokument
):
    e = schreiben(dokument)
    Zugangsregel.objects.create(dokument=dokument, nutzer=lehrkraft, freigeben=True)
    client.force_login(lehrkraft)
    assert client.get(reverse("kern:beschlussvorlage")).status_code == 200
    g = Gremium.objects.create(name="Fachkonferenz")
    r = client.post(
        reverse("kern:beschluss_anlegen"),
        {
            "eintrag": e.pk,
            "speichern": "1",
            "datum": "2026-10-31",
            "gremium": g.pk,
            "titel": "Fachliche Freigabe",
        },
    )
    assert r.status_code == 302
    e.refresh_from_db()
    assert e.status == Status.BESCHLOSSEN
    assert not rechte.darf_bearbeiten(lehrkraft, e)
    b = e.beschlossene_version().beschluss
    assert client.post(reverse("kern:beschluss_zuruecknehmen", args=[b.pk])).status_code == 302


def test_bestandsmigration_behaelt_personenzuordnungen_ohne_globale_neuvergabe(
    dokument, redaktion_nutzer, rollen
):
    from importlib import import_module
    from types import SimpleNamespace

    from django.apps import apps
    from django.db import connection

    from kern.models import Nutzer

    d = Dokument.objects.create(
        schluessel="bestand",
        titel="Bestehendes Konzept",
        dokumenttyp=dokument.dokumenttyp,
        fach="mathematik",
    )
    e = schreiben(d)
    b = freigeben(e)
    b.dokumente.clear()
    import_module(
        "kern.migrations.0009_wissensbereich_beschluss_dokumente_and_more"
    ).bestand_zuordnen(apps, SimpleNamespace(connection=connection))
    d.refresh_from_db()
    assert d.kollegiumsweit
    assert d.bereich.schluessel == "fach-mathematik"
    assert rechte.darf_bearbeiten(redaktion_nutzer, e)
    assert not rechte.darf_beschliessen(redaktion_nutzer, d)
    neu = Nutzer.objects.create_user(
        email="neu-redaktion@example.org", anzeigename="Neue Redaktion"
    )
    neu.groups.add(rollen["Redaktion"])
    assert not rechte.darf_bearbeiten(neu, e)
    assert list(b.dokumente.all()) == [d]


def test_stammdatenredaktion_bleibt_auf_ihr_fach_begrenzt(
    client, redaktion_nutzer, dokument, kompetenzen
):
    from fachdaten.models import Kompetenzerwartung

    redaktion_nutzer.is_staff = True
    redaktion_nutzer.save()
    redaktion_nutzer.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="fachdaten")
    )
    fremd = Kompetenzerwartung.objects.create(
        id="MA-TEST",
        fach="mathematik",
        bereich="MA",
        bereich_name="Mathematik",
        schwerpunkt="Test",
        schwerpunkt_nr=1,
        stufe="S",
        text="Mathematische Erwartung",
    )
    client.force_login(redaktion_nutzer)
    assert rechte.darf_schulische_festlegung_bearbeiten(redaktion_nutzer, "deutsch")
    assert not rechte.darf_schulische_festlegung_bearbeiten(redaktion_nutzer, "mathematik")
    r = client.get(reverse("admin:fachdaten_kompetenzerwartung_changelist"))
    assert r.status_code == 200
    assert "MA-TEST" not in r.content.decode()
    r = client.get(reverse("admin:fachdaten_kompetenzerwartung_change", args=[fremd.pk]))
    assert r.status_code in (302, 403, 404)
    client.post(
        reverse("admin:fachdaten_kompetenzerwartung_change", args=[fremd.pk]),
        {"schulische_festlegung": "Übernommen"},
    )
    fremd.refresh_from_db()
    assert fremd.schulische_festlegung == ""
