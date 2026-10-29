"""Die Oberfläche von außen: jede Seite lädt, der Ablauf funktioniert.

Der wichtigste Test ist ``test_lehrkraft_legt_vorhaben_an``: er geht genau den
Weg, den eine Lehrkraft am 9.11. gehen soll (SPEC.md §13, Abnahme).
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from kern.models import Status, Verlinkungsart

pytestmark = pytest.mark.django_db

PASSWORT = "testpasswort-sehr-lang"


def anmelden(client, nutzer):
    assert client.login(email=nutzer.email, password=PASSWORT)
    return client


# --- Anmeldung -------------------------------------------------------------


def test_startseite_verlangt_anmeldung(client):
    antwort = client.get(reverse("kern:startseite"))

    assert antwort.status_code == 302
    assert "anmelden" in antwort["Location"]


def test_anmeldeseite_laedt(client):
    antwort = client.get(reverse("kern:anmelden"))

    assert antwort.status_code == 200
    assert "E-Mail-Adresse" in antwort.content.decode()


def test_anmeldung_mit_email_funktioniert(client, lehrkraft):
    antwort = client.post(
        reverse("kern:anmelden"),
        {"username": lehrkraft.email, "password": PASSWORT},
    )

    assert antwort.status_code == 302
    assert antwort.wsgi_request.user.is_authenticated


def test_passwort_vergessen_schickt_mail(client, lehrkraft, mailoutbox):
    antwort = client.post(reverse("kern:passwort_zuruecksetzen"), {"email": lehrkraft.email})

    assert antwort.status_code == 302
    assert len(mailoutbox) == 1
    assert "Passwort" in mailoutbox[0].subject
    assert "passwort-neu/" in mailoutbox[0].body


# --- Seiten laden ----------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["kern:startseite", "fachdaten:uebersicht"],
)
def test_allgemeine_seiten_laden(client, lehrkraft, name):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse(name))

    assert antwort.status_code == 200


def test_dokumentseite_zeigt_gliederung(client, lehrkraft, importierter_arbeitsplan):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("kern:dokument", args=[importierter_arbeitsplan.schluessel]))
    inhalt = antwort.content.decode()

    assert antwort.status_code == 200
    assert "Rahmenbedingungen der fachlichen Arbeit" in inhalt
    assert "Leistungsbewertung und Leistungsrückmeldung" in inhalt
    assert "R-01" in inhalt
    assert "V-3-01" in inhalt


def test_eintragsansicht_zeigt_felder_und_kompetenzen(client, lehrkraft, importierter_arbeitsplan):
    anmelden(client, lehrkraft)

    antwort = client.get(
        reverse("kern:eintrag", args=[importierter_arbeitsplan.schluessel, "V-3-01"])
    )
    inhalt = antwort.content.decode()

    assert antwort.status_code == 200
    assert "Märchen entdecken" in inhalt
    # Kompetenzen im Klartext mit der Kennung als Schild (SPEC.md §7.4).
    assert "SC2.02D" in inhalt
    assert "Schriftliche Arbeiten" in inhalt
    # Der farbig abgesetzte Leistungsblock.
    assert "block-leistung" in inhalt


def test_eintragsansicht_nennt_offene_pflichtfelder(client, lehrkraft, importierter_arbeitsplan):
    anmelden(client, lehrkraft)

    antwort = client.get(
        reverse("kern:eintrag", args=[importierter_arbeitsplan.schluessel, "R-01"])
    )
    inhalt = antwort.content.decode()

    assert "Ausprägung Jg. 2" in inhalt
    assert "abgestimmt in Gruppe" in inhalt


def test_abdeckungsmatrix_zeigt_die_zahlen_der_arbeitsmappe(
    client, lehrkraft, importierter_arbeitsplan
):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("deutsch:abdeckung", args=[importierter_arbeitsplan.schluessel]))
    inhalt = antwort.content.decode()

    assert antwort.status_code == 200
    assert "Mit anderen sprechen" in inhalt
    assert "Gesamt" in inhalt
    assert ">117<" in inhalt


def test_pruefliste_laedt(client, lehrkraft, importierter_arbeitsplan):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("deutsch:pruefliste", args=[importierter_arbeitsplan.schluessel]))

    assert antwort.status_code == 200
    assert "Stufenzuordnung prüfen (61)" in antwort.content.decode()


def test_fassungen_laden(client, lehrkraft, importierter_arbeitsplan):
    anmelden(client, lehrkraft)

    antwort = client.get(
        reverse("kern:fassungen", args=[importierter_arbeitsplan.schluessel, "R-01"])
    )

    assert antwort.status_code == 200
    assert "Fassung" in antwort.content.decode()


# --- Kompetenzsuche --------------------------------------------------------


def test_kompetenzsuche_findet_ueber_kennung_und_wort(client, lehrkraft, kompetenzen):
    anmelden(client, lehrkraft)

    ueber_kennung = client.get(reverse("fachdaten:suche"), {"q": "SC2.02"})
    ueber_wort = client.get(reverse("fachdaten:suche"), {"q": "Märchen"})

    assert "SC2.02D" in ueber_kennung.content.decode()
    assert ueber_wort.status_code == 200


def test_kompetenzsuche_ist_tippfehlertolerant(client, lehrkraft, kompetenzen):
    """pg_trgm soll „Gesprch" statt „Gespräch" verzeihen (SPEC.md §9)."""
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("fachdaten:suche"), {"q": "Gesprch"})
    inhalt = antwort.content.decode()

    assert antwort.status_code == 200
    assert "treffer-knopf" in inhalt, "Es sollte trotz Tippfehler etwas gefunden werden."


def test_kompetenzsuche_verlangt_zwei_zeichen(client, lehrkraft, kompetenzen):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("fachdaten:suche"), {"q": "S"})

    assert "mindestens zwei Zeichen" in antwort.content.decode()


def test_kompetenzsuche_schlaegt_stufen_nach_jahrgang_vor(client, lehrkraft, kompetenzen):
    from fachdaten.models import Kompetenzerwartung

    anmelden(client, lehrkraft)

    jg1 = client.get(reverse("fachdaten:suche"), {"jahrgang": "1"})
    jg3 = client.get(reverse("fachdaten:suche"), {"jahrgang": "3"})

    # Jahrgang 1/2 → Stufen S und D, Jahrgang 3/4 → K und D (SPEC.md §7.4).
    def kennungen(antwort):
        inhalt = antwort.content.decode()
        return {
            e.pk for e in Kompetenzerwartung.objects.all() if f'data-kennung="{e.pk}"' in inhalt
        }

    stufen_jg1 = {k[-1] for k in kennungen(jg1)}
    stufen_jg3 = {k[-1] for k in kennungen(jg3)}

    assert stufen_jg1 == {"S", "D"}
    assert stufen_jg3 == {"K", "D"}
    # Der Hinweistext nennt die vorgeschlagenen Stufen.
    assert "Vorschlag für diesen Jahrgang" in jg1.content.decode()


def test_vorlagen_lassen_keine_kommentare_durch(client, lehrkraft, importierter_arbeitsplan):
    """Djangos {# … #} gilt nur je Zeile – mehrzeilig landet der Text auf der Seite."""
    anmelden(client, lehrkraft)

    seiten = [
        client.get(reverse("kern:startseite")),
        client.get(reverse("kern:dokument", args=[importierter_arbeitsplan.schluessel])),
        client.get(reverse("kern:eintrag", args=[importierter_arbeitsplan.schluessel, "V-3-01"])),
        client.get(
            reverse(
                "kern:eintrag_bearbeiten",
                args=[importierter_arbeitsplan.schluessel, "V-3-01"],
            )
        ),
        client.get(reverse("fachdaten:suche"), {"q": "Märchen"}),
        client.get(reverse("deutsch:abdeckung", args=[importierter_arbeitsplan.schluessel])),
    ]

    for antwort in seiten:
        inhalt = antwort.content.decode()
        assert "{#" not in inhalt, f"Kommentartext auf der Seite: {antwort.request['PATH_INFO']}"
        assert "{%" not in inhalt, f"Unaufgelöstes Tag: {antwort.request['PATH_INFO']}"
        assert "SPEC.md" not in inhalt, "Interne Verweise gehören nicht in die Oberfläche."


def test_kompetenzsuche_markiert_bereits_gewaehlte(client, lehrkraft, kompetenzen):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("fachdaten:suche"), {"q": "SC2.02", "gewaehlt": "SC2.02D"})

    assert "disabled" in antwort.content.decode()


