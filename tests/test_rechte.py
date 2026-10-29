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
