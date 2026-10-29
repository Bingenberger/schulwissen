"""Versionierung und Beschlüsse (SPEC.md §6, §8)."""

from __future__ import annotations

import datetime as dt

import pytest
from django.core.exceptions import ValidationError

from eintragstypen.dienste import Rohsatz, pruefen, speichern
from kern.models import Beschluss, Gremium, Status

pytestmark = pytest.mark.django_db


@pytest.fixture
def ritual(dokument, kompetenzen, lehrkraft):
    """Ein vollständig gefülltes Ritual – alle Pflichtfelder gesetzt."""
    roh = Rohsatz(
        kennung="R-01",
        eintragstyp="ritual",
        titel="Lesezeit",
        daten={
            "kurzbeschreibung": "Verbindliche Lesezeit dreimal pro Woche.",
            "einheiten_pro_woche": 3,
            "minuten_je_einheit": 20,
            "fester_ablauf": "<p>Einstieg, Lesephase, Austausch</p>",
            "auspraegung_jg1": "<p>Lautlesetandems</p>",
            "auspraegung_jg2": "<p>Silbentexte</p>",
            "auspraegung_jg3": "<p>Lesetandems</p>",
            "auspraegung_jg4": "<p>Freie Lektüre</p>",
            "didaktik_methoden": "<p>Lautlesetandems nach Rosebrock</p>",
            "differenzierung": "<p>Texte in drei Niveaustufen</p>",
            "leistung_bereich": "Sonstige Leistungen",
            "leistung_feststellung": "<p>Beobachtungsbogen Leseflüssigkeit</p>",
        },
        verweise={"kompetenzen_schwerpunkt": ["LE1.03S"]},
    )
    satz = pruefen(dokument, roh)
    assert satz.ok, satz.befunde
    return speichern(dokument, satz, nutzer=lehrkraft)


@pytest.fixture
def gremium(db) -> Gremium:
    return Gremium.objects.create(name="Fachkonferenz Deutsch")


def test_jede_speicherung_erzeugt_eine_fassung(ritual, dokument, lehrkraft):
    roh = Rohsatz(
        kennung="R-01",
        eintragstyp="ritual",
        titel="Lesezeit, überarbeitet",
        daten=dict(ritual.daten),
    )
    speichern(dokument, pruefen(dokument, roh), nutzer=lehrkraft)

    ritual.refresh_from_db()
    assert ritual.titel == "Lesezeit, überarbeitet"
    assert [v.versionsnummer for v in ritual.versionen.all()] == [2, 1]


def test_beschluss_macht_eine_fassung_gueltig(ritual, gremium, admin_nutzer):
    fassung = ritual.letzte_version()
    beschluss = Beschluss.objects.create(
        datum=dt.date(2026, 11, 9),
        gremium=gremium,
        titel="Arbeitsplan Deutsch, Ritual Lesezeit",
        erstellt_von=admin_nutzer,
    )
    fassung.beschluss = beschluss
    fassung.status = Status.BESCHLOSSEN
    fassung.save()
    ritual.status = Status.BESCHLOSSEN
    ritual.save()

    ritual.refresh_from_db()
    assert ritual.beschlossene_version() == fassung
    assert beschluss.beschlossene_versionen.count() == 1
    assert beschluss.herkunft == ("Gilt seit Beschluss der Fachkonferenz Deutsch vom 09.11.2026")


def test_beschlossene_fassung_ist_unveraenderlich(ritual, gremium):
    fassung = ritual.letzte_version()
    fassung.status = Status.BESCHLOSSEN
    fassung.save()

    fassung.titel = "Heimlich geändert"
    with pytest.raises(ValidationError, match="beschlossen"):
        fassung.save()

    with pytest.raises(ValidationError, match="beschlossen"):
        fassung.delete()


def test_bearbeiten_eines_beschlossenen_eintrags_erzeugt_einen_entwurf(
    ritual, dokument, gremium, lehrkraft
):
    """Die beschlossene Fassung bleibt gültig und sichtbar (SPEC.md §6)."""
    fassung = ritual.letzte_version()
    beschluss = Beschluss.objects.create(
        datum=dt.date(2026, 11, 9), gremium=gremium, titel="Beschluss"
    )
    fassung.beschluss = beschluss
    fassung.status = Status.BESCHLOSSEN
    fassung.save()
    ritual.status = Status.BESCHLOSSEN
    ritual.save()

    roh = Rohsatz(
        kennung="R-01",
        eintragstyp="ritual",
        titel="Lesezeit, neue Idee",
        daten=dict(ritual.daten),
    )
    speichern(dokument, pruefen(dokument, roh), nutzer=lehrkraft)

    ritual.refresh_from_db()
    assert ritual.status == Status.ENTWURF
    assert ritual.titel == "Lesezeit, neue Idee"
    # Die beschlossene Fassung ist unverändert erhalten.
    beschlossen = ritual.beschlossene_version()
    assert beschlossen.versionsnummer == 1
    assert beschlossen.titel == "Lesezeit"
    assert ritual.letzte_version().versionsnummer == 2


def test_import_setzt_niemals_direkt_auf_beschlossen(dokument, kompetenzen, arbeitsmappe):
    """„beschlossen“ entsteht nur über einen Beschluss (SPEC.md §8)."""
    roh = Rohsatz(
        kennung="R-05",
        eintragstyp="ritual",
        titel="Angeblich beschlossen",
        status=Status.BESCHLOSSEN,
        daten={"kurzbeschreibung": "Test"},
    )
    satz = pruefen(dokument, roh)
    eintrag = speichern(dokument, satz)

    assert eintrag.status == Status.ABGESTIMMT
    assert any("Beschluss" in b.text for b in satz.warnungen)


