"""Rollen und Rechte (SPEC.md §5)."""

from __future__ import annotations

import pytest

from eintragstypen.dienste import Rohsatz, pruefen, speichern
from kern import rechte
from kern.models import Status

pytestmark = pytest.mark.django_db


@pytest.fixture
def entwurf(dokument, kompetenzen, lehrkraft, arbeitsgruppe):
    """Ein Entwurf der Arbeitsgruppe „Jahrgang 3“."""
    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel="Märchen",
        daten={"jahrgang": 3, "quartal": "Q2"},
    )
    eintrag = speichern(dokument, pruefen(dokument, roh), nutzer=lehrkraft)
    eintrag.verantwortlich_gruppe = arbeitsgruppe
    eintrag.save()
    lehrkraft.groups.add(arbeitsgruppe)
    return eintrag


@pytest.fixture
def beschlossener_eintrag(entwurf):
    entwurf.status = Status.BESCHLOSSEN
    entwurf.save()
    return entwurf


# --- Lesen -----------------------------------------------------------------


def test_lesend_sieht_nur_beschlossene_inhalte(lesend_nutzer, entwurf):
    assert rechte.darf_lesen(lesend_nutzer, entwurf) is False

    entwurf.status = Status.BESCHLOSSEN
    assert rechte.darf_lesen(lesend_nutzer, entwurf) is True


def test_lehrkraft_darf_jeden_entwurf_lesen(andere_lehrkraft, entwurf):
    """§5 begrenzt bei der Lehrkraft das Bearbeiten, nicht das Lesen."""
    assert rechte.darf_lesen(andere_lehrkraft, entwurf) is True


def test_sichtbare_eintraege_filtert_fuer_lesende(lesend_nutzer, lehrkraft, dokument, entwurf):
    alle = dokument.eintraege.all()

    fuer_lesende = rechte.sichtbare_eintraege(lesend_nutzer, alle)
    fuer_lehrkraft = rechte.sichtbare_eintraege(lehrkraft, alle)

    assert entwurf not in fuer_lesende
    assert entwurf in fuer_lehrkraft


def test_konto_ohne_rolle_gilt_als_nur_lesend(db, entwurf):
    """Ein neu angelegtes Konto soll nicht versehentlich Entwürfe sehen."""
    from kern.models import Nutzer

    neu = Nutzer.objects.create_user(
        email="neu@example.org", password="testpasswort-sehr-lang", anzeigename="Neu"
    )

    assert rechte.ist_nur_lesend(neu) is True
    assert rechte.darf_lesen(neu, entwurf) is False


# --- Bearbeiten ------------------------------------------------------------


def test_lehrkraft_bearbeitet_entwuerfe_der_eigenen_arbeitsgruppe(lehrkraft, entwurf):
    assert rechte.darf_bearbeiten(lehrkraft, entwurf) is True


def test_lehrkraft_bearbeitet_fremde_entwuerfe_nicht(andere_lehrkraft, entwurf):
    assert rechte.darf_bearbeiten(andere_lehrkraft, entwurf) is False


def test_lehrkraft_bearbeitet_beschlossene_eintraege_nicht(lehrkraft, beschlossener_eintrag):
    assert rechte.darf_bearbeiten(lehrkraft, beschlossener_eintrag) is False


def test_redaktion_und_administration_bearbeiten_alles(
    redaktion_nutzer, admin_nutzer, beschlossener_eintrag
):
    assert rechte.darf_bearbeiten(redaktion_nutzer, beschlossener_eintrag) is True
    assert rechte.darf_bearbeiten(admin_nutzer, beschlossener_eintrag) is True


def test_lesend_bearbeitet_nichts(lesend_nutzer, entwurf):
    assert rechte.darf_bearbeiten(lesend_nutzer, entwurf) is False
    assert rechte.darf_anlegen(lesend_nutzer) is False


# --- Status ----------------------------------------------------------------


