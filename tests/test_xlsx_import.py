"""Import der Arbeitsmappe: Vorschau, Validierung, Übernahme."""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from deutsch.import_xlsx import pruefen_mappe, uebernehmen
from kern.models import Eintrag, Status, Verlinkungsart

pytestmark = pytest.mark.django_db


def test_beispielzeilen_werden_standardmaessig_uebersprungen(dokument, kompetenzen, arbeitsmappe):
    """SPEC.md §11: Zeilen mit „(Beispiel)“ im Titel überspringen."""
    bericht = pruefen_mappe(arbeitsmappe, dokument)

    assert bericht.saetze == []
    assert len(bericht.uebersprungen) == 2


def test_mit_beispielen_importiert_beide_zeilen(dokument, kompetenzen, arbeitsmappe):
    """SPEC.md §13: ich will die Beispielzeilen importieren können."""
    bericht = uebernehmen(arbeitsmappe, dokument, mit_beispielen=True)

    assert bericht.ok, bericht.als_text()
    assert bericht.geschrieben == 2
    assert bericht.neu == 2

    ritual = dokument.eintraege.get(kennung="R-01")
    vorhaben = dokument.eintraege.get(kennung="V-3-01")
    # Der Zusatz „(Beispiel)“ wird beim Import entfernt.
    assert ritual.titel == "Lesezeit"
    assert vorhaben.titel == "Märchen entdecken und zu Märchenmotiven schreiben"


def test_ritual_felder_kommen_vollstaendig_an(importierter_arbeitsplan):
    ritual = importierter_arbeitsplan.eintraege.get(kennung="R-01")

    assert ritual.eintragstyp == "ritual"
    assert ritual.status == Status.ENTWURF
    assert ritual.daten["einheiten_pro_woche"] == 3
    assert ritual.daten["minuten_je_einheit"] == 20
    # Berechnet, nicht aus der Mappe übernommen.
    assert ritual.daten["minuten_pro_woche"] == 60
    assert ritual.daten["leistung_bereich"] == "Sonstige Leistungen"
    assert "Lesezeit" in ritual.daten["kurzbeschreibung"]
    # Platzhalter „[…]“ der Arbeitsmappe sind kein Inhalt.
    assert "auspraegung_jg2" not in ritual.daten
    assert ritual.daten["auspraegung_jg1"].startswith("<p>")


def test_vorhaben_felder_kommen_vollstaendig_an(importierter_arbeitsplan):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")

    assert vorhaben.eintragstyp == "vorhaben"
    assert vorhaben.daten["jahrgang"] == 3
    assert vorhaben.daten["quartal"] == "Q2"
    assert vorhaben.daten["zeitumfang_std"] == 20
    assert vorhaben.daten["leistung_bereich"] == "Schriftliche Arbeiten"
    assert vorhaben.daten["klassenarbeit"] is True


def test_kompetenzverlinkungen_aus_der_id_liste(importierter_arbeitsplan):
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")

    schwerpunkte = set(
        vorhaben.verlinkungen.filter(art=Verlinkungsart.KOMPETENZ_SCHWERPUNKT).values_list(
            "ziel_id", flat=True
        )
    )
    beruehrt = set(
        vorhaben.verlinkungen.filter(art=Verlinkungsart.KOMPETENZ_BERUEHRT).values_list(
            "ziel_id", flat=True
        )
    )

    assert schwerpunkte == {"SC2.02D", "SC2.03D", "SC2.04D", "LE3.02K", "LE3.05D"}
    assert beruehrt == {"SZ2.02D", "SZ2.06D", "SC2.06D", "SP2.10D"}


def test_bezug_zu_ritual_wird_aufgeloest(importierter_arbeitsplan):
    """„Bezug zu Ritualen: R-01“ muss auf das Ritual zeigen, nicht auf Text."""
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    ritual = importierter_arbeitsplan.eintraege.get(kennung="R-01")

    bezug = vorhaben.verlinkungen.get(art=Verlinkungsart.BEZUG_RITUAL)
    assert bezug.ziel_id == str(ritual.pk)
    assert bezug.beschriftung.startswith("R-01")


def test_eintraege_haengen_unter_kapitel_2_1(importierter_arbeitsplan):
    sammelkapitel = importierter_arbeitsplan.eintraege.get(kennung="2.1")
    kinder = {k.kennung for k in sammelkapitel.kinder.all()}

    assert kinder == {"R-01", "V-3-01"}