# --- Der Abnahmeweg -------------------------------------------------------


def test_lehrkraft_legt_vorhaben_an(client, lehrkraft, arbeitsgruppe, dokument, kompetenzen):
    """Der Weg aus SPEC.md §13: Maske öffnen, ausfüllen, speichern, lesen."""
    lehrkraft.groups.add(arbeitsgruppe)
    anmelden(client, lehrkraft)

    # 1. Die Maske öffnen.
    maske = client.get(reverse("kern:eintrag_neu", args=[dokument.schluessel, "vorhaben"]))
    inhalt = maske.content.decode()
    assert maske.status_code == 200
    # Blöcke, Hilfetexte und die Pflichtmarkierung sind da.
    assert "Überblick" in inhalt
    assert "Kompetenzen" in inhalt
    assert "Verbindliche Zuordnung; ergibt den Fahrplan je Jahrgang." in inhalt
    assert "Speichern geht immer." in inhalt

    # 2. Ausfüllen und speichern.
    antwort = client.post(
        reverse("kern:eintrag_neu", args=[dokument.schluessel, "vorhaben"]),
        {
            "titel": "Gedichte lesen und sprechen",
            "f_kurzbeschreibung": "Gedichte kennenlernen, auswendig vortragen.",
            "f_jahrgang": "4",
            "f_quartal": "Q3",
            "f_zeitumfang_std": "12",
            "f_didaktik_methoden": "<p>Vortragstraining in Kleingruppen</p>",
            "f_differenzierung": "<p>Gedichte in drei Längen</p>",
            "f_leistung_bereich": "Sonstige Leistungen",
            "f_leistung_form": "<p>Gedichtvortrag</p>",
            "f_leistung_kriterien": "<p>Auswendig, Betonung, Haltung</p>",
            "f_klassenarbeit": "nein",
            "v_kompetenzen_schwerpunkt": "SZ2.02D, LE3.05D",
            "v_kompetenzen_beruehrt": "SP2.10D",
            "status": Status.ENTWURF,
        },
        follow=True,
    )

    assert antwort.status_code == 200
    vorhaben = dokument.eintraege.get(titel="Gedichte lesen und sprechen")
    # Die Kennung vergibt die App, mit dem Jahrgang darin.
    assert vorhaben.kennung == "V-4-01"
    assert vorhaben.status == Status.ENTWURF
    assert vorhaben.daten["jahrgang"] == 4
    assert vorhaben.daten["klassenarbeit"] is False
    # Die Verantwortung liegt bei der Arbeitsgruppe der Lehrkraft.
    assert vorhaben.verantwortlich_gruppe_id == arbeitsgruppe.pk
    # Das Vorhaben hängt unter Kapitel 2.1.
    assert vorhaben.eltern.kennung == "2.1"

    # 3. Die Kompetenzen sind als Verlinkung gespeichert, nicht als Text.
    schwerpunkte = set(
        vorhaben.verlinkungen.filter(art=Verlinkungsart.KOMPETENZ_SCHWERPUNKT).values_list(
            "ziel_id", flat=True
        )
    )
    assert schwerpunkte == {"SZ2.02D", "LE3.05D"}

    # 4. Es gibt eine erste Fassung und der Eintrag ist lesbar.
    assert vorhaben.versionen.count() == 1
    lesen = client.get(reverse("kern:eintrag", args=[dokument.schluessel, "V-4-01"]))
    assert "Gedichte lesen und sprechen" in lesen.content.decode()


