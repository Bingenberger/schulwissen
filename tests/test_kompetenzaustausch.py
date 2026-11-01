"""Export und Import der Kompetenzerwartungen müssen zusammenpassen.

Der Export ist nur dann brauchbar, wenn er sich wieder importieren lässt: die
Schule pflegt ihre Festlegungen in einer Tabelle und spielt sie zurück.
"""

from __future__ import annotations

import io
import json

import pytest
from openpyxl import load_workbook

from fachdaten import exporte, lehrplan
from fachdaten.felder import UEBERSCHRIFTEN
from fachdaten.importe import MODUS_FESTLEGUNGEN, MODUS_LEHRPLAN, importieren
from fachdaten.models import Fach, Kompetenzerwartung

pytestmark = pytest.mark.django_db


# --- Die Lehrplandaten selbst ---------------------------------------------


def test_alle_faecher_des_sammelbands_sind_angelegt(lehrplanverzeichnis):
    """Die Migration legt die zehn Fächer des Sammelbands an."""
    namen = dict(Fach.objects.values_list("schluessel", "name"))
    assert namen["philosophie"] == "Praktische Philosophie"
    assert namen["religion-katholisch"] == "Katholische Religionslehre"
    assert namen["religion-evangelisch"] == "Evangelische Religionslehre"
    assert len(lehrplan.vorhandene_dateien()) == 10
    for fach in lehrplan.faecher():
        assert Fach.objects.get(schluessel=fach["schluessel"]).bereiche == fach["bereiche"]


def test_alle_faecher_lassen_sich_importieren(lehrplanverzeichnis):
    for fach, pfad in lehrplan.vorhandene_dateien():
        bericht = importieren(pfad, fach=fach)
        assert bericht.fehler == [], f"{fach}: {bericht.als_text()}"

    assert Kompetenzerwartung.objects.count() == sum(f["anzahl"] for f in lehrplan.faecher())
    # Jede Kennung gehört genau einem Fach, und kein Fach bleibt leer.
    for fach in lehrplan.faecher():
        assert Kompetenzerwartung.objects.filter(fach=fach["schluessel"]).count() == fach["anzahl"]


def test_progressionspartner_bleiben_im_eigenen_fach(lehrplanverzeichnis):
    for fach, pfad in lehrplan.vorhandene_dateien():
        importieren(pfad, fach=fach)

    for erwartung in Kompetenzerwartung.objects.exclude(progressionspartner=None):
        partner = erwartung.progressionspartner
        assert partner.fach == erwartung.fach
        assert partner.progressionspartner_id == erwartung.pk
        assert {erwartung.stufe, partner.stufe} == {"S", "K"}


# --- Export ----------------------------------------------------------------


def test_json_export_laesst_sich_wieder_importieren(kompetenzen):
    erwartung = Kompetenzerwartung.objects.filter(ua_weiterer_inhalt=True).first()
    erwartung.schulische_festlegung = "Bei uns: Streitschlichtungsgespräch"
    erwartung.save()

    rohdaten = exporte.als_json(Kompetenzerwartung.objects.all())
    saetze = json.loads(rohdaten.decode("utf-8"))
    nach_kennung = {satz["id"]: satz for satz in saetze}
    assert len(saetze) == 117
    assert nach_kennung[erwartung.pk]["schulischeFestlegung"] == (
        "Bei uns: Streitschlichtungsgespräch"
    )

    Kompetenzerwartung.objects.all().delete()
    bericht = importieren(saetze, fach="deutsch", modus=MODUS_LEHRPLAN)

    assert bericht.fehler == []
    assert bericht.angelegt == 117
    wieder = Kompetenzerwartung.objects.get(pk=erwartung.pk)
    assert wieder.text == erwartung.text
    assert wieder.progressionspartner_id == erwartung.progressionspartner_id
    # Die Lehrplanbetriebsart schreibt die schulische Spalte nicht mit.
    assert wieder.schulische_festlegung == ""


def test_xlsx_export_hat_die_spalten_des_imports(kompetenzen):
    mappe = load_workbook(io.BytesIO(exporte.als_xlsx(Kompetenzerwartung.objects.all())))
    blatt = mappe.active

    assert [zelle.value for zelle in blatt[1]] == list(UEBERSCHRIFTEN)
    assert blatt.max_row == 118


