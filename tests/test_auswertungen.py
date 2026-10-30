"""Die übrigen Auswertungen aus SPEC.md §7.5."""

from __future__ import annotations

import pytest
from django.urls import reverse

from deutsch import auswertungen
from eintragstypen.dienste import Rohsatz, pruefen, speichern

pytestmark = pytest.mark.django_db

PASSWORT = "testpasswort-sehr-lang"


def anmelden(client, nutzer):
    assert client.login(email=nutzer.email, password=PASSWORT)
    return client


@pytest.fixture
def mit_vorhaben(importierter_arbeitsplan, kompetenzen):
    """Drei weitere Vorhaben, damit die Auswertungen etwas zu zeigen haben."""
    saetze = [
        ("V-3-02", 3, "Q1", 10, "Sonstige Leistungen", False),
        ("V-3-03", 3, "Q4", 15, "Schriftliche Arbeiten", True),
        ("V-4-01", 4, "Q2", 12, "Sonstige Leistungen", False),
    ]
    for kennung, jahrgang, quartal, stunden, bereich, klassenarbeit in saetze:
        roh = Rohsatz(
            kennung=kennung,
            eintragstyp="vorhaben",
            titel=f"Vorhaben {kennung}",
            daten={
                "jahrgang": jahrgang,
                "quartal": quartal,
                "zeitumfang_std": stunden,
                "leistung_bereich": bereich,
                "klassenarbeit": klassenarbeit,
                "leistung_form": "<p>Vortrag</p>",
                "leistung_kriterien": "<p>Kriterien</p>",
            },
        )
        speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))
    return importierter_arbeitsplan


# --- 7.5.2 Fahrplan --------------------------------------------------------


def test_fahrplan_sortiert_nach_quartal(mit_vorhaben):
    plan = auswertungen.fahrplan(mit_vorhaben, jahrgang=3)

    nach_quartal = {q.schluessel: [v.kennung for v in q.vorhaben] for q in plan.quartale}
    assert nach_quartal["Q1"] == ["V-3-02"]
    assert nach_quartal["Q2"] == ["V-3-01"]
    assert nach_quartal["Q4"] == ["V-3-03"]
    assert nach_quartal["Q3"] == []
    assert plan.anzahl_vorhaben == 3
    assert plan.stunden_gesamt == 20 + 10 + 15


def test_fahrplan_zeigt_nur_den_eigenen_jahrgang(mit_vorhaben):
    plan = auswertungen.fahrplan(mit_vorhaben, jahrgang=4)

    kennungen = [v.kennung for q in plan.quartale for v in q.vorhaben]
    assert kennungen == ["V-4-01"]


def test_fahrplan_nimmt_die_auspraegung_des_jahrgangs(mit_vorhaben):
    """R-01 hat nur für Jg. 1 und 4 eine Ausprägung – 2 und 3 sind „[…]“."""
    jg1 = auswertungen.fahrplan(mit_vorhaben, jahrgang=1)
    jg2 = auswertungen.fahrplan(mit_vorhaben, jahrgang=2)

    assert "Lautlesetandems" in jg1.rituale[0]["auspraegung"]
    assert jg2.rituale[0]["auspraegung"] == ""


# --- 7.5.3 Ritual-Progression ---------------------------------------------


def test_ritualprogression_hat_vier_spalten(importierter_arbeitsplan):
    progressionen = auswertungen.ritualprogressionen(importierter_arbeitsplan)

    assert len(progressionen) == 1
    progression = progressionen[0]
    assert [s.jahrgang for s in progression.spalten] == [1, 2, 3, 4]
    # Jahrgang 2 und 3 stehen in der Mappe als Platzhalter „[…]“.
    assert progression.offene_jahrgaenge == [2, 3]
    assert not progression.vollstaendig