def test_unvollstaendiges_vorhaben_wird_als_entwurf_gespeichert(
    client, lehrkraft, dokument, kompetenzen
):
    """Speichern muss immer gehen, mit Hinweis auf das Fehlende (SPEC.md §7.4)."""
    anmelden(client, lehrkraft)

    antwort = client.post(
        reverse("kern:eintrag_neu", args=[dokument.schluessel, "vorhaben"]),
        {
            "titel": "Erst mal notiert",
            "f_jahrgang": "2",
            "status": Status.ENTWURF,
        },
        follow=True,
    )
    inhalt = antwort.content.decode()

    assert dokument.eintraege.filter(titel="Erst mal notiert").exists()
    assert "Als Entwurf gespeichert" in inhalt
    assert "Kurzbeschreibung" in inhalt


def test_abgestimmt_scheitert_bei_fehlenden_pflichtfeldern(
    client, redaktion_nutzer, dokument, kompetenzen
):
    anmelden(client, redaktion_nutzer)

    antwort = client.post(
        reverse("kern:eintrag_neu", args=[dokument.schluessel, "vorhaben"]),
        {"titel": "Unfertig", "f_jahrgang": "3", "status": Status.ABGESTIMMT},
    )
    inhalt = antwort.content.decode()

    assert antwort.status_code == 200, "Die Maske soll wieder erscheinen."
    assert "erst, wenn alle Pflichtfelder gefüllt sind" in inhalt
    assert not dokument.eintraege.filter(titel="Unfertig").exists()


