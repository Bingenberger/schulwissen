"""Konferenzprotokolle gemeinsam genehmigen und versehentliche Einträge sicher entfernen."""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from eintragstypen import dienste
from kern.dokumenttypen import typen_sichern
from kern.models import (
    Beschluss,
    Dokument,
    Dokumenttyp,
    Eintrag,
    Gremium,
    ReservierteKennung,
    Status,
    Verlinkung,
    Zieltyp,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def protokoll(db, lehrkraft):
    typen_sichern()
    dok = Dokument.objects.create(
        titel="Konferenz vom 30.10.2026",
        schluessel="konferenz-test",
        dokumenttyp=Dokumenttyp.objects.get(schluessel="protokoll"),
    )
    for kennung, typ, titel, daten in [
        (
            "P-01",
            "protokollkopf",
            "Konferenz",
            {"datum": "2026-10-30", "gremium": "Lehrerkonferenz"},
        ),
        (
            "TOP-01",
            "tagesordnungspunkt",
            "Organisation",
            {"text": "<p>Wir stimmen die Termine ab.</p>"},
        ),
    ]:
        roh = dienste.Rohsatz(kennung=kennung, eintragstyp=typ, titel=titel, daten=daten)
        dienste.speichern(dok, dienste.pruefen(dok, roh), nutzer=lehrkraft)
    return dok


def test_loeschen_erst_nach_bestaetigung_und_kennung_bleibt_vergeben(client, lehrkraft, protokoll):
    e = protokoll.eintraege.get(kennung="TOP-01")
    client.force_login(lehrkraft)
    url = reverse("kern:eintrag_loeschen", args=[protokoll.schluessel, e.kennung])
    assert client.get(url).status_code == 200
    assert Eintrag.objects.filter(pk=e.pk).exists()
    assert client.post(url).status_code == 302
    assert not Eintrag.objects.filter(pk=e.pk).exists()
    assert ReservierteKennung.objects.filter(dokument=protokoll, kennung="TOP-01").exists()
    assert protokoll.naechste_kennung("TOP-{nr:02d}") == "TOP-02"
    roh = dienste.Rohsatz(
        kennung="TOP-01", eintragstyp="tagesordnungspunkt", titel="Wiederverwenden"
    )
    assert not dienste.pruefen(protokoll, roh).ok
    with pytest.raises(ValidationError):
        Eintrag.objects.create(
            dokument=protokoll,
            kennung="TOP-01",
            eintragstyp="tagesordnungspunkt",
            titel="Wiederverwenden",
        )


@pytest.mark.parametrize("konto", ["andere_lehrkraft", "lesend_nutzer"])
def test_loeschen_schuetzt_fremde_entwuerfe(client, request, konto, protokoll):
    client.force_login(request.getfixturevalue(konto))
    url = reverse("kern:eintrag_loeschen", args=[protokoll.schluessel, "TOP-01"])
    assert client.post(url).status_code == 403
    assert protokoll.eintraege.filter(kennung="TOP-01").exists()


@pytest.mark.parametrize(
    "schutz",
    ["beschluss", "verweis", "historischer_verweis", "kind", "anhang", "kommentar", "planung"],
)
def test_loeschen_schuetzt_freigaben_und_verwendete_inhalte(
    client, admin_nutzer, protokoll, schutz
):
    from kern.models import Anhang, Kommentar, PersoenlicherFortschritt

    e = protokoll.eintraege.get(kennung="TOP-01")
    kopf = protokoll.eintraege.get(kennung="P-01")
    if schutz == "beschluss":
        e.versionen.update(status=Status.ARCHIVIERT)
    elif schutz == "verweis":
        Verlinkung.objects.create(
            von_eintrag=kopf, ziel_typ=Zieltyp.EINTRAG, ziel_id=str(e.pk), art="bezug"
        )
    elif schutz == "historischer_verweis":
        kopf.versionen.update(verlinkungen=[{"ziel_typ": "eintrag", "ziel_id": str(e.pk)}])
    elif schutz == "kind":
        kopf.eltern = e
        kopf.save()
    elif schutz == "anhang":
        Anhang.objects.create(eintrag=e, dateiname="Datei.pdf")
    elif schutz == "planung":
        PersoenlicherFortschritt.objects.create(eintrag=e, nutzer=admin_nutzer, schuljahr="2026/27")
    else:
        Kommentar.objects.create(eintrag=e, autor=admin_nutzer, text="Gemeinsame Arbeit")
    client.force_login(admin_nutzer)
    assert (
        client.post(
            reverse("kern:eintrag_loeschen", args=[protokoll.schluessel, e.kennung])
        ).status_code
        == 409
    )
    assert Eintrag.objects.filter(pk=e.pk).exists()


def freigabedaten(client, protokoll):
    url = reverse("kern:protokoll_beschliessen", args=[protokoll.schluessel])
    antwort = client.get(url)
    return url, {
        "datum": "2026-11-09",
        "gremium": Gremium.objects.get_or_create(name="Lehrerkonferenz")[0].pk,
        "titel": "Genehmigung des Konferenzprotokolls",
        "text": "Das Protokoll wird genehmigt.",
        "stand": antwort.context["stand"],
    }


def test_ganzes_protokoll_wird_gemeinsam_beschlossen(client, admin_nutzer, protokoll):
    client.force_login(admin_nutzer)
    url, daten = freigabedaten(client, protokoll)
    assert not Beschluss.objects.exists()
    assert client.post(url, daten).status_code == 302
    beschluss = Beschluss.objects.get()
    assert beschluss.protokoll_eintrag.kennung == "P-01"
    assert beschluss.beschlossene_versionen.count() == 2
    assert set(protokoll.eintraege.values_list("status", flat=True)) == {Status.BESCHLOSSEN}


@pytest.mark.parametrize("konto", ["lehrkraft", "redaktion_nutzer", "lesend_nutzer"])
def test_protokollbeschluss_nur_administration(client, request, konto, protokoll):
    client.force_login(request.getfixturevalue(konto))
    assert (
        client.post(reverse("kern:protokoll_beschliessen", args=[protokoll.schluessel])).status_code
        == 403
    )
    assert not Beschluss.objects.exists()


@pytest.mark.parametrize("aenderung", ["pflichtfeld", "neuer_eintrag", "neue_fassung", "token"])
def test_protokollfreigabe_bleibt_bei_fehlern_vollstaendig_unveraendert(
    client, admin_nutzer, protokoll, aenderung
):
    client.force_login(admin_nutzer)
    url, daten = freigabedaten(client, protokoll)
    top = protokoll.eintraege.get(kennung="TOP-01")
    if aenderung == "pflichtfeld":
        top.daten = {}
        top.save()
        top.version_anlegen()
    elif aenderung == "neuer_eintrag":
        e = Eintrag.objects.create(
            dokument=protokoll,
            kennung="TOP-02",
            eintragstyp="tagesordnungspunkt",
            titel="Neu",
            daten={"text": "<p>Neu</p>"},
        )
        e.version_anlegen()
    elif aenderung == "neue_fassung":
        top.titel = "Neu bearbeitet"
        top.save()
        top.version_anlegen()
    else:
        daten["stand"] = "manipuliert"
    assert client.post(url, daten).status_code == 200
    assert not Beschluss.objects.exists()
    assert set(protokoll.eintraege.values_list("status", flat=True)) == {Status.ENTWURF}


def test_startseite_begrenzt_und_listen_sind_durchsuchbar(client, lehrkraft, dokument):
    for n in range(25):
        Eintrag.objects.create(
            dokument=dokument,
            kennung=f"K-Test-{n}",
            eintragstyp="grundlagenkapitel",
            titel=f"Entwurf {n}",
            erstellt_von=lehrkraft,
        )
    for n in range(14):
        Dokument.objects.create(
            titel=f"Zusatzdokument {n}", schluessel=f"zusatz-{n}", dokumenttyp=dokument.dokumenttyp
        )
    client.force_login(lehrkraft)
    home = client.get(reverse("kern:startseite"))
    assert len(home.context["eigene_entwuerfe"]) == 5
    assert len(home.context["dokumente"]) == 6
    antwort = client.get(reverse("kern:eigene_entwuerfe"))
    assert len(antwort.context["seite"]) == 20
    assert antwort.context["seite"].paginator.count == 25
    assert len(client.get(reverse("kern:eigene_entwuerfe"), {"seite": 2}).context["seite"]) == 5
    antwort = client.get(reverse("kern:dokumente"), {"q": "Zusatzdokument"})
    assert len(antwort.context["seite"]) == 12
    assert antwort.context["seite"].paginator.count == 14
    assert (
        len(
            client.get(reverse("kern:dokumente"), {"q": "Zusatzdokument", "seite": 2}).context[
                "seite"
            ]
        )
        == 2
    )


def test_erneute_gesamtgenehmigung_erhaelt_bisherige_fassungen(client, admin_nutzer, protokoll):
    from kern import beschluesse

    alt = Beschluss.objects.create(
        datum="2026-10-30",
        gremium=Gremium.objects.create(name="Lehrerkonferenz"),
        titel="Erster Beschluss",
    )
    top = protokoll.eintraege.get(kennung="TOP-01")
    beschluesse.beschluss_fassen(alt, [top])
    client.force_login(admin_nutzer)
    url, daten = freigabedaten(client, protokoll)
    assert client.post(url, daten).status_code == 302
    neu = Beschluss.objects.exclude(pk=alt.pk).get()
    assert neu.beschlossene_versionen.filter(status=Status.BESCHLOSSEN).count() == 2
    assert top.versionen.filter(beschluss=alt, status=Status.ARCHIVIERT).count() == 1


def test_unerwarteter_fehler_fuehrt_nicht_zu_teilfreigabe(
    client, admin_nutzer, protokoll, monkeypatch
):
    from kern import beschluesse

    original = beschluesse.beschluss_fassen

    def abbrechen(beschluss, eintraege, nutzer=None):
        original(beschluss, eintraege[:1], nutzer)
        raise RuntimeError("Abbruch nach dem ersten Eintrag")

    client.force_login(admin_nutzer)
    url, daten = freigabedaten(client, protokoll)
    monkeypatch.setattr(beschluesse, "beschluss_fassen", abbrechen)
    with pytest.raises(RuntimeError):
        client.post(url, daten)
    assert not Beschluss.objects.exists()
    assert set(protokoll.eintraege.values_list("status", flat=True)) == {Status.ENTWURF}
