"""AP04: aktuelle Kontakte, getrennte Rechte und unverlierbare Besetzungshistorie."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.urls import reverse
from django.utils import timezone

from kern import funktionen, rechte
from kern.models import (
    Besetzungsart,
    Besetzungsmodus,
    Funktionsbereich,
    Funktionsbesetzung,
    Funktionsstand,
    Schulfunktion,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def funktion():
    return Schulfunktion.objects.create(name="Testfunktion", schluessel="testfunktion")


def besetzen(funktion, person, **kwargs):
    return Funktionsbesetzung.objects.create(funktion=funktion, person=person, **kwargs)


def ids(auskunft):
    return {b.person_id for b in auskunft.zustaendige}


def test_mehrere_funktionen_ohne_zusaetzliche_rechte(funktion, lehrkraft, arbeitsgruppe):
    lehrkraft.groups.add(arbeitsgruppe)
    gruppen = set(lehrkraft.groups.values_list("pk", flat=True))
    zweite = Schulfunktion.objects.create(name="Zweite Funktion", schluessel="zweite")
    besetzen(funktion, lehrkraft)
    besetzen(zweite, lehrkraft)
    lehrkraft.refresh_from_db()
    assert ids(funktionen.aufloesen(funktion.pk)) == {lehrkraft.pk}
    assert ids(funktionen.aufloesen(zweite.pk)) == {lehrkraft.pk}
    assert set(lehrkraft.groups.values_list("pk", flat=True)) == gruppen
    assert not lehrkraft.is_staff and not lehrkraft.is_superuser
    assert not rechte.ist_administration(lehrkraft)
    assert not lehrkraft.user_permissions.exists()


@pytest.mark.parametrize("versatz", [0, 1, 10])
def test_einzelbesetzung_verhindert_ueberlappung(funktion, lehrkraft, andere_lehrkraft, versatz):
    heute = timezone.localdate()
    besetzen(funktion, lehrkraft, gueltig_ab=heute, gueltig_bis=heute + timedelta(days=10))
    with pytest.raises(ValidationError, match="überlappende"):
        besetzen(funktion, andere_lehrkraft, gueltig_ab=heute + timedelta(days=versatz))
    neu = besetzen(funktion, andere_lehrkraft, gueltig_ab=heute + timedelta(days=11))
    assert ids(funktionen.aufloesen(funktion, stichtag=neu.gueltig_ab)) == {andere_lehrkraft.pk}


def test_getrennte_bereiche_ohne_stillschweigenden_rueckfall(funktion, lehrkraft, andere_lehrkraft):
    bereich = Funktionsbereich.objects.create(name="Test Jahrgang 1", schluessel="jg1")
    leer = Funktionsbereich.objects.create(name="Test Jahrgang 2", schluessel="jg2")
    besetzen(funktion, lehrkraft)
    besetzen(funktion, andere_lehrkraft, bereich=bereich)
    assert ids(funktionen.aufloesen(funktion, bereich=bereich)) == {andere_lehrkraft.pk}
    assert ids(funktionen.aufloesen(funktion)) == {lehrkraft.pk}
    assert funktionen.aufloesen(funktion, bereich=leer).status == "unbesetzt"
    assert len(funktionen.auskuenfte(funktion)) == 2
    bereich.name = "Andere Bedeutung"
    with pytest.raises(ValidationError):
        bereich.save()


def test_hinterlegte_vertretung_uebernimmt_nur_bewusst(funktion, lehrkraft, andere_lehrkraft):
    besetzen(funktion, lehrkraft)
    v = besetzen(funktion, andere_lehrkraft, art=Besetzungsart.VERTRETUNG)
    auskunft = funktionen.aufloesen(funktion)
    assert ids(auskunft) == {lehrkraft.pk}
    assert auskunft.vertretungen == (v,)
    v.storniert = True
    v.save()
    heute = timezone.localdate()
    besetzen(
        funktion,
        andere_lehrkraft,
        art=Besetzungsart.VERTRETUNG,
        vertretung_aktiv=True,
        gueltig_bis=heute,
    )
    assert ids(funktionen.aufloesen(funktion)) == {andere_lehrkraft.pk}
    assert funktionen.aufloesen(funktion).status == "vertretung"
    assert ids(funktionen.aufloesen(funktion, stichtag=heute + timedelta(days=1))) == {lehrkraft.pk}


def test_team_zeigt_alle_und_verhindert_doppelbesetzung(funktion, lehrkraft, andere_lehrkraft):
    funktion.besetzungsmodus = Besetzungsmodus.TEAM
    funktion.save()
    besetzen(funktion, lehrkraft)
    besetzen(funktion, andere_lehrkraft)
    assert ids(funktionen.aufloesen(funktion)) == {lehrkraft.pk, andere_lehrkraft.pk}
    with pytest.raises(ValidationError):
        besetzen(funktion, lehrkraft)
    besetzen(funktion, lehrkraft, art=Besetzungsart.VERTRETUNG, vertretung_aktiv=True)
    assert len(funktionen.aufloesen(funktion).zustaendige) == 2


@pytest.mark.parametrize("zustand", ["kuenftig", "abgelaufen", "storniert", "inaktiv"])
def test_nicht_aktuelle_personen_sind_keine_kontakte(funktion, lehrkraft, zustand):
    heute = timezone.localdate()
    daten = {
        "kuenftig": {"gueltig_ab": heute + timedelta(days=1)},
        "abgelaufen": {
            "gueltig_ab": heute - timedelta(days=5),
            "gueltig_bis": heute - timedelta(days=1),
        },
        "storniert": {"storniert": True},
        "inaktiv": {},
    }[zustand]
    b = besetzen(funktion, lehrkraft, **daten)
    stand = b.staende.get().daten
    if zustand == "inaktiv":
        lehrkraft.is_active = False
        lehrkraft.save()
    auskunft = funktionen.aufloesen(funktion.pk)
    assert not auskunft.zustaendige
    assert (
        auskunft.status
        == {
            "inaktiv": "pruefen",
            "kuenftig": "geplant",
            "abgelaufen": "abgelaufen",
            "storniert": "unbesetzt",
        }[zustand]
    )
    assert b.staende.get().daten == stand
    assert b.person_id == lehrkraft.pk


def test_archiv_und_inaktive_neubesetzung(funktion, lehrkraft):
    lehrkraft.is_active = False
    lehrkraft.save()
    with pytest.raises(ValidationError, match="aktives"):
        besetzen(funktion, lehrkraft)
    lehrkraft.is_active = True
    lehrkraft.save()
    besetzen(funktion, lehrkraft)
    funktion.archiviert = True
    funktion.save()
    assert funktionen.aufloesen(funktion.pk).status == "archiviert"
    assert not funktionen.aufloesen(funktion.pk).zustaendige
    with pytest.raises(ValidationError, match="Archivierte"):
        besetzen(funktion, lehrkraft)


def test_stabile_kennung_modus_und_identitaet(funktion, lehrkraft, andere_lehrkraft):
    b = besetzen(funktion, lehrkraft)
    funktion.schluessel = "veraendert"
    with pytest.raises(ValidationError):
        funktion.save()
    funktion.refresh_from_db()
    funktion.besetzungsmodus = Besetzungsmodus.TEAM
    with pytest.raises(ValidationError):
        funktion.save()
    b.person = andere_lehrkraft
    with pytest.raises(ValidationError):
        b.save()
    with pytest.raises(ValidationError):
        b.delete()


def test_datenregeln_auch_in_datenbank(funktion, lehrkraft):
    b = besetzen(funktion, lehrkraft)
    with pytest.raises(IntegrityError), transaction.atomic():
        Funktionsbesetzung.objects.filter(pk=b.pk).update(
            gueltig_bis=b.gueltig_ab - timedelta(days=1)
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Funktionsbesetzung.objects.filter(pk=b.pk).update(vertretung_aktiv=True)


def test_geschichte_unveraenderlich_und_konflikt_erkannt(funktion, lehrkraft, admin_nutzer):
    b = besetzen(funktion, lehrkraft)
    alt = Funktionsbesetzung.objects.get(pk=b.pk)
    b.gueltig_bis = timezone.localdate()
    b.save(autor=admin_nutzer)
    with pytest.raises(ValidationError, match="inzwischen"):
        alt.save()
    assert b.staende.count() == 2
    stand = b.staende.first()
    assert stand.autor == admin_nutzer
    with pytest.raises(ValidationError):
        stand.save()
    with pytest.raises(ValidationError):
        stand.delete()
    alte_funktion = Schulfunktion.objects.get(pk=funktion.pk)
    funktion.aufgabe = "Neue Aufgabe"
    funktion.save(autor=admin_nutzer)
    with pytest.raises(ValidationError):
        alte_funktion.save()
    assert funktion.staende.filter(besetzung__isnull=True).count() == 2


@pytest.mark.parametrize("gleicher_tag", [False, True])
def test_personalwechsel_aktualisiert_kontakte_und_erhaelt_stand(
    funktion,
    lehrkraft,
    andere_lehrkraft,
    admin_nutzer,
    gleicher_tag,
):
    heute = timezone.localdate()
    ab = heute if gleicher_tag else heute - timedelta(days=10)
    alt = besetzen(funktion, lehrkraft, gueltig_ab=ab)
    vorher = alt.staende.get().daten
    neu = funktionen.wechseln(alt, andere_lehrkraft, heute, autor=admin_nutzer)
    alt.refresh_from_db()
    assert ids(funktionen.aufloesen(funktion.pk)) == {andere_lehrkraft.pk}
    assert neu.person == andere_lehrkraft
    assert alt.storniert == gleicher_tag
    if not gleicher_tag:
        assert alt.gueltig_bis == heute - timedelta(days=1)
        assert ids(funktionen.aufloesen(funktion, stichtag=ab)) == {lehrkraft.pk}
    assert alt.staende.last().daten == vorher
    assert alt.staende.first().autor == admin_nutzer
    assert neu.staende.get().autor == admin_nutzer


@pytest.mark.parametrize("fehler", ["inaktiv", "gleich", "vorher", "nachher", "revision", "rolle"])
def test_ungueltiger_wechsel_aendert_nichts(
    funktion,
    lehrkraft,
    andere_lehrkraft,
    admin_nutzer,
    fehler,
):
    heute = timezone.localdate()
    alt = besetzen(funktion, lehrkraft, gueltig_bis=heute + timedelta(days=5))
    person = andere_lehrkraft
    ab = heute
    autor = admin_nutzer
    revision = alt.revision
    if fehler == "inaktiv":
        person.is_active = False
        person.save()
    elif fehler == "gleich":
        person = lehrkraft
    elif fehler == "vorher":
        ab = heute - timedelta(days=1)
    elif fehler == "nachher":
        ab = heute + timedelta(days=6)
    elif fehler == "revision":
        revision = 0
    elif fehler == "rolle":
        autor = lehrkraft
    with pytest.raises((ValidationError, PermissionDenied)):
        funktionen.wechseln(alt, person, ab, autor=autor, erwartete_revision=revision)
    alt.refresh_from_db()
    assert alt.revision == 1 and not alt.storniert
    assert Funktionsbesetzung.objects.count() == 1
    assert alt.staende.count() == 1


def test_wechsel_rollt_altes_ende_bei_teamkonflikt_zurueck(
    funktion,
    lehrkraft,
    andere_lehrkraft,
    admin_nutzer,
):
    funktion.besetzungsmodus = Besetzungsmodus.TEAM
    funktion.save()
    alt = besetzen(funktion, lehrkraft)
    besetzen(funktion, andere_lehrkraft)
    staende = Funktionsstand.objects.count()
    with pytest.raises(ValidationError):
        funktionen.wechseln(alt, andere_lehrkraft, timezone.localdate(), autor=admin_nutzer)
    alt.refresh_from_db()
    assert not alt.storniert and alt.gueltig_bis is None and alt.revision == 1
    assert Funktionsstand.objects.count() == staende


@pytest.mark.parametrize("modell", [Schulfunktion, Funktionsbesetzung])
def test_schreibdienst_erfordert_administration(funktion, lehrkraft, modell):
    obj = (
        funktion
        if modell == Schulfunktion
        else Funktionsbesetzung(funktion=funktion, person=lehrkraft)
    )
    with pytest.raises(PermissionDenied):
        obj.save(autor=lehrkraft)


@pytest.mark.parametrize("rolle", ["lehrkraft", "lesend_nutzer", "admin_nutzer"])
def test_verzeichnis_fuer_angemeldete_ohne_kontoemail(
    client,
    request,
    rolle,
    funktion,
    andere_lehrkraft,
):
    andere_lehrkraft.anzeigename = "Testkontakt Anna"
    andere_lehrkraft.save()
    besetzen(funktion, andere_lehrkraft)
    client.force_login(request.getfixturevalue(rolle))
    antwort = client.get(reverse("kern:funktionen"))
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert "Testkontakt Anna" in html
    assert andere_lehrkraft.email not in html
    assert ("Schulfunktion anlegen" in html) == (rolle == "admin_nutzer")
    assert client.get(reverse("kern:funktion", args=[funktion.schluessel])).status_code == 200


def test_verzeichnis_anmeldung_unbekannt_und_archiv(client, funktion, lehrkraft):
    assert client.get(reverse("kern:funktionen")).status_code == 302
    client.force_login(lehrkraft)
    assert client.get(reverse("kern:funktion", args=["unbekannt"])).status_code == 404
    funktion.archiviert = True
    funktion.save()
    assert not client.get(reverse("kern:funktionen")).context["karten"]
    antwort = client.get(reverse("kern:funktion", args=[funktion.schluessel]))
    assert "Funktion archiviert" in antwort.content.decode()


def test_suche_verraet_keine_historischen_oder_inaktiven_personen(
    client,
    funktion,
    lehrkraft,
    andere_lehrkraft,
):
    andere_lehrkraft.anzeigename = "Vergangener Testkontakt"
    andere_lehrkraft.save()
    b = besetzen(funktion, andere_lehrkraft)
    client.force_login(lehrkraft)
    url = reverse("kern:funktionen")
    assert len(client.get(url, {"q": "Vergangener"}).context["karten"]) == 1
    andere_lehrkraft.is_active = False
    andere_lehrkraft.save()
    assert not client.get(url, {"q": "Vergangener"}).context["karten"]
    andere_lehrkraft.is_active = True
    andere_lehrkraft.save()
    b.storniert = True
    b.save()
    assert not client.get(url, {"q": "Vergangener"}).context["karten"]


def test_verzeichnis_begrenzt_und_suche_behaelt_begriff(client, lehrkraft):
    for nummer in range(14):
        Schulfunktion.objects.create(name=f"Testfunktion {nummer:02}", schluessel=f"test-{nummer}")
    client.force_login(lehrkraft)
    antwort = client.get(reverse("kern:funktionen"), {"q": "Testfunktion"})
    assert len(antwort.context["karten"]) == 12
    assert "q=Testfunktion" in antwort.content.decode()
    assert len(client.get(reverse("kern:funktionen"), {"seite": "2"}).context["karten"]) == 2


@pytest.mark.parametrize(
    "modell", ["schulfunktion", "funktionsbereich", "funktionsbesetzung", "funktionsstand"]
)
def test_backend_braucht_fachliche_adminrolle(client, lehrkraft, modell):
    lehrkraft.is_staff = True
    lehrkraft.save()
    lehrkraft.user_permissions.set(Permission.objects.all())
    client.force_login(lehrkraft)
    assert client.get(reverse(f"admin:kern_{modell}_changelist")).status_code == 403


def test_backend_autocomplete_sucht_nur_aktive_konten(
    client,
    admin_nutzer,
    lehrkraft,
    andere_lehrkraft,
):
    lehrkraft.anzeigename = "Testsuchname"
    lehrkraft.kuerzel = "XYZ"
    lehrkraft.save()
    andere_lehrkraft.anzeigename = "Testsuchname"
    andere_lehrkraft.is_active = False
    andere_lehrkraft.save()
    client.force_login(admin_nutzer)
    for begriff in ["Testsuchname", "XYZ", lehrkraft.email]:
        antwort = client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "kern",
                "model_name": "funktionsbesetzung",
                "field_name": "person",
                "term": begriff,
            },
        )
        assert antwort.status_code == 200
        assert [r["id"] for r in antwort.json()["results"]] == [str(lehrkraft.pk)]


def test_backend_anlegen_und_standkonflikt(client, admin_nutzer, lehrkraft):
    client.force_login(admin_nutzer)
    daten = {"name": "Backend Test", "schluessel": "backend-test", "besetzungsmodus": "einzel"}
    antwort = client.post(reverse("admin:kern_schulfunktion_add"), daten)
    assert antwort.status_code == 302
    f = Schulfunktion.objects.get(schluessel="backend-test")
    assert f.staende.get().autor == admin_nutzer
    url = reverse("admin:kern_schulfunktion_change", args=[f.pk])
    assert client.get(url).status_code == 200
    f.aufgabe = "Bereits geänderte Aufgabe"
    f.save(autor=admin_nutzer)
    daten.update(name="Meine erhaltene Eingabe", ausgangsrevision=1)
    antwort = client.post(url, daten)
    assert antwort.status_code == 200
    assert "Deine Eingaben bleiben erhalten" in antwort.content.decode()
    assert "Meine erhaltene Eingabe" in antwort.content.decode()
    f.refresh_from_db()
    assert f.name == "Backend Test"
    daten.pop("ausgangsrevision")
    assert client.post(url, daten).status_code == 200
    daten = {
        "funktion": f.pk,
        "person": lehrkraft.pk,
        "art": "haupt",
        "gueltig_ab": timezone.localdate().isoformat(),
    }
    assert client.post(reverse("admin:kern_funktionsbesetzung_add"), daten).status_code == 302
    assert f.besetzungen.get().staende.get().autor == admin_nutzer


def test_backend_wechsel_get_schreibt_nicht_und_post_schuetzt_revision(
    client,
    admin_nutzer,
    funktion,
    lehrkraft,
    andere_lehrkraft,
):
    b = besetzen(funktion, lehrkraft)
    client.force_login(admin_nutzer)
    url = reverse("admin:kern_funktionsbesetzung_wechseln", args=[b.pk])
    assert client.get(url).status_code == 200
    assert b.staende.count() == 1
    daten = {
        "neue_person": andere_lehrkraft.pk,
        "wechsel_ab": timezone.localdate().isoformat(),
        "ausgangsrevision": 0,
    }
    antwort = client.post(url, daten)
    assert antwort.status_code == 200
    assert "inzwischen geändert" in antwort.content.decode()
    assert b.staende.count() == 1
    daten["ausgangsrevision"] = 1
    assert client.post(url, daten).status_code == 302
    assert ids(funktionen.aufloesen(funktion.pk)) == {andere_lehrkraft.pk}


@pytest.mark.django_db(transaction=True)
def test_zwei_parallele_einzelbesetzungen_werden_serialisiert(lehrkraft, andere_lehrkraft):
    f = Schulfunktion.objects.create(name="Paralleltest", schluessel="parallel")
    start = Barrier(2)

    def schreiben(person_id):
        close_old_connections()
        try:
            start.wait(timeout=10)
            try:
                Funktionsbesetzung.objects.create(funktion_id=f.pk, person_id=person_id)
                return "gespeichert"
            except ValidationError:
                return "konflikt"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ergebnisse = list(pool.map(schreiben, [lehrkraft.pk, andere_lehrkraft.pk]))
    assert sorted(ergebnisse) == ["gespeichert", "konflikt"]
    assert f.besetzungen.count() == 1


def test_widerspruechliche_rohdaten_waehlen_keine_zufaellige_person(
    funktion,
    lehrkraft,
    andere_lehrkraft,
):
    # Nur ungespeicherte Daten: Nachweis des Resolvers bei beschädigtem Importbestand.
    daten = [Funktionsbesetzung(funktion=funktion, person=p) for p in [lehrkraft, andere_lehrkraft]]
    auskunft = funktionen.aufloesen(funktion, besetzungen=daten)
    assert auskunft.status == "pruefen" and not auskunft.zustaendige


def test_teilupdate_und_kontoumbenennung_veraendern_alte_staende_nicht(
    funktion,
    lehrkraft,
    admin_nutzer,
):
    lehrkraft.anzeigename = "Ursprünglicher Testname"
    lehrkraft.save()
    b = besetzen(funktion, lehrkraft)
    lehrkraft.anzeigename = "Aktueller Testname"
    lehrkraft.save()
    assert (
        funktionen.aufloesen(funktion.pk).zustaendige[0].person.anzeigename == "Aktueller Testname"
    )
    assert b.staende.get().daten["person_anzeige"] == "Ursprünglicher Testname"
    funktion.name = "Wird nicht gespeichert"
    funktion.aufgabe = "Teiländerung"
    funktion.save(update_fields=["aufgabe"], autor=admin_nutzer)
    stand = funktion.staende.filter(besetzung__isnull=True).first()
    assert stand.daten["name"] == "Testfunktion"
    assert stand.daten["aufgabe"] == "Teiländerung"


def test_backend_besetzungskonflikt_erhaelt_eingabe(
    client,
    admin_nutzer,
    funktion,
    lehrkraft,
):
    b = besetzen(funktion, lehrkraft)
    client.force_login(admin_nutzer)
    url = reverse("admin:kern_funktionsbesetzung_change", args=[b.pk])
    b.gueltig_bis = timezone.localdate() + timedelta(days=3)
    b.save(autor=admin_nutzer)
    antwort = client.post(
        url,
        {
            "ausgangsrevision": 1,
            "gueltig_ab": b.gueltig_ab.isoformat(),
            "gueltig_bis": (b.gueltig_ab + timedelta(days=10)).isoformat(),
        },
    )
    assert antwort.status_code == 200
    assert "Deine Eingaben bleiben erhalten" in antwort.content.decode()
    b.refresh_from_db()
    assert b.gueltig_bis == timezone.localdate() + timedelta(days=3)
    assert b.staende.count() == 2