def test_csv_export_oeffnet_sich_in_excel(kompetenzen):
    rohdaten = exporte.als_csv(Kompetenzerwartung.objects.all()[:3])

    assert rohdaten.startswith(b"\xef\xbb\xbf"), "Excel braucht die Bytefolge am Anfang."
    kopf = rohdaten.decode("utf-8-sig").splitlines()[0]
    assert kopf.split(";")[0] == "Kennung"


# --- Import der schulischen Festlegungen ----------------------------------


def test_tabelle_mit_festlegungen_wird_zurueckgespielt(kompetenzen):
    offen = list(Kompetenzerwartung.objects.filter(ua_weiterer_inhalt=True)[:2])
    rohdaten = exporte.als_xlsx(Kompetenzerwartung.objects.all())
    mappe = load_workbook(io.BytesIO(rohdaten))
    blatt = mappe.active
    spalte = list(UEBERSCHRIFTEN).index("Schulische Festlegung") + 1
    kennungen = {offen[0].pk: "Fabeln", offen[1].pk: "Sachbuch zur Verkehrserziehung"}
    for zeile in blatt.iter_rows(min_row=2):
        if zeile[0].value in kennungen:
            blatt.cell(row=zeile[0].row, column=spalte, value=kennungen[zeile[0].value])
    puffer = io.BytesIO()
    mappe.save(puffer)

    from fachdaten.importe import saetze_aus_daten

    saetze = saetze_aus_daten("kompetenzen.xlsx", puffer.getvalue())
    bericht = importieren(saetze, fach="deutsch", modus=MODUS_FESTLEGUNGEN)

    assert bericht.fehler == []
    assert bericht.festlegungen == 2
    for kennung, text in kennungen.items():
        assert Kompetenzerwartung.objects.get(pk=kennung).schulische_festlegung == text


def test_festlegungsimport_laesst_den_lehrplan_unberuehrt(kompetenzen):
    vorher = Kompetenzerwartung.objects.get(pk="SZ1.04S")
    saetze = [
        {
            "id": "SZ1.04S",
            "text": "VERFÄLSCHT",
            "stufe": "K",
            "schulischeFestlegung": "Klassenrat",
        }
    ]

    bericht = importieren(saetze, fach="deutsch", modus=MODUS_FESTLEGUNGEN)

    assert bericht.fehler == []
    nachher = Kompetenzerwartung.objects.get(pk="SZ1.04S")
    assert nachher.text == vorher.text
    assert nachher.stufe == vorher.stufe
    assert nachher.schulische_festlegung == "Klassenrat"


def test_unbekannte_kennung_im_festlegungsimport_ist_ein_fehler(kompetenzen):
    bericht = importieren(
        [{"id": "SZ9.99X", "schulischeFestlegung": "Unsinn"}],
        fach="deutsch",
        modus=MODUS_FESTLEGUNGEN,
    )

    assert any("SZ9.99X" in fehler for fehler in bericht.fehler)
    assert Kompetenzerwartung.objects.filter(pk="SZ9.99X").count() == 0


def test_zu_lange_festlegung_wird_abgewiesen(kompetenzen):
    bericht = importieren(
        [{"id": "SZ1.04S", "schulischeFestlegung": "x" * 2001}],
        fach="deutsch",
        modus=MODUS_FESTLEGUNGEN,
    )

    assert bericht.fehler
    assert Kompetenzerwartung.objects.get(pk="SZ1.04S").schulische_festlegung == ""


def test_csv_ohne_kopfzeile_wird_erklaert():
    from fachdaten.importe import saetze_aus_daten

    with pytest.raises(ValueError, match="Spaltenüberschriften"):
        saetze_aus_daten("x.csv", b"SZ1.04S;Fabeln\n")


# --- Die Wege in der Oberfläche -------------------------------------------

PASSWORT = "testpasswort-sehr-lang"


def anmelden(client, nutzer):
    assert client.login(email=nutzer.email, password=PASSWORT)
    return client