def test_import_legt_eine_erste_fassung_an(importierter_arbeitsplan):
    ritual = importierter_arbeitsplan.eintraege.get(kennung="R-01")

    fassungen = list(ritual.versionen.all())
    assert len(fassungen) == 1
    assert fassungen[0].versionsnummer == 1
    assert fassungen[0].daten == ritual.daten
    # Auch die Verlinkungen stehen im Schnappschuss, sonst wäre ein Beschluss
    # nicht vollständig nachvollziehbar.
    assert len(fassungen[0].verlinkungen) == ritual.verlinkungen.count()


def test_zweiter_import_aktualisiert_und_legt_fassung_zwei_an(
    importierter_arbeitsplan, arbeitsmappe
):
    bericht = uebernehmen(arbeitsmappe, importierter_arbeitsplan, mit_beispielen=True)

    assert bericht.ok, bericht.als_text()
    assert bericht.neu == 0
    assert bericht.geschrieben == 2
    assert Eintrag.objects.filter(dokument=importierter_arbeitsplan).count() == 12

    ritual = importierter_arbeitsplan.eintraege.get(kennung="R-01")
    assert ritual.versionen.count() == 2


# --- Fehlerwege ------------------------------------------------------------


def _mappe_bauen(pfad, ritual_zeilen=(), vorhaben_zeilen=()):
    """Baut eine kleine Arbeitsmappe mit denselben Überschriften wie das Original."""
    mappe = Workbook()
    rituale = mappe.active
    rituale.title = "Rituale"
    rituale.append(
        [
            "ID",
            "Titel",
            "Status",
            "Kurzbeschreibung",
            "Einheiten pro Woche",
            "Minuten je Einheit",
            "Kompetenzen Schwerpunkt (IDs)",
        ]
    )
    for zeile in ritual_zeilen:
        rituale.append(zeile)

    vorhaben = mappe.create_sheet("Vorhaben")
    vorhaben.append(
        [
            "ID",
            "Titel",
            "Status",
            "Jahrgang",
            "Quartal",
            "Zeitumfang (Std.)",
            "Kurzbeschreibung / Produkt",
            "Kompetenzen Schwerpunkt (IDs)",
            "Bezug zu Ritualen (IDs)",
        ]
    )
    for zeile in vorhaben_zeilen:
        vorhaben.append(zeile)

    mappe.save(pfad)
    return pfad


def test_unbekannte_kompetenz_id_wird_gemeldet_und_nichts_geschrieben(
    dokument, kompetenzen, tmp_path
):
    pfad = _mappe_bauen(
        tmp_path / "mappe.xlsx",
        ritual_zeilen=[["R-09", "Erfundenes Ritual", "Entwurf", "Text", 1, 10, "XX9.99Z"]],
    )

    bericht = uebernehmen(pfad, dokument, mit_beispielen=True)

    assert not bericht.ok
    meldungen = " ".join(b.text for s in bericht.saetze for b in s.fehler)
    assert "XX9.99Z" in meldungen
    assert not dokument.eintraege.filter(kennung="R-09").exists()


def test_ungueltiger_wertelisten_wert_wird_gemeldet(dokument, kompetenzen, tmp_path):
    pfad = _mappe_bauen(
        tmp_path / "mappe.xlsx",
        vorhaben_zeilen=[
            ["V-3-09", "Falsches Quartal", "Entwurf", 3, "Q7", 10, "Text", "SC2.02D", ""]
        ],
    )

    bericht = uebernehmen(pfad, dokument, mit_beispielen=True)

    assert not bericht.ok
    meldungen = " ".join(b.text for s in bericht.saetze for b in s.fehler)
    assert "Q7" in meldungen
    assert not dokument.eintraege.filter(kennung="V-3-09").exists()


def test_doppelte_kennung_in_der_mappe_wird_gemeldet(dokument, kompetenzen, tmp_path):
    pfad = _mappe_bauen(
        tmp_path / "mappe.xlsx",
        ritual_zeilen=[
            ["R-09", "Erstes", "Entwurf", "Text", 1, 10, "SC2.02D"],
            ["R-09", "Zweites", "Entwurf", "Text", 1, 10, "SC2.02D"],
        ],
    )

    bericht = uebernehmen(pfad, dokument, mit_beispielen=True)

    assert not bericht.ok
    meldungen = " ".join(b.text for s in bericht.saetze for b in s.fehler)
    assert "mehrfach" in meldungen
    assert dokument.eintraege.filter(kennung="R-09").count() == 0


