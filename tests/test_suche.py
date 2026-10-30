"""Die Suche (SPEC.md §9).

Der wichtigste Test ist ``test_abnahme_maerchen``: er ist die Abnahme aus
SPEC.md §13 für Phase 2 – die Suche nach „Märchen“ muss das Vorhaben, das
Kapitel 2.4 und eine angehängte PDF finden.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from eintragstypen.dienste import Rohsatz, pruefen, speichern
from kern.models import Status
from suche import dienste

pytestmark = pytest.mark.django_db

PASSWORT = "testpasswort-sehr-lang"


def anmelden(client, nutzer):
    assert client.login(email=nutzer.email, password=PASSWORT)
    return client


@pytest.fixture
def kapitel_mit_text(importierter_arbeitsplan, lehrkraft):
    """Kapitel 2.4 mit dem Leistungskonzept – enthält das Wort „Märchen“."""
    kapitel = importierter_arbeitsplan.eintraege.get(kennung="2.4")
    roh = Rohsatz(
        kennung="2.4",
        eintragstyp="grundlagenkapitel",
        titel=kapitel.titel,
        daten={
            "text": "<p>Schriftliche Arbeiten in Klasse 3 und 4: Das selbst "
            "geschriebene Märchen wird nach den Kriterien aus dem Märchenraster "
            "bewertet.</p>"
        },
    )
    return speichern(
        importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh), nutzer=lehrkraft
    )


@pytest.fixture
def pdf_anhang(importierter_arbeitsplan, lehrkraft):
    """Eine angehängte PDF, deren Text schon ausgelesen ist."""
    from kern.models import Anhang

    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    anhang = Anhang.objects.create(
        eintrag=vorhaben,
        dokument=importierter_arbeitsplan,
        dateiname="Merkmale von Maerchen.pdf",
        mimetype="application/pdf",
        beschreibung="Übersicht für die Hand der Kinder",
        extrahierter_text=(
            "Merkmale von Märchen: Es war einmal, Zahlen wie drei und sieben, "
            "Gut und Böse, ein gutes Ende."
        ),
    )
    from eintragstypen.dienste import suchtext_aktualisieren

    suchtext_aktualisieren(vorhaben)
    return anhang


# --- Die Abnahme aus SPEC.md §13 ------------------------------------------


def test_abnahme_maerchen(client, lehrkraft, kapitel_mit_text, pdf_anhang):
    """Suche nach „Märchen“ findet Vorhaben, Kapitel 2.4 und die PDF."""
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("suche:suchen"), {"q": "Märchen"})
    inhalt = antwort.content.decode()

    assert antwort.status_code == 200
    # Das Vorhaben.
    assert "V-3-01" in inhalt
    assert "Märchen entdecken" in inhalt
    # Das Kapitel 2.4.
    assert "Leistungsbewertung und Leistungsrückmeldung" in inhalt
    # Die angehängte PDF.
    assert "Merkmale von Maerchen.pdf" in inhalt
    # Und die Gruppen sind benannt.
    assert "Arbeitspläne und Konzepte" in inhalt
    assert "Dateien" in inhalt


def test_abnahme_maerchen_im_dienst(lehrkraft, kapitel_mit_text, pdf_anhang):
    """Dasselbe eine Ebene tiefer, damit die Gruppen eindeutig geprüft sind."""
    ergebnis = dienste.suchen(lehrkraft, "Märchen")

    nach_gruppe = {g.schluessel: g for g in ergebnis.gruppen}
    eintragskennungen = {t.kennung for t in nach_gruppe["eintraege"].treffer}
    dateinamen = {t.titel for t in nach_gruppe["dateien"].treffer}

    assert "V-3-01" in eintragskennungen
    assert "2.4" in eintragskennungen
    assert "Merkmale von Maerchen.pdf" in dateinamen


# --- Volltext --------------------------------------------------------------


def test_deutsche_stammformen(lehrkraft, importierter_arbeitsplan):
    """„Märchens“ muss „Märchen“ finden – dafür ist die german-Konfiguration da."""
    ergebnis = dienste.suchen(lehrkraft, "Märchens")

    kennungen = {t.kennung for g in ergebnis.gruppen for t in g.treffer}
    assert "V-3-01" in kennungen


def test_suche_ueber_die_kennung(lehrkraft, importierter_arbeitsplan):
    ergebnis = dienste.suchen(lehrkraft, "V-3-01")

    kennungen = {t.kennung for g in ergebnis.gruppen for t in g.treffer}
    assert "V-3-01" in kennungen


def test_suche_findet_kompetenzen(lehrkraft, kompetenzen):
    ergebnis = dienste.suchen(lehrkraft, "SC2.02D")

    nach_gruppe = {g.schluessel: g for g in ergebnis.gruppen}
    assert "SC2.02D" in {t.kennung for t in nach_gruppe["kompetenzen"].treffer}


def test_suche_findet_beschluesse(lehrkraft, db):
    import datetime as dt

    from kern.models import Beschluss, Gremium

    gremium = Gremium.objects.create(name="Fachkonferenz Deutsch")
    Beschluss.objects.create(
        datum=dt.date(2026, 11, 9),
        gremium=gremium,
        titel="Arbeitsplan Deutsch, Kapitel 2.1",
        text="Die Fachkonferenz beschließt die Unterrichtsvorhaben für Jahrgang 3.",
    )

    ergebnis = dienste.suchen(lehrkraft, "Unterrichtsvorhaben Jahrgang")

    nach_gruppe = {g.schluessel: g for g in ergebnis.gruppen}
    assert nach_gruppe["beschluesse"].gesamt >= 1


def test_trefferausschnitt_ist_hervorgehoben(lehrkraft, importierter_arbeitsplan):
    ergebnis = dienste.suchen(lehrkraft, "Märchen")

    treffer = next(t for g in ergebnis.gruppen for t in g.treffer if t.kennung == "V-3-01")
    assert "<mark>" in treffer.ausschnitt


def test_kontext_zeigt_den_weg(lehrkraft, importierter_arbeitsplan):
    """„Arbeitsplan Deutsch › 2.1 Unterrichtsvorhaben › V-3-01“ (SPEC.md §9)."""
    ergebnis = dienste.suchen(lehrkraft, "Märchen")

    treffer = next(t for g in ergebnis.gruppen for t in g.treffer if t.kennung == "V-3-01")
    assert treffer.kontext.startswith("Arbeitsplan Deutsch")
    assert "Unterrichtsvorhaben" in treffer.kontext


# --- Rechte und Filter -----------------------------------------------------


def test_lesende_finden_keine_entwuerfe(lesend_nutzer, importierter_arbeitsplan):
    ergebnis = dienste.suchen(lesend_nutzer, "Märchen")

    kennungen = {t.kennung for g in ergebnis.gruppen for t in g.treffer}
    assert "V-3-01" not in kennungen


def test_lesende_finden_beschlossenes(lesend_nutzer, importierter_arbeitsplan):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    vorhaben.status = Status.BESCHLOSSEN
    vorhaben.save()

    ergebnis = dienste.suchen(lesend_nutzer, "Märchen")

    kennungen = {t.kennung for g in ergebnis.gruppen for t in g.treffer}
    assert "V-3-01" in kennungen


def test_beschlossenes_steht_vorn(lehrkraft, importierter_arbeitsplan, kapitel_mit_text):
    """Standard: beschlossene Inhalte zuerst (SPEC.md §9)."""
    kapitel = importierter_arbeitsplan.eintraege.get(kennung="2.4")
    kapitel.status = Status.BESCHLOSSEN
    kapitel.save()

    ergebnis = dienste.suchen(lehrkraft, "Märchen")
    eintraege = next(g for g in ergebnis.gruppen if g.schluessel == "eintraege")

    assert eintraege.treffer[0].kennung == "2.4"


def test_filter_nach_jahrgang(lehrkraft, importierter_arbeitsplan):
    mit = dienste.suchen(lehrkraft, "Märchen", jahrgang="3")
    ohne = dienste.suchen(lehrkraft, "Märchen", jahrgang="1")

    assert "V-3-01" in {t.kennung for g in mit.gruppen for t in g.treffer}
    eintraege_ohne = next(g for g in ohne.gruppen if g.schluessel == "eintraege")
    assert eintraege_ohne.gesamt == 0


def test_filter_nach_status(lehrkraft, importierter_arbeitsplan):
    ergebnis = dienste.suchen(lehrkraft, "Märchen", status=Status.BESCHLOSSEN)

    eintraege = next(g for g in ergebnis.gruppen if g.schluessel == "eintraege")
    assert eintraege.gesamt == 0


def test_nur_eine_gruppe_zeigen(lehrkraft, importierter_arbeitsplan):
    ergebnis = dienste.suchen(lehrkraft, "Märchen", gruppe="eintraege")

    assert [g.schluessel for g in ergebnis.gruppen] == ["eintraege"]


# --- Tippfehler und Autovervollständigung ---------------------------------


def test_tippfehler_werden_verziehen(lehrkraft, importierter_arbeitsplan):
    """Der Volltext findet „Maerchen“ nicht – die Ähnlichkeitssuche schon."""
    ergebnis = dienste.suchen(lehrkraft, "Maerchen")

    assert not ergebnis.leer
    assert ergebnis.ueber_aehnlichkeit
    assert "V-3-01" in {t.kennung for g in ergebnis.gruppen for t in g.treffer}


def test_unter_zwei_zeichen_wird_nicht_gesucht(lehrkraft, importierter_arbeitsplan):
    assert dienste.suchen(lehrkraft, "M").leer
    assert dienste.vorschlaege(lehrkraft, "M") == []


def test_vorschlaege_ueber_titel_und_kennung(lehrkraft, importierter_arbeitsplan):
    ueber_titel = dienste.vorschlaege(lehrkraft, "Märchen")
    ueber_kennung = dienste.vorschlaege(lehrkraft, "V-3")

    assert "V-3-01" in {v.kennung for v in ueber_titel}
    assert "V-3-01" in {v.kennung for v in ueber_kennung}


def test_vorschlaege_nehmen_kompetenzen_mit(lehrkraft, kompetenzen):
    gefunden = dienste.vorschlaege(lehrkraft, "SC2.02")

    assert "SC2.02D" in {v.kennung for v in gefunden}


def test_vorschlagsendpunkt_liefert_html(client, lehrkraft, importierter_arbeitsplan):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("suche:vorschlaege"), {"q": "Märchen"})

    assert antwort.status_code == 200
    assert "vorschlagsliste" in antwort.content.decode()


def test_suchseite_ohne_begriff_erklaert_sich(client, lehrkraft):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("suche:suchen"))

    assert antwort.status_code == 200
    assert "Inhalt angehängter Dateien" in antwort.content.decode()


# --- Eingaben, die nur aus Füllwörtern bestehen ---------------------------


def test_fuellwoerter_werden_erkannt():
    """Die deutsche Konfiguration wirft „es war einmal“ komplett weg."""
    assert dienste.hat_suchbegriffe("Märchen") is True
    assert dienste.hat_suchbegriffe("Gut und Böse") is True
    assert dienste.hat_suchbegriffe("Es war einmal") is False


def test_fuellwortsuche_findet_den_wortlaut(lehrkraft, pdf_anhang):
    """„Es war einmal“ ist eine plausible Suche – sie darf nicht ins Leere laufen."""
    ergebnis = dienste.suchen(lehrkraft, "Es war einmal")

    assert ergebnis.nur_wortlaut
    dateien = next(g for g in ergebnis.gruppen if g.schluessel == "dateien")
    assert "Merkmale von Maerchen.pdf" in {t.titel for t in dateien.treffer}


def test_fuellwortsuche_hebt_die_fundstelle_hervor(lehrkraft, pdf_anhang):
    ergebnis = dienste.suchen(lehrkraft, "Es war einmal")

    treffer = next(t for g in ergebnis.gruppen for t in g.treffer if t.titel.endswith(".pdf"))
    assert "<mark>Es war einmal</mark>" in treffer.ausschnitt


def test_suchseite_erklaert_die_wortlautsuche(client, lehrkraft, pdf_anhang):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("suche:suchen"), {"q": "Es war einmal"})

    assert "nach dem genauen Wortlaut" in antwort.content.decode()


def test_wortlautausschnitt_entschaerft_html():
    ergebnis = dienste.wortlaut_ausschnitt("<b>Es war einmal</b> ein König", "Es war einmal")

    assert "<b>" not in ergebnis
    assert "&lt;b&gt;" in ergebnis
    assert "<mark>Es war einmal</mark>" in ergebnis


# --- Genauigkeit der Kompetenzsuche ---------------------------------------


def test_kompetenzsuche_liefert_kein_rauschen(lehrkraft, kompetenzen):
    """Keine Kompetenzerwartung handelt von Märchen – also keine Treffer.

    Bei zu niedriger Ähnlichkeitsschwelle lieferte pg_trgm hier 68 Treffer:
    „Recherchen“ teilt genug Buchstabengruppen mit „Märchen“. Die begruben
    das eine richtige Ergebnis.
    """
    ergebnis = dienste.suchen(lehrkraft, "Märchen")

    kompetenzgruppe = next(g for g in ergebnis.gruppen if g.schluessel == "kompetenzen")
    assert kompetenzgruppe.gesamt == 0


def test_kompetenzsuche_verzeiht_echte_tippfehler(lehrkraft, kompetenzen):
    """„Gesprch“ statt „Gespräch“ muss weiterhin funktionieren."""
    ergebnis = dienste.suchen(lehrkraft, "Gesprch")

    kompetenzgruppe = next(g for g in ergebnis.gruppen if g.schluessel == "kompetenzen")
    assert kompetenzgruppe.gesamt > 0


def test_kompetenzsuche_findet_ueber_den_wortstamm(lehrkraft, kompetenzen):
    from fachdaten.suche import kompetenzen_finden

    assert kompetenzen_finden("Rechtschreibstrategien").count() > 0
    assert kompetenzen_finden("SC2.02").count() > 0
    assert kompetenzen_finden("Märchen").count() == 0


def test_auswahlmaske_zeigt_kein_rauschen(client, lehrkraft, kompetenzen):
    """Dasselbe im Auswahlfeld der Eingabemaske – dort wäre es schlimmer.

    Eine Lehrkraft, die „Märchen“ tippt und 40 unpassende Erwartungen sieht,
    hakt irgendeine davon an.
    """
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("fachdaten:suche"), {"q": "Märchen"})
    inhalt = antwort.content.decode()

    assert "treffer-knopf" not in inhalt
    assert "wurde nichts gefunden" in inhalt


def test_filter_gelten_auch_fuer_dateien(lehrkraft, pdf_anhang, importierter_arbeitsplan):
    """Sonst widersprächen sich die Gruppen: 0 Einträge, aber deren Anhang doch da."""
    ohne_filter = dienste.suchen(lehrkraft, "Märchen")
    mit_jahrgang_1 = dienste.suchen(lehrkraft, "Märchen", jahrgang="1")

    def dateien(ergebnis):
        return next(g for g in ergebnis.gruppen if g.schluessel == "dateien").gesamt

    assert dateien(ohne_filter) == 1
    assert dateien(mit_jahrgang_1) == 0


def test_filter_nach_dokument_schliesst_fremde_dateien_aus(lehrkraft, pdf_anhang, db):
    from kern.models import Dokument, Dokumenttyp

    typ, _ = Dokumenttyp.objects.get_or_create(schluessel="konzept", defaults={"name": "Konzept"})
    Dokument.objects.create(schluessel="anderes", titel="Anderes Dokument", dokumenttyp=typ)

    ergebnis = dienste.suchen(lehrkraft, "Märchen", dokument="anderes")

    assert ergebnis.leer