def test_lehrkraft_darf_status_abgestimmt_nicht_setzen(
    client, lehrkraft, arbeitsgruppe, importierter_arbeitsplan
):
    lehrkraft.groups.add(arbeitsgruppe)
    vorhaben = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    vorhaben.verantwortlich_gruppe = arbeitsgruppe
    vorhaben.save()
    anmelden(client, lehrkraft)

    antwort = client.post(
        reverse("kern:eintrag_bearbeiten", args=[importierter_arbeitsplan.schluessel, "V-3-01"]),
        {"titel": vorhaben.titel, "status": Status.ABGESTIMMT},
    )

    assert antwort.status_code == 200
    assert "nur die Redaktion oder die Administration" in antwort.content.decode()
    vorhaben.refresh_from_db()
    assert vorhaben.status == Status.ENTWURF


def test_lesend_kommt_nicht_an_entwuerfe(client, lesend_nutzer, importierter_arbeitsplan):
    anmelden(client, lesend_nutzer)

    antwort = client.get(
        reverse("kern:eintrag", args=[importierter_arbeitsplan.schluessel, "V-3-01"])
    )

    assert antwort.status_code == 403


def test_lesend_darf_nicht_bearbeiten(client, lesend_nutzer, importierter_arbeitsplan):
    eintrag = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    eintrag.status = Status.BESCHLOSSEN
    eintrag.save()
    anmelden(client, lesend_nutzer)

    lesen = client.get(
        reverse("kern:eintrag", args=[importierter_arbeitsplan.schluessel, "V-3-01"])
    )
    bearbeiten = client.get(
        reverse("kern:eintrag_bearbeiten", args=[importierter_arbeitsplan.schluessel, "V-3-01"])
    )

    assert lesen.status_code == 200
    assert "Bearbeiten</a>" not in lesen.content.decode()
    assert bearbeiten.status_code == 403


def test_kommentar_anlegen_und_erledigen(client, lehrkraft, importierter_arbeitsplan):
    anmelden(client, lehrkraft)
    adresse = reverse(
        "kern:kommentar_anlegen", args=[importierter_arbeitsplan.schluessel, "V-3-01"]
    )

    client.post(adresse, {"text": "Passt das Quartal wirklich?"})

    eintrag = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    kommentar = eintrag.kommentare.get()
    assert kommentar.text == "Passt das Quartal wirklich?"
    assert kommentar.autor == lehrkraft
    assert kommentar.erledigt is False

    client.post(
        reverse(
            "kern:kommentar_erledigen",
            args=[importierter_arbeitsplan.schluessel, "V-3-01", kommentar.pk],
        )
    )
    kommentar.refresh_from_db()
    assert kommentar.erledigt is True


def test_richtext_wird_gesaeubert(client, lehrkraft, dokument, kompetenzen):
    """Der Editor läuft beim Kollegium – das HTML darf nicht ungeprüft durch."""
    anmelden(client, lehrkraft)

    client.post(
        reverse("kern:eintrag_neu", args=[dokument.schluessel, "vorhaben"]),
        {
            "titel": "Mit Skript",
            "f_jahrgang": "3",
            "f_didaktik_methoden": (
                "<p>Erlaubt</p><script>alert(1)</script>"
                '<p><a href="javascript:alert(2)">Klick</a></p>'
                "<table><tr><td>Zelle</td></tr></table>"
            ),
            "status": Status.ENTWURF,
        },
    )

    eintrag = dokument.eintraege.get(titel="Mit Skript")
    gespeichert = eintrag.daten["didaktik_methoden"]
    assert "<script>" not in gespeichert
    assert "javascript:" not in gespeichert
    assert "<p>Erlaubt</p>" in gespeichert
    # Einfache Tabellen bleiben erhalten – Grundlagenkapitel brauchen sie.
    assert "<table>" in gespeichert