def test_nur_redaktion_setzt_auf_abgestimmt(lehrkraft, redaktion_nutzer, entwurf):
    assert rechte.darf_status_setzen(lehrkraft, entwurf, Status.ABGESTIMMT) is False
    assert rechte.darf_status_setzen(redaktion_nutzer, entwurf, Status.ABGESTIMMT) is True


def test_nur_administration_setzt_auf_beschlossen(redaktion_nutzer, admin_nutzer, entwurf):
    assert rechte.darf_status_setzen(redaktion_nutzer, entwurf, Status.BESCHLOSSEN) is False
    assert rechte.darf_status_setzen(admin_nutzer, entwurf, Status.BESCHLOSSEN) is True


def test_lehrkraft_setzt_eigenen_entwurf_auf_idee(lehrkraft, entwurf):
    assert rechte.darf_status_setzen(lehrkraft, entwurf, Status.IDEE) is True


# --- Verwaltung ------------------------------------------------------------


def test_import_und_beschluss_sind_der_administration_vorbehalten(
    admin_nutzer, redaktion_nutzer, lehrkraft
):
    assert rechte.darf_importieren(admin_nutzer) is True
    assert rechte.darf_importieren(redaktion_nutzer) is False
    assert rechte.darf_beschliessen(lehrkraft) is False
    assert rechte.darf_dokument_anlegen(redaktion_nutzer) is False


def test_schulische_festlegung_nur_redaktion_und_administration(
    redaktion_nutzer, lehrkraft, admin_nutzer
):
    """Kompetenzen sind sonst nur auswählbar (SPEC.md §7.3)."""
    assert rechte.darf_schulische_festlegung_bearbeiten(admin_nutzer) is True
    assert rechte.darf_schulische_festlegung_bearbeiten(redaktion_nutzer) is True
    assert rechte.darf_schulische_festlegung_bearbeiten(lehrkraft) is False


def test_kommentieren_darf_jede_lehrkraft_aber_nicht_lesend(
    lehrkraft, lesend_nutzer, beschlossener_eintrag
):
    assert rechte.darf_kommentieren(lehrkraft, beschlossener_eintrag) is True
    assert rechte.darf_kommentieren(lesend_nutzer, beschlossener_eintrag) is False


def test_rollen_erben_aufwaerts(admin_nutzer, redaktion_nutzer, lehrkraft):
    """Administration kann alles, was Redaktion kann, und so weiter."""
    assert rechte.ist_lehrkraft(admin_nutzer) is True
    assert rechte.ist_lehrkraft(redaktion_nutzer) is True
    assert rechte.ist_redaktion(lehrkraft) is False
    assert rechte.ist_administration(redaktion_nutzer) is False


# --- Zuordnung der Arbeitsgruppe beim Import -------------------------------


def test_import_ordnet_vorhaben_der_jahrgangsgruppe_zu(dokument, kompetenzen, arbeitsgruppe):
    """Sonst könnte niemand aus dem Kollegium einen importierten Eintrag bearbeiten."""
    roh = Rohsatz(
        kennung="V-3-05",
        eintragstyp="vorhaben",
        titel="Aus der Arbeitsmappe",
        daten={"jahrgang": 3},
    )

    eintrag = speichern(dokument, pruefen(dokument, roh))

    assert eintrag.verantwortlich_gruppe == arbeitsgruppe


def test_import_nutzt_die_spalte_verantwortlich(db, dokument, kompetenzen):
    from django.contrib.auth.models import Group

    from kern.models import Gruppenart, Gruppenprofil

    gruppe = Group.objects.create(name="Steuergruppe")
    Gruppenprofil.objects.create(gruppe=gruppe, art=Gruppenart.ARBEITSGRUPPE)
    roh = Rohsatz(
        kennung="R-05",
        eintragstyp="ritual",
        titel="Mit Verantwortlicher",
        verantwortlich_text="steuergruppe",
    )

    eintrag = speichern(dokument, pruefen(dokument, roh))

    assert eintrag.verantwortlich_gruppe == gruppe
    assert eintrag.verantwortlich_text == "steuergruppe"