def test_ritualprogression_wird_vollstaendig(importierter_arbeitsplan):
    ritual = importierter_arbeitsplan.eintraege.get(kennung="R-01")
    daten = dict(ritual.daten)
    daten["auspraegung_jg2"] = "<p>Silbentexte</p>"
    daten["auspraegung_jg3"] = "<p>Lesetandems</p>"
    roh = Rohsatz(kennung="R-01", eintragstyp="ritual", titel=ritual.titel, daten=daten)
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))

    progression = auswertungen.ritualprogressionen(importierter_arbeitsplan)[0]

    assert progression.vollstaendig
    assert progression.offene_jahrgaenge == []


# --- 7.5.4 Zeitbudget ------------------------------------------------------


def test_zeitbudget_rechnet_gegen_die_stundentafel(importierter_arbeitsplan):
    """R-01 bindet 60 Minuten; Jg. 1 hat 6 Stunden à 45 Min. = 270 Minuten."""
    budget = auswertungen.zeitbudget(importierter_arbeitsplan)

    assert budget.minuten_durch_rituale == 60
    jg1 = budget.zeilen[0]
    assert jg1.jahrgang == 1
    assert jg1.stunden_pro_woche == 6
    assert jg1.minuten_pro_woche == 270
    assert jg1.minuten_frei == 210
    assert jg1.anteil_prozent == 22.2
    assert not jg1.ueberbucht


def test_zeitbudget_meldet_ueberbuchung(importierter_arbeitsplan):
    dokument = importierter_arbeitsplan
    dokument.einstellungen = {"deutschstunden_pro_woche": {"1": 1, "2": 1, "3": 1, "4": 1}}
    dokument.save()

    budget = auswertungen.zeitbudget(dokument)

    assert budget.zeilen[0].ueberbucht
    assert budget.zeilen[0].minuten_frei == 45 - 60


def test_zeitbudget_nennt_rituale_ohne_zeitangabe(importierter_arbeitsplan, kompetenzen):
    roh = Rohsatz(kennung="R-02", eintragstyp="ritual", titel="Ohne Takt")
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))

    budget = auswertungen.zeitbudget(importierter_arbeitsplan)

    assert [r.kennung for r in budget.ohne_angabe] == ["R-02"]
    assert budget.minuten_durch_rituale == 60


# --- 7.5.5 Leistungsübersicht ---------------------------------------------


def test_leistungsuebersicht_zaehlt_klassenarbeiten(mit_vorhaben):
    uebersicht = auswertungen.leistungsuebersicht(mit_vorhaben)

    jg3 = uebersicht.jahrgaenge[2]
    assert jg3.jahrgang == 3
    assert len(jg3.zeilen) == 3
    # V-3-01 (aus der Mappe) und V-3-03 sind Klassenarbeiten.
    assert jg3.klassenarbeiten == 2
    assert jg3.schriftliche_arbeiten == 2


def test_leistungsuebersicht_nimmt_rituale_mit(mit_vorhaben):
    uebersicht = auswertungen.leistungsuebersicht(mit_vorhaben)

    assert len(uebersicht.rituale) == 1
    assert uebersicht.rituale[0].bereich == "Sonstige Leistungen"
    assert "Beobachtungsbogen" in uebersicht.rituale[0].form


def test_leistungsuebersicht_meldet_fehlenden_bereich(importierter_arbeitsplan, kompetenzen):
    roh = Rohsatz(
        kennung="V-2-01",
        eintragstyp="vorhaben",
        titel="Ohne Bereich",
        daten={"jahrgang": 2, "quartal": "Q1"},
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))

    uebersicht = auswertungen.leistungsuebersicht(importierter_arbeitsplan)

    assert "V-2-01" in {e.kennung for e in uebersicht.ohne_angabe}


# --- 7.5.6 Progressionspaare ----------------------------------------------


