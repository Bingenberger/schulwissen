"""AP01: Alle Zugänge verwenden Inhalte und Metadaten derselben Lesefassung."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from eintragstypen.dienste import Rohsatz, pruefen, speichern
from kern import beschluesse, exporte, rechte
from kern.models import (
    Anhang,
    Beschluss,
    Eintrag,
    Eintragsversion,
    Gremium,
    Kommentar,
    Status,
    Verlinkung,
    Zieltyp,
)
from kern.staende import lesestand, sichtbare_anhaenge
from suche import dienste

pytestmark = pytest.mark.django_db


def schreiben(dokument, kennung, titel, daten=None, typ="grundlagenkapitel"):
    if daten is None:
        daten = {"text": titel} if typ == "grundlagenkapitel" else {}
    befund = pruefen(
        dokument,
        Rohsatz(kennung=kennung, eintragstyp=typ, titel=titel, daten=daten),
    )
    assert befund.ok, befund.fehler
    return speichern(dokument, befund)


def freigeben(eintrag):
    gremium, _ = Gremium.objects.get_or_create(name="Testkonferenz")
    beschluss = Beschluss.objects.create(
        datum=date(2026, 10, 31), gremium=gremium, titel="Testfreigabe"
    )
    beschluesse.beschluss_fassen(beschluss, [eintrag])
    return eintrag.beschlossene_version()


@pytest.fixture
def staende(dokument):
    eltern = schreiben(dokument, "K-80", "Gültiger Kapitelname")
    freigeben(eltern)
    e = schreiben(
        dokument, "V-3-80", "Akkordeonwissen", {"jahrgang": 3, "quartal": "Q1"}, "vorhaben"
    )
    e.eltern = eltern
    e.save()
    version = freigeben(e)
    e = schreiben(
        dokument, e.kennung, "Xylophonfundus", {"jahrgang": 4, "quartal": "Q4"}, "vorhaben"
    )
    schreiben(dokument, eltern.kennung, "Unveröffentlichter Kapitelname")
    return e, version


@pytest.mark.parametrize("begriff", ["Akkordeonwissen", "V-3-80", "Akkordeonwisen"])
def test_suche_zeigt_freigegebenen_titel_status_und_kontext(lesend_nutzer, staende, begriff):
    e, _ = staende
    ergebnis = dienste.suchen(lesend_nutzer, begriff, gruppe="eintraege")
    treffer = next(t for t in ergebnis.gruppen[0].treffer if t.kennung == e.kennung)
    assert treffer.titel == "Akkordeonwissen"
    assert treffer.status == Status.BESCHLOSSEN
    assert treffer.status_text == "beschlossen"
    assert "Gültiger Kapitelname" in treffer.kontext
    assert "Unveröffentlicht" not in treffer.kontext
    assert "Xylophon" not in treffer.ausschnitt


def test_arbeitsbegriffe_liefern_lesenden_auch_keine_trefferzahlen(
    lesend_nutzer, lehrkraft, staende
):
    assert dienste.suchen(lesend_nutzer, "Xylophonfundus", gruppe="eintraege").gesamt == 0
    assert dienste.vorschlaege(lesend_nutzer, "Xylophonfundus") == []
    assert dienste.suchen(lehrkraft, "Xylophonfundus", gruppe="eintraege").gesamt == 1
    assert dienste.suchen(lehrkraft, "Akkordeonwissen", gruppe="eintraege").gesamt == 0


def test_filter_und_vorschlaege_verwenden_lesestand(lesend_nutzer, staende):
    e, _ = staende
    assert (
        dienste.suchen(
            lesend_nutzer, e.kennung, jahrgang="3", status=Status.BESCHLOSSEN, gruppe="eintraege"
        ).gesamt
        == 1
    )
    assert dienste.suchen(lesend_nutzer, e.kennung, jahrgang="4", gruppe="eintraege").gesamt == 0
    assert (
        dienste.suchen(lesend_nutzer, e.kennung, status=Status.ENTWURF, gruppe="eintraege").gesamt
        == 0
    )
    v = next(t for t in dienste.vorschlaege(lesend_nutzer, e.kennung) if t.kennung == e.kennung)
    assert v.titel == "Akkordeonwissen" and v.status == Status.BESCHLOSSEN


def test_wortlautsuche_durchsucht_nur_den_lesestand(dokument, lesend_nutzer, lehrkraft):
    e = schreiben(dokument, "K-81", "Füllwortbeispiel", {"text": "Es war einmal"})
    freigeben(e)
    schreiben(dokument, e.kennung, "Füllwortbeispiel", {"text": "Und wenn aber"})
    assert dienste.suchen(lesend_nutzer, "Es war einmal", gruppe="eintraege").gesamt == 1
    assert dienste.suchen(lesend_nutzer, "Und wenn aber", gruppe="eintraege").gesamt == 0
    assert dienste.suchen(lehrkraft, "Und wenn aber", gruppe="eintraege").gesamt == 1


@pytest.mark.parametrize("ansicht", ["kern:eintrag", "kern:dokument", "kern:startseite"])
def test_html_verraet_keine_entwurfstitel(client, lesend_nutzer, staende, ansicht):
    e, _ = staende
    client.force_login(lesend_nutzer)
    args = (
        [e.dokument.schluessel, e.kennung]
        if ansicht == "kern:eintrag"
        else [e.dokument.schluessel]
        if ansicht == "kern:dokument"
        else []
    )
    antwort = client.get(reverse(ansicht, args=args))
    assert antwort.status_code == 200
    text = antwort.content.decode()
    assert "Akkordeonwissen" in text
    assert "Xylophonfundus" not in text
    assert "Unveröffentlichter Kapitelname" not in text


def test_rueckverweise_kommen_aus_der_freigegebenen_fassung(
    client, dokument, lesend_nutzer, lehrkraft
):
    ziel = schreiben(dokument, "K-82", "Zielkapitel")
    freigeben(ziel)
    quelle = schreiben(dokument, "K-83", "Freigegebene Quelle")
    Verlinkung.objects.create(
        von_eintrag=quelle, ziel_typ=Zieltyp.EINTRAG, ziel_id=str(ziel.pk), art="verweist_auf"
    )
    quelle.version_anlegen()
    freigeben(quelle)
    quelle.verlinkungen.all().delete()
    schreiben(dokument, quelle.kennung, "Versteckte neue Quellenbezeichnung")
    geheim = schreiben(dokument, "K-84", "Versteckte neue Verknüpfung")
    Verlinkung.objects.create(
        von_eintrag=geheim, ziel_typ=Zieltyp.EINTRAG, ziel_id=str(ziel.pk), art="verweist_auf"
    )
    client.force_login(lesend_nutzer)
    antwort = client.get(reverse("kern:eintrag", args=[dokument.schluessel, ziel.kennung]))
    text = antwort.content.decode()
    assert "Freigegebene Quelle" in text
    assert "Versteckte" not in text
    client.force_login(lehrkraft)
    antwort = client.get(reverse("kern:eintrag", args=[dokument.schluessel, ziel.kennung]))
    assert [v.von_eintrag.pk for v in antwort.context["rueckverweise"]] == [geheim.pk]


def test_neue_entwurfsverknuepfung_einer_freigegebenen_quelle_bleibt_verborgen(
    client, dokument, lesend_nutzer
):
    ziel = schreiben(dokument, "K-85", "Zielkapitel")
    freigeben(ziel)
    quelle = schreiben(dokument, "K-86", "Andere gültige Quelle")
    freigeben(quelle)
    schreiben(dokument, quelle.kennung, "Vertraulicher Quellenentwurf")
    Verlinkung.objects.create(
        von_eintrag=quelle, ziel_typ=Zieltyp.EINTRAG, ziel_id=str(ziel.pk), art="verweist_auf"
    )
    client.force_login(lesend_nutzer)
    antwort = client.get(reverse("kern:eintrag", args=[dokument.schluessel, ziel.kennung]))
    assert antwort.context["rueckverweise"] == []


def test_dateisuche_anzeige_und_download_haben_dieselben_rechte(
    client, settings, tmp_path, dokument, lesend_nutzer, lehrkraft
):
    settings.MEDIA_ROOT = tmp_path
    e = schreiben(dokument, "K-87", "Gültiger Anhangkontext")
    alt = Anhang.objects.create(
        eintrag=e,
        dokument=dokument,
        dateiname="Lesematerial.txt",
        extrahierter_text="Akkordeonwissen",
        datei=SimpleUploadedFile("alt.txt", b"ok"),
    )
    freigeben(e)
    schreiben(dokument, e.kennung, "Geheimer Anhangkontext")
    neu = Anhang.objects.create(
        eintrag=e,
        dokument=dokument,
        dateiname="Geheimdatei.txt",
        extrahierter_text="Xylophonfundus",
        datei=SimpleUploadedFile("neu.txt", b"geheim"),
    )
    client.force_login(lesend_nutzer)
    assert client.get(alt.datei.url).status_code == 200
    assert client.get(neu.datei.url).status_code == 404
    antwort = client.get(reverse("kern:eintrag", args=[dokument.schluessel, e.kennung]))
    assert "Lesematerial.txt" in antwort.content.decode()
    assert "Geheimdatei" not in antwort.content.decode()
    ergebnis = dienste.suchen(lesend_nutzer, "Akkordeonwissen", gruppe="dateien")
    assert ergebnis.gesamt == 1
    assert ergebnis.gruppen[0].treffer[0].kontext == "Anhang zu K-87 Gültiger Anhangkontext"
    assert dienste.suchen(lesend_nutzer, "Xylophonfundus", gruppe="dateien").gesamt == 0
    client.force_login(lehrkraft)
    assert client.get(neu.datei.url).status_code == 200
    client.logout()
    assert client.get(alt.datei.url).status_code == 302
    # Änderung einer bereits bekannten Anlage ist ebenfalls Arbeitsstand.
    alt.beschreibung = "Vertrauliche Änderung"
    alt.save(update_fields=["beschreibung"])
    assert not sichtbare_anhaenge(lesend_nutzer, Anhang.objects.filter(pk=alt.pk)).exists()


def test_fassungszaehler_und_kommentare_enthalten_keine_arbeitsinformationen(
    client, lesend_nutzer, lehrkraft, staende
):
    e, _ = staende
    Kommentar.objects.create(eintrag=e, autor=lehrkraft, text="Vertraulicher Entwurfskommentar")
    client.force_login(lesend_nutzer)
    antwort = client.get(reverse("kern:eintrag", args=[e.dokument.schluessel, e.kennung]))
    assert antwort.context["anzahl_fassungen"] == 1
    assert "Vertraulicher Entwurfskommentar" not in antwort.content.decode()


def test_status_ohne_beschluss_schaltet_keinen_entwurf_frei(dokument, lesend_nutzer):
    e = schreiben(dokument, "K-88", "Nicht freigegeben")
    Eintragsversion.objects.create(
        eintrag=e, versionsnummer=99, titel="Unbelegt", status=Status.BESCHLOSSEN
    )
    assert not rechte.darf_lesen(lesend_nutzer, e)
    assert not rechte.sichtbare_eintraege(lesend_nutzer, Eintrag.objects.filter(pk=e.pk)).exists()
    assert lesestand(lesend_nutzer, e) is None


def test_pdf_und_abdeckungsdaten_verwenden_auch_freigegebene_eintragstitel(staende):
    e, version = staende
    zeile = next(z for z in exporte.beschlossener_stand(e.dokument) if z["eintrag"].pk == e.pk)
    assert zeile["titel"] == "Akkordeonwissen"
    assert zeile["eintrag"].titel == "Akkordeonwissen"
    assert zeile["eintrag"].daten == version.daten


def test_ruecknahme_reaktiviert_auch_den_passenden_suchindex(lesend_nutzer, staende):
    e, alt = staende
    neu = freigeben(e)
    assert dienste.suchen(lesend_nutzer, "Xylophonfundus", gruppe="eintraege").gesamt == 1
    beschluesse.beschluss_zuruecknehmen(neu.beschluss)
    assert dienste.suchen(lesend_nutzer, "Akkordeonwissen", gruppe="eintraege").gesamt == 1
    assert dienste.suchen(lesend_nutzer, "Xylophonfundus", gruppe="eintraege").gesamt == 0
    alt.refresh_from_db()
    assert alt.status == Status.BESCHLOSSEN


def test_suchbare_verweise_bleiben_beim_freigegebenen_schnappschuss(
    dokument, lesend_nutzer, lehrkraft
):
    e = schreiben(dokument, "K-89", "Verweisbeispiel")
    v = Verlinkung.objects.create(
        von_eintrag=e,
        ziel_typ=Zieltyp.KOMPETENZ,
        ziel_id="LE1.03S",
        art="verweist_auf",
        beschriftung="Akkordeonwissen",
    )
    e.version_anlegen()
    freigeben(e)
    v.beschriftung = "Xylophonfundus"
    v.save()
    schreiben(dokument, e.kennung, e.titel)
    assert dienste.suchen(lesend_nutzer, "Akkordeonwissen", gruppe="eintraege").gesamt == 1
    assert dienste.suchen(lesend_nutzer, "Xylophonfundus", gruppe="eintraege").gesamt == 0
    assert dienste.suchen(lehrkraft, "Xylophonfundus", gruppe="eintraege").gesamt == 1


def test_dokumentzaehlungen_enthalten_keine_versteckten_entwuerfe(client, lesend_nutzer, staende):
    e, _ = staende
    schreiben(e.dokument, "K-91", "Vertraulicher zusätzlicher Entwurf")
    client.force_login(lesend_nutzer)
    for url in [reverse("kern:startseite"), reverse("kern:dokumente")]:
        antwort = client.get(url)
        dokumente = (
            antwort.context["dokumente"] if url == "/" else antwort.context["seite"].object_list
        )
        assert next(d.anzahl for d in dokumente if d.pk == e.dokument_id) == 2


def test_freigabe_einer_quelle_verraet_keinen_zielentwurf(
    client, dokument, lesend_nutzer, lehrkraft
):
    ziel = schreiben(dokument, "R-95", "Xylophonfundus", typ="ritual")
    quelle = schreiben(
        dokument, "V-3-95", "Freigegebenes Verweisbeispiel", {"jahrgang": 3}, "vorhaben"
    )
    Verlinkung.objects.create(
        von_eintrag=quelle,
        ziel_typ=Zieltyp.EINTRAG,
        ziel_id=str(ziel.pk),
        art="bezug_ritual",
        feld="bezug_rituale",
        beschriftung="Xylophonfundus",
    )
    quelle.version_anlegen()
    version = freigeben(quelle)
    url = reverse("kern:eintrag", args=[dokument.schluessel, quelle.kennung])
    client.force_login(lesend_nutzer)
    assert "Xylophonfundus" not in client.get(url).content.decode()
    assert dienste.suchen(lesend_nutzer, "Xylophonfundus", gruppe="eintraege").gesamt == 0
    client.force_login(lehrkraft)
    assert "Xylophonfundus" in client.get(url).content.decode()
    # Nach Freigabe des Ziels dessen erlaubten Namen auflösen, nicht den alten Entwurfstitel.
    ziel = schreiben(dokument, ziel.kennung, "Akkordeonwissen", typ="ritual")
    freigeben(ziel)
    client.force_login(lesend_nutzer)
    text = client.get(url).content.decode()
    assert "Akkordeonwissen" in text and "Xylophonfundus" not in text
    text = client.get(
        reverse("kern:version", args=[dokument.schluessel, quelle.kennung, version.versionsnummer])
    ).content.decode()
    assert "Akkordeonwissen" in text and "Xylophonfundus" not in text
    version.refresh_from_db()
    assert version.verlinkungen[0]["beschriftung"] == "Xylophonfundus"


def test_freigegebener_vergleich_verraet_keine_versteckten_zielbeschriftungen(
    client, dokument, lesend_nutzer
):
    ziel = schreiben(dokument, "R-96", "Xylophonfundus", typ="ritual")
    quelle = schreiben(dokument, "V-3-96", "Quelle", {"jahrgang": 3}, "vorhaben")
    Verlinkung.objects.create(
        von_eintrag=quelle,
        ziel_typ=Zieltyp.EINTRAG,
        ziel_id=str(ziel.pk),
        art="bezug_ritual",
        feld="bezug_rituale",
        beschriftung="Xylophonfundus",
    )
    quelle.version_anlegen()
    freigeben(quelle)
    quelle.verlinkungen.all().delete()
    quelle = schreiben(dokument, quelle.kennung, "Neue Quelle", {"jahrgang": 3}, "vorhaben")
    freigeben(quelle)
    client.force_login(lesend_nutzer)
    antwort = client.get(reverse("kern:vergleich", args=[dokument.schluessel, quelle.kennung]))
    assert antwort.status_code == 200
    assert "Xylophonfundus" not in antwort.content.decode()
    assert antwort.context["vergleich"].verweise_weg == []


def test_fehlender_fassungsindex_faellt_nicht_auf_entwurfsindex_zurueck(lesend_nutzer, staende):
    _, version = staende
    Eintragsversion.objects.filter(pk=version.pk).update(suchvektor=None)
    assert dienste.suchen(lesend_nutzer, "Xylophonfundus", gruppe="eintraege").gesamt == 0