def test_lehrkraft_bearbeitet_importiertes_vorhaben_ihres_jahrgangs(
    dokument, kompetenzen, arbeitsgruppe, lehrkraft
):
    lehrkraft.groups.add(arbeitsgruppe)
    roh = Rohsatz(
        kennung="V-3-06", eintragstyp="vorhaben", titel="Importiert", daten={"jahrgang": 3}
    )
    eintrag = speichern(dokument, pruefen(dokument, roh))

    assert rechte.darf_bearbeiten(lehrkraft, eintrag) is True


def test_ohne_passende_gruppe_bleibt_das_feld_leer(dokument, kompetenzen):
    roh = Rohsatz(
        kennung="V-2-01", eintragstyp="vorhaben", titel="Jahrgang 2", daten={"jahrgang": 2}
    )

    eintrag = speichern(dokument, pruefen(dokument, roh))

    assert eintrag.verantwortlich_gruppe_id is None


# --- Beschlossene Fassungen bleiben sichtbar (SPEC.md §6) ------------------


@pytest.fixture
def beschlossen_mit_entwurf(dokument, kompetenzen, lehrkraft):
    """Ein beschlossener Eintrag, an dem inzwischen weitergearbeitet wird."""
    import datetime as dt

    from kern import beschluesse
    from kern.models import Beschluss, Gremium

    roh = Rohsatz(
        kennung="V-3-09",
        eintragstyp="vorhaben",
        titel="Beschlossener Stand",
        daten={"jahrgang": 3, "quartal": "Q1"},
    )
    eintrag = speichern(dokument, pruefen(dokument, roh))
    eintrag.status = Status.ABGESTIMMT
    eintrag.save()
    fassung = eintrag.letzte_version()
    fassung.status = Status.ABGESTIMMT
    fassung.save()

    gremium, _ = Gremium.objects.get_or_create(name="Fachkonferenz Deutsch")
    beschluss = Beschluss.objects.create(
        datum=dt.date(2026, 11, 9), gremium=gremium, titel="Beschluss"
    )
    beschluesse.beschluss_fassen(beschluss, [eintrag])

    # Jetzt arbeitet jemand weiter – der Eintrag wird wieder Entwurf.
    neu = Rohsatz(
        kennung="V-3-09",
        eintragstyp="vorhaben",
        titel="Neuer Arbeitsstand",
        daten={"jahrgang": 3, "quartal": "Q2"},
    )
    speichern(dokument, pruefen(dokument, neu), nutzer=lehrkraft)
    eintrag.refresh_from_db()
    return eintrag


def test_bearbeiten_macht_den_eintrag_wieder_zum_entwurf(beschlossen_mit_entwurf):
    assert beschlossen_mit_entwurf.status == Status.ENTWURF
    assert beschlossen_mit_entwurf.beschlossene_version().titel == "Beschlossener Stand"


def test_lesende_verlieren_die_beschlossene_fassung_nicht(lesend_nutzer, beschlossen_mit_entwurf):
    """Sonst verschwände ein beschlossener Eintrag, sobald jemand ihn anfasst."""
    assert rechte.darf_lesen(lesend_nutzer, beschlossen_mit_entwurf) is True


def test_sichtbare_eintraege_behalten_beschlossenes(
    lesend_nutzer, dokument, beschlossen_mit_entwurf
):
    sichtbar = rechte.sichtbare_eintraege(lesend_nutzer, dokument.eintraege.all())

    assert beschlossen_mit_entwurf in sichtbar


def test_entwurf_ohne_beschluss_bleibt_verborgen(lesend_nutzer, dokument, kompetenzen):
    roh = Rohsatz(kennung="V-3-10", eintragstyp="vorhaben", titel="Nur Entwurf")
    eintrag = speichern(dokument, pruefen(dokument, roh))

    assert rechte.darf_lesen(lesend_nutzer, eintrag) is False
    assert eintrag not in rechte.sichtbare_eintraege(lesend_nutzer, dokument.eintraege.all())


def _fliesstext(antwort) -> str:
    """Seiteninhalt mit zusammengefassten Leerräumen.

    Vorlagen umbrechen ihre Sätze; ohne das scheitert jede Prüfung auf einen
    Satz an einem Zeilenumbruch.
    """
    import re

    return re.sub(r"\s+", " ", antwort.content.decode())