def test_fehlende_pflichtfelder_sind_nur_eine_warnung(dokument, kompetenzen, tmp_path):
    """Als Entwurf speichern muss immer möglich sein (SPEC.md §7.4)."""
    pfad = _mappe_bauen(
        tmp_path / "mappe.xlsx",
        ritual_zeilen=[["R-09", "Unfertig", "Entwurf", "Text", 1, 10, "SC2.02D"]],
    )

    bericht = uebernehmen(pfad, dokument, mit_beispielen=True)

    assert bericht.ok, bericht.als_text()
    assert bericht.anzahl_warnungen >= 1
    assert dokument.eintraege.filter(kennung="R-09").exists()


def test_verweis_auf_ritual_derselben_mappe_ist_kein_fehler(dokument, kompetenzen, tmp_path):
    """Das Ritual entsteht erst in diesem Lauf – die Vorschau muss es kennen."""
    pfad = _mappe_bauen(
        tmp_path / "mappe.xlsx",
        ritual_zeilen=[["R-09", "Neues Ritual", "Entwurf", "Text", 1, 10, "SC2.02D"]],
        vorhaben_zeilen=[
            ["V-3-09", "Nutzt R-09", "Entwurf", 3, "Q1", 10, "Text", "SC2.03D", "R-09"]
        ],
    )

    vorschau = pruefen_mappe(pfad, dokument, mit_beispielen=True)
    assert vorschau.ok, vorschau.als_text()

    bericht = uebernehmen(pfad, dokument, mit_beispielen=True)
    assert bericht.ok, bericht.als_text()
    vorhaben = dokument.eintraege.get(kennung="V-3-09")
    ritual = dokument.eintraege.get(kennung="R-09")
    assert vorhaben.verlinkungen.get(art=Verlinkungsart.BEZUG_RITUAL).ziel_id == str(ritual.pk)


def test_vorschau_schreibt_nichts(dokument, kompetenzen, arbeitsmappe):
    bericht = pruefen_mappe(arbeitsmappe, dokument, mit_beispielen=True)

    assert bericht.ok, bericht.als_text()
    assert len(bericht.saetze) == 2
    assert bericht.geschrieben == 0
    # Im Dokument stehen nur die zehn Kapitel der Gliederung.
    assert dokument.eintraege.count() == 10


def test_teildatensatz_laesst_fremde_verweise_stehen(importierter_arbeitsplan):
    """Ein Datensatz, der ein Verweisfeld nicht nennt, darf es nicht leeren.

    Das trifft den generischen JSON-Import: wer nur die Schwerpunkte schickt,
    will nicht die berührten Kompetenzen und die Ritualbezüge verlieren.
    """
    from eintragstypen.dienste import Rohsatz, pruefen, speichern

    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    vorher_beruehrt = vorhaben.verlinkungen.filter(art=Verlinkungsart.KOMPETENZ_BERUEHRT).count()
    assert vorher_beruehrt == 4

    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel=vorhaben.titel,
        daten=dict(vorhaben.daten),
        verweise={"kompetenzen_schwerpunkt": ["SC2.02D"]},
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))

    vorhaben.refresh_from_db()
    assert vorhaben.verlinkungen.filter(art=Verlinkungsart.KOMPETENZ_SCHWERPUNKT).count() == 1
    # Unberührt geblieben:
    assert vorhaben.verlinkungen.filter(art=Verlinkungsart.KOMPETENZ_BERUEHRT).count() == 4
    assert vorhaben.verlinkungen.filter(art=Verlinkungsart.BEZUG_RITUAL).count() == 1


def test_leere_liste_loescht_die_verweise_doch(importierter_arbeitsplan):
    """Ausdrücklich leer heißt leer – anders als „gar nicht genannt"."""
    from eintragstypen.dienste import Rohsatz, pruefen, speichern

    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    roh = Rohsatz(
        kennung="V-3-01",
        eintragstyp="vorhaben",
        titel=vorhaben.titel,
        daten=dict(vorhaben.daten),
        verweise={"kompetenzen_beruehrt": []},
    )
    speichern(importierter_arbeitsplan, pruefen(importierter_arbeitsplan, roh))

    vorhaben.refresh_from_db()
    assert vorhaben.verlinkungen.filter(art=Verlinkungsart.KOMPETENZ_BERUEHRT).count() == 0
    assert vorhaben.verlinkungen.filter(art=Verlinkungsart.KOMPETENZ_SCHWERPUNKT).count() == 5