def test_anhang_hochladen(client, lehrkraft, arbeitsgruppe, importierter_arbeitsplan):
    from django.core.files.uploadedfile import SimpleUploadedFile

    lehrkraft.groups.add(arbeitsgruppe)
    eintrag = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    eintrag.verantwortlich_gruppe = arbeitsgruppe
    eintrag.save()
    anmelden(client, lehrkraft)

    client.post(
        reverse("kern:anhang_hochladen", args=[importierter_arbeitsplan.schluessel, "V-3-01"]),
        {
            "datei": SimpleUploadedFile(
                "Maerchenraster.txt", b"Raster fuer die Schreibkonferenz", "text/plain"
            ),
            "beschreibung": "Raster für die Schreibkonferenz",
        },
    )

    anhang = eintrag.anhaenge.get()
    assert anhang.dateiname == "Maerchenraster.txt"
    assert anhang.groesse > 0
    # Der Dateiname fließt in den Suchtext ein.
    eintrag.refresh_from_db()
    assert "Maerchenraster" in eintrag.suchtext


def test_gesundheit_ist_ohne_anmeldung_erreichbar(client):
    antwort = client.get(reverse("kern:gesundheit"))

    assert antwort.status_code == 200
    assert antwort.content == b"ok"


def test_klassenarbeit_steht_schon_in_der_neuen_maske(client, lehrkraft, dokument, kompetenzen):
    """Das Feld muss da sein, bevor der Jahrgang gewählt ist.

    Sonst erschiene „Klassenarbeit" erst nach dem ersten Speichern – die
    Lehrkraft würde es beim Anlegen nie sehen.
    """
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("kern:eintrag_neu", args=[dokument.schluessel, "vorhaben"]))
    inhalt = antwort.content.decode()

    assert "f_klassenarbeit" in inhalt
    # Im Browser ein- und ausgeblendet, abhängig vom Jahrgang.
    assert "includes(String(jahrgang))" in inhalt
    assert "'3', '4'" in inhalt


def test_klassenarbeit_bleibt_in_jahrgang_1_ohne_pflicht(client, lehrkraft, dokument, kompetenzen):
    """Serverseitig gilt das Feld weiter nur in Jahrgang 3 und 4."""
    anmelden(client, lehrkraft)

    antwort = client.post(
        reverse("kern:eintrag_neu", args=[dokument.schluessel, "vorhaben"]),
        {"titel": "Bilderbuch", "f_jahrgang": "1", "status": Status.ENTWURF},
        follow=True,
    )

    eintrag = dokument.eintraege.get(titel="Bilderbuch")
    offen = {f.schluessel for f in eintrag.typ.fehlende_pflichtfelder(eintrag.daten)}
    assert "klassenarbeit" not in offen
    assert "Als Entwurf gespeichert" in antwort.content.decode()


def test_anhangkapitel_behaelt_seine_kennung(client, lehrkraft, dokument):
    """Kapitel „A" wird nicht mitgezählt – es heißt A, nicht 5."""
    anmelden(client, lehrkraft)

    anhang = dokument.eintraege.get(kennung="A")
    assert anhang.anzeige_nummer == "A"

    antwort = client.get(reverse("kern:dokument", args=[dokument.schluessel]))
    assert ">A<" in antwort.content.decode()


def test_neuer_eintrag_ist_vorbelegt_als_entwurf(client, lehrkraft, dokument, kompetenzen):
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("kern:eintrag_neu", args=[dokument.schluessel, "vorhaben"]))
    inhalt = antwort.content.decode()

    assert '<option value="entwurf" selected>' in inhalt


def test_balkenbreite_nutzt_den_punkt_als_dezimaltrenner(
    client, lehrkraft, importierter_arbeitsplan
):
    """„width:0,0%" ist ungültiges CSS – der Balken wäre dann immer voll."""
    anmelden(client, lehrkraft)

    antwort = client.get(reverse("deutsch:abdeckung", args=[importierter_arbeitsplan.schluessel]))
    inhalt = antwort.content.decode()

    assert "width:0,0%" not in inhalt
    assert "width:0.0%" in inhalt
    assert "width:33.3%" in inhalt