def test_lesende_sehen_den_beschlossenen_inhalt_nicht_den_entwurf(
    client, lesend_nutzer, beschlossen_mit_entwurf, dokument
):
    from django.urls import reverse

    assert client.login(email=lesend_nutzer.email, password="testpasswort-sehr-lang")

    antwort = client.get(reverse("kern:eintrag", args=[dokument.schluessel, "V-3-09"]))
    inhalt = _fliesstext(antwort)

    assert antwort.status_code == 200
    assert "Beschlossener Stand" in inhalt
    assert "Neuer Arbeitsstand" not in inhalt
    assert "Es gibt bereits einen neueren Entwurf" in inhalt


def test_bearbeitende_sehen_den_entwurf_mit_hinweis(
    client, lehrkraft, beschlossen_mit_entwurf, dokument
):
    from django.urls import reverse

    assert client.login(email=lehrkraft.email, password="testpasswort-sehr-lang")

    antwort = client.get(reverse("kern:eintrag", args=[dokument.schluessel, "V-3-09"]))
    inhalt = _fliesstext(antwort)

    assert "Neuer Arbeitsstand" in inhalt
    assert "Angezeigt wird der Arbeitsstand" in inhalt
    assert "Unterschiede ansehen" in inhalt


def test_lesende_finden_den_beschlossenen_eintrag_auch_ueber_die_suche(
    lesend_nutzer, beschlossen_mit_entwurf
):
    from suche import dienste

    ergebnis = dienste.suchen(lesend_nutzer, "Beschlossener")

    assert "V-3-09" in {t.kennung for g in ergebnis.gruppen for t in g.treffer}


def test_gliederung_bleibt_fuer_lesende_nutzbar(
    client, lesend_nutzer, beschlossen_mit_entwurf, dokument
):
    """Ohne das Kapitelgerüst stünde ein freigegebenes Vorhaben nirgends im Baum.

    Die Kapitel selbst sind Entwurf; sie erscheinen als Gerüst, sind aber nicht
    anklickbar.
    """
    from django.urls import reverse

    assert client.login(email=lesend_nutzer.email, password="testpasswort-sehr-lang")

    inhalt = _fliesstext(client.get(reverse("kern:eintrag", args=[dokument.schluessel, "V-3-09"])))

    # Das Gerüst ist da …
    assert "Unterrichtsvorhaben" in inhalt
    assert "Leistungsbewertung und Leistungsrückmeldung" in inhalt
    assert "ist-gesperrt" in inhalt
    # … und der eigene, freigegebene Eintrag auch.
    assert "V-3-09" in inhalt
    # Nicht freigegebene Kapitel sind nicht verlinkt.
    assert 'href="/d/arbeitsplan-deutsch/2.4"' not in inhalt


def test_lesende_sehen_den_status_der_angezeigten_fassung(
    client, lesend_nutzer, beschlossen_mit_entwurf, dokument
):
    """„Status: Entwurf“ neben einer beschlossenen Fassung wäre irreführend."""
    from django.urls import reverse

    assert client.login(email=lesend_nutzer.email, password="testpasswort-sehr-lang")

    inhalt = _fliesstext(client.get(reverse("kern:eintrag", args=[dokument.schluessel, "V-3-09"])))

    assert '<span class="schild schild-klein schild-beschlossen">beschlossen' in inhalt
    assert '<span class="schild schild-klein schild-entwurf">' not in inhalt
    assert "Der Arbeitsstand ist noch Entwurf." in inhalt


def test_bearbeitende_sehen_weiter_die_volle_gliederung(client, lehrkraft, dokument):
    from django.urls import reverse

    assert client.login(email=lehrkraft.email, password="testpasswort-sehr-lang")

    inhalt = _fliesstext(client.get(reverse("kern:dokument", args=[dokument.schluessel])))

    assert "ist-gesperrt" not in inhalt
    assert 'href="/d/arbeitsplan-deutsch/2.4"' in inhalt