def test_progressionspaare_stehen_paarweise(importierter_arbeitsplan):
    paare = auswertungen.progressionspaare(importierter_arbeitsplan)

    # 52 Erwartungen mit Partner ergeben 26 Paare.
    assert len(paare) == 26
    for paar in paare:
        assert paar.sep.stufe == "S"
        assert paar.klasse4.stufe == "K"
        assert paar.sep.pk[:-1] == paar.klasse4.pk[:-1]


def test_progressionspaare_zeigen_luecken(importierter_arbeitsplan):
    """R-01 deckt LE1.03S und LE1.03K ab – das ist vollständig."""
    paare = auswertungen.progressionspaare(importierter_arbeitsplan)

    vollstaendig = [p for p in paare if p.beide_abgedeckt]
    assert {p.sep.pk for p in vollstaendig} == {"LE1.03S", "LE1.08S"}

    # LE3.02K ist abgedeckt, der Partner LE3.02S nicht.
    luecke = next(p for p in paare if p.klasse4.pk == "LE3.02K")
    assert luecke.luecke == "Schuleingangsphase fehlt"


# --- Filter und Oberfläche -------------------------------------------------


@pytest.mark.parametrize(
    "funktion",
    [
        auswertungen.ritualprogressionen,
        auswertungen.zeitbudget,
        auswertungen.leistungsuebersicht,
        auswertungen.progressionspaare,
    ],
)
def test_filter_nur_beschlossene_greift_ueberall(mit_vorhaben, funktion):
    """Mit „nur beschlossene" darf nichts erscheinen – beschlossen ist nichts."""
    ergebnis = funktion(mit_vorhaben, nur_beschlossene=True)

    if funktion is auswertungen.ritualprogressionen:
        assert ergebnis == []
    elif funktion is auswertungen.zeitbudget:
        assert ergebnis.minuten_durch_rituale == 0
    elif funktion is auswertungen.leistungsuebersicht:
        assert all(not j.zeilen for j in ergebnis.jahrgaenge)
    else:
        assert all(not p.beide_abgedeckt for p in ergebnis)


def test_alle_auswertungsseiten_laden(client, lehrkraft, mit_vorhaben):
    anmelden(client, lehrkraft)
    schluessel = mit_vorhaben.schluessel

    adressen = [
        reverse("deutsch:abdeckung", args=[schluessel]),
        reverse("deutsch:fahrplan", args=[schluessel, 3]),
        reverse("deutsch:ritualprogression", args=[schluessel]),
        reverse("deutsch:zeitbudget", args=[schluessel]),
        reverse("deutsch:leistung", args=[schluessel]),
        reverse("deutsch:progressionspaare", args=[schluessel]),
        reverse("deutsch:pruefliste", args=[schluessel]),
    ]

    for adresse in adressen:
        antwort = client.get(adresse)
        assert antwort.status_code == 200, adresse
        inhalt = antwort.content.decode()
        assert "{%" not in inhalt, adresse
        assert "{#" not in inhalt, adresse


def test_fahrplanseite_zeigt_die_vorhaben(client, lehrkraft, mit_vorhaben):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("deutsch:fahrplan", args=[mit_vorhaben.schluessel, 3]))
    inhalt = antwort.content.decode()

    assert "V-3-01" in inhalt
    assert "V-3-02" in inhalt
    assert "V-4-01" not in inhalt


def test_zeitbudgetseite_nutzt_den_punkt_als_dezimaltrenner(client, lehrkraft, mit_vorhaben):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("deutsch:zeitbudget", args=[mit_vorhaben.schluessel]))
    inhalt = antwort.content.decode()

    assert "width:22,2%" not in inhalt
    assert "width:22.2%" in inhalt


def test_auswertungen_beruecksichtigen_den_statusfilter(client, lehrkraft, mit_vorhaben):
    anmelden(client, lehrkraft)

    antwort = client.get(
        reverse("deutsch:leistung", args=[mit_vorhaben.schluessel]), {"stand": "beschlossen"}
    )

    assert "Für diesen Jahrgang ist noch nichts erfasst." in antwort.content.decode()