@pytest.mark.parametrize(
    ("format", "typ"),
    [
        ("json", "application/json"),
        ("csv", "text/csv; charset=utf-8"),
        (
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    ],
)
def test_lehrkraft_laedt_die_gefilterte_auswahl_herunter(
    client, lehrkraft, kompetenzen, format, typ
):
    from django.urls import reverse

    anmelden(client, lehrkraft)

    antwort = client.get(reverse("fachdaten:export", args=[format]), {"bereich": "SZ"})

    assert antwort.status_code == 200
    assert antwort["Content-Type"] == typ
    assert "kompetenzerwartungen-deutsch" in antwort["Content-Disposition"]
    assert antwort.content


def test_uebersicht_gliedert_nach_bereich_und_schwerpunkt(client, lehrkraft, kompetenzen):
    from django.urls import reverse

    anmelden(client, lehrkraft)

    antwort = client.get(reverse("fachdaten:uebersicht"), {"fach": "deutsch"})
    seite = antwort.content.decode()

    assert antwort.status_code == 200
    assert "Mit anderen sprechen" in seite
    assert "Zuhörstrategien nutzen und verstehend zuhören" in seite
    # Ohne Importrecht steht der Importknopf nicht da.
    assert "Importieren</a>" not in seite


def test_lehrkraft_darf_nicht_importieren(client, lehrkraft):
    from django.urls import reverse

    anmelden(client, lehrkraft)

    antwort = client.get(reverse("fachdaten:import"))

    assert antwort.status_code == 403


def test_administration_prueft_und_uebernimmt_festlegungen(client, admin_nutzer, kompetenzen):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    anmelden(client, admin_nutzer)
    adresse = reverse("fachdaten:import")
    inhalt = json.dumps([{"id": "SZ1.04S", "schulischeFestlegung": "Klassenrat"}]).encode("utf-8")

    pruefung = client.post(
        adresse,
        {
            "fach": "deutsch",
            "modus": MODUS_FESTLEGUNGEN,
            "aktion": "vorschau",
            "datei": SimpleUploadedFile("festlegungen.json", inhalt),
        },
    )

    assert pruefung.status_code == 200
    assert "Die Datei ist in Ordnung" in pruefung.content.decode()
    # Die Vorschau schreibt nichts.
    assert Kompetenzerwartung.objects.get(pk="SZ1.04S").schulische_festlegung == ""

    uebernahme = client.post(
        adresse,
        {"fach": "deutsch", "modus": MODUS_FESTLEGUNGEN, "aktion": "uebernehmen"},
    )

    assert uebernahme.status_code == 302
    assert Kompetenzerwartung.objects.get(pk="SZ1.04S").schulische_festlegung == "Klassenrat"


def test_fehlerhafte_datei_laesst_sich_nicht_uebernehmen(client, admin_nutzer, kompetenzen):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    anmelden(client, admin_nutzer)
    adresse = reverse("fachdaten:import")
    inhalt = json.dumps([{"id": "GIBTSNICHT", "schulischeFestlegung": "x"}]).encode("utf-8")

    pruefung = client.post(
        adresse,
        {
            "fach": "deutsch",
            "modus": MODUS_FESTLEGUNGEN,
            "aktion": "vorschau",
            "datei": SimpleUploadedFile("festlegungen.json", inhalt),
        },
    )

    assert "Es wurde nichts geschrieben" in pruefung.content.decode()

    # Ohne geprüfte Datei gibt es nichts zu übernehmen.
    zweite = client.post(
        adresse, {"aktion": "uebernehmen", "fach": "deutsch", "modus": MODUS_FESTLEGUNGEN}
    )

    assert zweite.status_code == 200
    assert "Bitte eine Datei auswählen" in zweite.content.decode()


def test_datei_des_falschen_fachs_wird_abgewiesen(lehrplanverzeichnis):
    """Eine Sportdatei unter „Musik“ einzulesen wäre schwer zu bemerken."""
    pfad = lehrplan.datei_fuer("sport")

    bericht = importieren(pfad, fach="musik")

    assert any("sport" in fehler for fehler in bericht.fehler)
    assert Kompetenzerwartung.objects.count() == 0
