"""Beschlüsse, Fassungsvergleich und „Änderungen seit Beschluss“ (SPEC.md §8)."""

from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from eintragstypen.dienste import Rohsatz, pruefen, speichern
from kern import beschluesse, vergleich
from kern.models import Beschluss, Gremium, Status

pytestmark = pytest.mark.django_db

PASSWORT = "testpasswort-sehr-lang"


def anmelden(client, nutzer):
    assert client.login(email=nutzer.email, password=PASSWORT)
    return client


@pytest.fixture
def gremium(db) -> Gremium:
    return Gremium.objects.create(name="Fachkonferenz Deutsch")


@pytest.fixture
def abgestimmt(importierter_arbeitsplan):
    """Ein Vorhaben, das die Gruppe abgestimmt hat."""
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    vorhaben.status = Status.ABGESTIMMT
    vorhaben.save()
    letzte = vorhaben.letzte_version()
    letzte.status = Status.ABGESTIMMT
    letzte.save()
    return vorhaben


@pytest.fixture
def beschluss(gremium, admin_nutzer) -> Beschluss:
    return Beschluss.objects.create(
        datum=dt.date(2026, 11, 9),
        gremium=gremium,
        titel="Arbeitsplan Deutsch, Unterrichtsvorhaben Jahrgang 3",
        text="Die Fachkonferenz beschließt die vorgelegten Vorhaben.",
        erstellt_von=admin_nutzer,
    )


# --- Beschluss fassen ------------------------------------------------------


def test_beschluss_macht_fassungen_gueltig(abgestimmt, beschluss, admin_nutzer):
    bericht = beschluesse.beschluss_fassen(beschluss, [abgestimmt], nutzer=admin_nutzer)

    abgestimmt.refresh_from_db()
    assert bericht.beschlossen == 1
    assert abgestimmt.status == Status.BESCHLOSSEN
    gueltig = abgestimmt.beschlossene_version()
    assert gueltig is not None
    assert gueltig.beschluss == beschluss


def test_aelterer_beschluss_wird_archiviert(
    abgestimmt, beschluss, gremium, admin_nutzer, importierter_arbeitsplan
):
    """Vorgängerfassungen werden archiviert, nicht gelöscht (SPEC.md §8.4)."""
    beschluesse.beschluss_fassen(beschluss, [abgestimmt], nutzer=admin_nutzer)
    erste_fassung = abgestimmt.beschlossene_version()

    # Neue Arbeitsfassung, erneut abstimmen, erneut beschließen.
    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel="Märchen, überarbeitet",
        status=Status.ABGESTIMMT,
        daten=dict(abgestimmt.daten),
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))
    abgestimmt.refresh_from_db()

    zweiter = Beschluss.objects.create(datum=dt.date(2027, 3, 1), gremium=gremium, titel="Nachtrag")
    bericht = beschluesse.beschluss_fassen(zweiter, [abgestimmt], nutzer=admin_nutzer)

    erste_fassung.refresh_from_db()
    assert bericht.archiviert == 1
    assert erste_fassung.status == Status.ARCHIVIERT
    # Der Verweis auf den alten Beschluss bleibt – die Historie bleibt lesbar.
    assert erste_fassung.beschluss_id == beschluss.pk
    assert abgestimmt.beschlossene_version().titel == "Märchen, überarbeitet"


def test_schon_beschlossenes_wird_uebersprungen(abgestimmt, beschluss, admin_nutzer):
    beschluesse.beschluss_fassen(beschluss, [abgestimmt], nutzer=admin_nutzer)
    bericht = beschluesse.beschluss_fassen(beschluss, [abgestimmt], nutzer=admin_nutzer)

    assert bericht.beschlossen == 0
    assert any("schon beschlossen" in h for h in bericht.uebersprungen)


def test_beschluss_zuruecknehmen(abgestimmt, beschluss, admin_nutzer):
    beschluesse.beschluss_fassen(beschluss, [abgestimmt], nutzer=admin_nutzer)

    anzahl = beschluesse.beschluss_zuruecknehmen(beschluss)

    abgestimmt.refresh_from_db()
    assert anzahl == 1
    assert abgestimmt.status == Status.ABGESTIMMT
    assert abgestimmt.beschlossene_version() is None


def test_vorlage_zeigt_nur_abgestimmtes(abgestimmt, importierter_arbeitsplan):
    kandidaten = list(beschluesse.vorlage_kandidaten(importierter_arbeitsplan))

    kennungen = {e.kennung for e in kandidaten}
    assert kennungen == {"V-3-01"}
    assert "R-01" not in kennungen, "R-01 ist nur Entwurf."