def test_pflichtfelder_fehlen_wird_gemeldet_blockiert_aber_nicht(dokument, kompetenzen):
    roh = Rohsatz(
        kennung="R-06",
        eintragstyp="ritual",
        titel="Nur angefangen",
        daten={"kurzbeschreibung": "Erst mal notiert."},
    )
    satz = pruefen(dokument, roh)

    assert satz.ok, "Als Entwurf speichern muss immer gehen."
    fehlende = {f.schluessel for f in satz.fehlende_pflichtfelder}
    assert "einheiten_pro_woche" in fehlende
    assert "kompetenzen_schwerpunkt" in fehlende
    assert "kurzbeschreibung" not in fehlende

    eintrag = speichern(dokument, satz)
    assert eintrag.status == Status.ENTWURF


def test_vollstaendiges_ritual_hat_keine_offenen_pflichtfelder(ritual):
    offen = ritual.typ.fehlende_pflichtfelder(
        ritual.daten, [v.feld for v in ritual.verlinkungen.all()]
    )
    assert offen == []


def test_klassenarbeit_ist_in_jahrgang_1_kein_pflichtfeld(dokument, kompetenzen):
    """Klassenarbeiten gibt es erst ab Klasse 3 (SPEC.md §7.4)."""
    from eintragstypen.registry import registry

    vorhaben = registry.holen("vorhaben")

    offen_jg1 = {f.schluessel for f in vorhaben.fehlende_pflichtfelder({"jahrgang": 1})}
    offen_jg3 = {f.schluessel for f in vorhaben.fehlende_pflichtfelder({"jahrgang": 3})}

    assert "klassenarbeit" not in offen_jg1
    assert "klassenarbeit" in offen_jg3


def test_kennungen_werden_nie_neu_vergeben(dokument, kompetenzen):
    """Auch nach dem Archivieren zählt die Kennung weiter hoch (SPEC.md §6)."""
    from eintragstypen.registry import registry

    ritual_typ = registry.holen("ritual")
    erste = ritual_typ.kennung_bauen(dokument)
    speichern(
        dokument,
        pruefen(dokument, Rohsatz(kennung=erste, eintragstyp="ritual", titel="Erstes")),
    )

    zweite = ritual_typ.kennung_bauen(dokument)
    eintrag = speichern(
        dokument,
        pruefen(dokument, Rohsatz(kennung=zweite, eintragstyp="ritual", titel="Zweites")),
    )
    eintrag.status = Status.ARCHIVIERT
    eintrag.save()

    dritte = ritual_typ.kennung_bauen(dokument)

    assert erste == "R-01"
    assert zweite == "R-02"
    assert dritte == "R-03", "Eine archivierte Kennung darf nicht neu vergeben werden."


def test_vorhaben_kennung_enthaelt_den_jahrgang(dokument, kompetenzen):
    from eintragstypen.registry import registry

    vorhaben = registry.holen("vorhaben")
    assert vorhaben.kennung_bauen(dokument, jahrgang=3) == "V-3-01"
    speichern(
        dokument,
        pruefen(dokument, Rohsatz(kennung="V-3-01", eintragstyp="vorhaben", titel="Eins")),
    )
    assert vorhaben.kennung_bauen(dokument, jahrgang=3) == "V-3-02"
    # Jahrgang 4 zählt eigenständig.
    assert vorhaben.kennung_bauen(dokument, jahrgang=4) == "V-4-01"


def test_anzeigenummer_folgt_dem_baum_die_kennung_bleibt(dokument):
    """Verschiebt man ein Kapitel, ändert sich nur die angezeigte Nummer."""
    kapitel = dokument.eintraege.get(kennung="2.4")
    assert kapitel.anzeige_nummer == "2.4"

    # „Leistungsbewertung“ an den Anfang von Kapitel 2 ziehen.
    kapitel.position = 1
    kapitel.save()

    kapitel.refresh_from_db()
    assert kapitel.kennung == "2.4", "Die Kennung wird nie neu vergeben."
    assert kapitel.anzeige_nummer == "2.1", "Die Anzeige folgt der neuen Stellung."
    # Das frühere 2.1 heißt jetzt 2.2 – ebenfalls nur in der Anzeige.
    vorhaben_kapitel = dokument.eintraege.get(kennung="2.1")
    assert vorhaben_kapitel.anzeige_nummer == "2.2"


def test_gliederung_ist_vollstaendig(dokument):
    """Die zehn Kapitel aus SPEC.md §7.1 werden automatisch erzeugt."""
    kennungen = set(dokument.eintraege.values_list("kennung", flat=True))
    assert kennungen == {"1", "2", "2.1", "2.2", "2.3", "2.4", "2.5", "3", "4", "A"}

    kapitel_zwei = dokument.eintraege.get(kennung="2")
    unterkapitel = {k.kennung for k in kapitel_zwei.kinder.all()}
    assert unterkapitel == {"2.1", "2.2", "2.3", "2.4", "2.5"}


def test_gliederung_erneut_anlegen_laesst_texte_unberuehrt(dokument):
    from deutsch import gliederung

    kapitel = dokument.eintraege.get(kennung="2.4")
    kapitel.daten = {"text": "<p>Unser Leistungskonzept</p>"}
    kapitel.titel = "Leistungsbewertung (überarbeitet)"
    kapitel.save()

    nochmal, neu, angelegt = gliederung.dokument_anlegen()

    assert nochmal.pk == dokument.pk
    assert neu is False
    assert angelegt == 0
    kapitel.refresh_from_db()
    assert kapitel.daten["text"] == "<p>Unser Leistungskonzept</p>"
    assert kapitel.titel == "Leistungsbewertung (überarbeitet)"