# --- Änderungen seit Beschluss ---------------------------------------------


def test_aenderungen_seit_beschluss(abgestimmt, beschluss, admin_nutzer, importierter_arbeitsplan):
    beschluesse.beschluss_fassen(beschluss, [abgestimmt], nutzer=admin_nutzer)

    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel="Märchen, jetzt mit Hörspiel",
        daten=dict(abgestimmt.daten),
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))

    uebersicht = beschluesse.aenderungen_seit_beschluss(importierter_arbeitsplan)

    geaenderte_kennungen = {e.kennung for e, _, _ in uebersicht["geaendert"]}
    assert "V-3-01" in geaenderte_kennungen
    # R-01 und die Kapitel waren noch nie beschlossen.
    assert "R-01" in {e.kennung for e in uebersicht["neu"]}


def test_ohne_aenderung_gilt_als_unveraendert(
    abgestimmt, beschluss, admin_nutzer, importierter_arbeitsplan
):
    beschluesse.beschluss_fassen(beschluss, [abgestimmt], nutzer=admin_nutzer)

    uebersicht = beschluesse.aenderungen_seit_beschluss(importierter_arbeitsplan)

    assert uebersicht["geaendert"] == []
    assert "V-3-01" in {e.kennung for e in uebersicht["unveraendert"]}


# --- Fassungsvergleich -----------------------------------------------------


def test_vergleich_findet_geaendertes_feld(importierter_arbeitsplan):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    alt = vorhaben.letzte_version()

    daten = dict(vorhaben.daten)
    daten["kurzbeschreibung"] = "Märchen kennenlernen und ein Hörspiel aufnehmen."
    roh = Rohsatz(kennung="V-3-01", eintragstyp="vorhaben", titel=vorhaben.titel, daten=daten)
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))
    vorhaben.refresh_from_db()
    neu = vorhaben.letzte_version()

    ergebnis = vergleich.vergleichen(alt, neu)

    geaendert = {f.schluessel for f in ergebnis.geaenderte_felder}
    assert "kurzbeschreibung" in geaendert
    assert ergebnis.hat_aenderungen
    assert not ergebnis.titel_geaendert


def test_vergleich_merkt_titelaenderung(importierter_arbeitsplan):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    alt = vorhaben.letzte_version()
    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel="Ganz anderer Titel",
        daten=dict(vorhaben.daten),
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))
    vorhaben.refresh_from_db()

    ergebnis = vergleich.vergleichen(alt, vorhaben.letzte_version())

    assert ergebnis.titel_geaendert


def test_vergleich_zeigt_verweise(importierter_arbeitsplan, kompetenzen):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    alt = vorhaben.letzte_version()

    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel=vorhaben.titel,
        daten=dict(vorhaben.daten),
        verweise={"kompetenzen_schwerpunkt": ["SC2.02D"]},
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))
    vorhaben.refresh_from_db()

    ergebnis = vergleich.vergleichen(alt, vorhaben.letzte_version())

    # Vier Schwerpunkte sind weggefallen, SC2.02D ist geblieben.
    assert len(ergebnis.verweise_weg) == 4
    assert ergebnis.verweise_dazu == []


def test_wortvergleich_markiert_ein_und_ausgefuegtes():
    ergebnis = vergleich.woerter_vergleichen(
        "Märchen lesen und nacherzählen", "Märchen lesen und schreiben"
    )

    assert "<del>nacherzählen</del>" in ergebnis
    assert "<ins>schreiben</ins>" in ergebnis
    assert "Märchen lesen und" in ergebnis


def test_wortvergleich_entschaerft_html():
    ergebnis = vergleich.woerter_vergleichen("alt", "<script>alert(1)</script>")

    assert "<script>" not in ergebnis
    assert "&lt;script&gt;" in ergebnis


# --- Oberfläche ------------------------------------------------------------


def test_beschlussvorlage_nur_fuer_redaktion(client, lehrkraft, redaktion_nutzer, abgestimmt):
    anmelden(client, lehrkraft)
    als_lehrkraft = client.get(reverse("kern:beschlussvorlage"))

    client.logout()
    anmelden(client, redaktion_nutzer)
    als_redaktion = client.get(reverse("kern:beschlussvorlage"))

    assert als_lehrkraft.status_code == 403
    assert als_redaktion.status_code == 200
    assert "V-3-01" in als_redaktion.content.decode()


def test_beschluss_ueber_die_oberflaeche_eintragen(client, admin_nutzer, gremium, abgestimmt):
    anmelden(client, admin_nutzer)

    antwort = client.post(
        reverse("kern:beschluss_anlegen"),
        {
            "speichern": "1",
            "eintrag": [str(abgestimmt.pk)],
            "datum": "2026-11-09",
            "gremium": str(gremium.pk),
            "titel": "Arbeitsplan Deutsch, Jahrgang 3",
            "text": "Beschlossen wie vorgelegt.",
        },
        follow=True,
    )

    abgestimmt.refresh_from_db()
    assert antwort.status_code == 200
    assert abgestimmt.status == Status.BESCHLOSSEN
    assert Beschluss.objects.filter(titel="Arbeitsplan Deutsch, Jahrgang 3").exists()
    assert "sind jetzt gültig" in antwort.content.decode()


def test_lehrkraft_darf_keinen_beschluss_eintragen(client, lehrkraft, gremium, abgestimmt):
    anmelden(client, lehrkraft)

    antwort = client.post(
        reverse("kern:beschluss_anlegen"),
        {
            "speichern": "1",
            "eintrag": [str(abgestimmt.pk)],
            "datum": "2026-11-09",
            "gremium": str(gremium.pk),
            "titel": "Heimlich",
        },
    )

    assert antwort.status_code == 403
    assert not Beschluss.objects.filter(titel="Heimlich").exists()


def test_beschluss_ohne_auswahl_wird_abgelehnt(client, admin_nutzer, gremium):
    anmelden(client, admin_nutzer)

    antwort = client.post(
        reverse("kern:beschluss_anlegen"),
        {"speichern": "1", "datum": "2026-11-09", "gremium": str(gremium.pk), "titel": "Leer"},
    )

    assert antwort.status_code == 200
    assert "mindestens einen Eintrag" in antwort.content.decode()
    assert not Beschluss.objects.filter(titel="Leer").exists()


def test_beschlossener_eintrag_nennt_seinen_beschluss(
    client, lehrkraft, abgestimmt, beschluss, admin_nutzer, importierter_arbeitsplan
):
    """SPEC.md §8.5: „Gilt seit Beschluss der … vom …“ steht oben."""
    beschluesse.beschluss_fassen(beschluss, [abgestimmt], nutzer=admin_nutzer)
    anmelden(client, lehrkraft)

    antwort = client.get(
        reverse("kern:eintrag", args=[importierter_arbeitsplan.schluessel, "V-3-01"])
    )
    inhalt = antwort.content.decode()

    assert "Gilt seit Beschluss der Fachkonferenz Deutsch vom 09.11.2026" in inhalt


@pytest.mark.parametrize("name", ["kern:beschluesse", "kern:beschlussvorlage"])
def test_beschlussseiten_laden(client, admin_nutzer, abgestimmt, name):
    anmelden(client, admin_nutzer)

    assert client.get(reverse(name)).status_code == 200


def test_vergleichsseite_und_aenderungen_laden(client, lehrkraft, importierter_arbeitsplan):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel="Zweiter Stand",
        daten=dict(vorhaben.daten),
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))
    anmelden(client, lehrkraft)

    vergleichsseite = client.get(
        reverse("kern:vergleich", args=[importierter_arbeitsplan.schluessel, "V-3-01"])
    )
    aenderungen = client.get(
        reverse("kern:aenderungen", args=[importierter_arbeitsplan.schluessel])
    )
    fassung = client.get(
        reverse("kern:version", args=[importierter_arbeitsplan.schluessel, "V-3-01", 1])
    )

    assert vergleichsseite.status_code == 200
    assert aenderungen.status_code == 200
    assert fassung.status_code == 200
    assert "Märchen entdecken" in fassung.content.decode()


def test_titel_wird_wortweise_verglichen(importierter_arbeitsplan):
    """Gleiche Wörter im Titel sollen nicht als Änderung erscheinen."""
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    alt = vorhaben.letzte_version()
    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel="Märchen entdecken und als Hörspiel erzählen",
        daten=dict(vorhaben.daten),
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))
    vorhaben.refresh_from_db()

    ergebnis = vergleich.vergleichen(alt, vorhaben.letzte_version())
    gegenueberstellung = ergebnis.titel_gegenueberstellung

    # „Märchen entdecken und“ ist gleich geblieben und bleibt unmarkiert.
    assert "<del>Märchen entdecken und " not in gegenueberstellung
    assert "Märchen entdecken und" in gegenueberstellung
    assert "<del>" in gegenueberstellung
    assert "<ins>" in gegenueberstellung
