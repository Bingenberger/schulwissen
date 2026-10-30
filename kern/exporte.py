"""Portable Datenausgaben und PDF aus freigegebenen Fassungen."""

import io
import json

from django.template.loader import render_to_string

from eintragstypen import html
from kern.models import Zieltyp
from kern.views import bloecke_zum_lesen, verweise_aus_schnappschuss


def gliederungsfolge(dokument):
    eintraege = list(dokument.eintraege.select_related("eltern").order_by("position", "kennung"))
    kinder = {}
    for e in eintraege:
        kinder.setdefault(e.eltern_id, []).append(e)
    ergebnis = []
    gesehen = set()

    def besuchen(e):
        if e.pk in gesehen:
            return
        gesehen.add(e.pk)
        ergebnis.append(e)
        for kind in kinder.get(e.pk, []):
            besuchen(kind)

    for e in kinder.get(None, []):
        besuchen(e)
    for e in eintraege:
        besuchen(e)
    return ergebnis


def dokument_json(dokument):
    alle = gliederungsfolge(dokument)
    kennungen = {str(e.pk): e.kennung for e in alle}
    eintraege = []
    beschluesse = {}
    for e in alle:
        zeile = {
            "kennung": e.kennung,
            "eintragstyp": e.eintragstyp,
            "titel": e.titel,
            "status": e.status,
            "daten": e.daten,
            "eltern": kennungen.get(str(e.eltern_id)),
            "position": e.position,
            "verantwortlich_text": e.verantwortlich_text,
            "fassung_stand": e.fassung_stand.isoformat() if e.fassung_stand else None,
            "verlinkungen": [v.als_schnappschuss() for v in e.verlinkungen.all()],
            "fassungen": [],
            "anhaenge": [_anhang(a) for a in e.anhaenge.all()],
        }
        for feld in e.typ.verlinkungsfelder:
            zeile[feld.schluessel] = [
                kennungen.get(v.ziel_id, v.ziel_id)
                if feld.zieltyp == Zieltyp.EINTRAG
                else v.ziel_id
                for v in e.verlinkungen.filter(feld=feld.schluessel)
            ]
        for v in e.versionen.select_related("beschluss", "beschluss__gremium", "autor"):
            zeile["fassungen"].append(
                {
                    "versionsnummer": v.versionsnummer,
                    "titel": v.titel,
                    "status": v.status,
                    "daten": v.daten,
                    "verlinkungen": v.verlinkungen,
                    "autor": v.autor.email if v.autor else None,
                    "zeitpunkt": v.zeitpunkt.isoformat(),
                    "beschluss": v.beschluss_id,
                }
            )
            if v.beschluss:
                b = v.beschluss
                beschluesse[b.pk] = {
                    "id": b.pk,
                    "datum": b.datum.isoformat(),
                    "gremium": b.gremium.name,
                    "titel": b.titel,
                    "text": b.text,
                }
        eintraege.append(zeile)
    return json.dumps(
        {
            "schema_version": 1,
            "dokument": dokument.schluessel,
            "metadaten": {
                "titel": dokument.titel,
                "dokumenttyp": dokument.dokumenttyp.schluessel,
                "fach": dokument.fach,
                "beschreibung": dokument.beschreibung,
                "gueltig_ab_schuljahr": dokument.gueltig_ab_schuljahr,
                "einstellungen": dokument.einstellungen,
            },
            "eintraege": eintraege,
            "beschluesse": list(beschluesse.values()),
            "anhaenge": [_anhang(a) for a in dokument.anhaenge.filter(eintrag__isnull=True)],
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def _anhang(a):
    return {
        "dateiname": a.dateiname,
        "beschreibung": a.beschreibung,
        "datei": a.datei.name,
        "nextcloud_pfad": a.nextcloud_pfad,
        "nextcloud_link": a.nextcloud_link,
        "mimetype": a.mimetype,
        "groesse": a.groesse,
    }


def dokument_xlsx(dokument):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    from eintragstypen.registry import registry

    mappe = Workbook()
    mappe.remove(mappe.active)
    kennungen = {str(e.pk): e.kennung for e in dokument.eintraege.all()}
    for schluessel in ("ritual", "vorhaben"):
        typ = registry.holen(schluessel)
        blatt = mappe.create_sheet(typ.xlsx_blatt)
        felder = list(typ.felder)
        blatt.append(
            [
                "ID",
                "Titel",
                "Status",
                "Verantwortlich (Gruppe/Person)",
                "Fassung / Stand",
                *[f.xlsx_spalten[0] if f.xlsx_spalten else f.label for f in felder],
            ]
        )
        for zelle in blatt[1]:
            zelle.font = Font(bold=True)
        for e in dokument.eintraege.filter(eintragstyp=schluessel).order_by("position", "kennung"):
            werte = [e.kennung, e.titel, e.status, e.verantwortlich_text, e.fassung_stand]
            for feld in felder:
                if feld.ist_verlinkung:
                    werte.append(
                        "; ".join(
                            kennungen.get(v.ziel_id, v.ziel_id)
                            if feld.zieltyp == Zieltyp.EINTRAG
                            else v.ziel_id
                            for v in e.verlinkungen.filter(feld=feld.schluessel)
                        )
                    )
                else:
                    werte.append(e.daten.get(feld.schluessel))
            blatt.append(werte)
            # Benutzertext bleibt Text, auch wenn er mit einem Gleichheitszeichen beginnt.
            for zelle in blatt[blatt.max_row]:
                if isinstance(zelle.value, str):
                    zelle.data_type = "s"
        blatt.freeze_panes = "C2"
        blatt.auto_filter.ref = blatt.dimensions
        for spalte in blatt.columns:
            blatt.column_dimensions[spalte[0].column_letter].width = 24
    ausgabe = io.BytesIO()
    mappe.save(ausgabe)
    return ausgabe.getvalue()


def pdf_zeile(eintrag, version=None):
    daten = version.daten if version else eintrag.daten
    if version:
        verweise = verweise_aus_schnappschuss(version)
        titel = version.titel
    else:
        verweise = {}
        for v in eintrag.verlinkungen.all():
            verweise.setdefault(v.feld, []).append(v)
        titel = eintrag.titel
    bloecke = list(bloecke_zum_lesen(eintrag.typ, daten, verweise))
    # Auch administrativ eingespieltes Rich Text vor PDF-Ausgabe säubern.
    for block in bloecke:
        for feld in block["felder"]:
            if feld.get("html"):
                feld["html"] = html.saeubern(str(feld["html"]))
    return {
        "eintrag": eintrag,
        "titel": titel,
        "bloecke": bloecke,
        "beschluss": version.beschluss if version else None,
        "version": version,
    }


def beschlossener_stand(dokument):
    ergebnis = []
    for e in gliederungsfolge(dokument):
        v = e.beschlossene_version()
        if v:
            ergebnis.append(pdf_zeile(e, v))
    return ergebnis


def abdeckung_des_stands(zeilen, fach="deutsch"):
    from deutsch.auswertungen import Erwartungszeile
    from fachdaten.models import Kompetenzerwartung

    schwerpunkt, beruehrt = {}, {}
    for zeile in zeilen:
        for v in zeile["version"].verlinkungen:
            if v.get("ziel_typ") != Zieltyp.KOMPETENZ:
                continue
            ziel = (
                schwerpunkt
                if v["art"] == "kompetenz_schwerpunkt"
                else beruehrt
                if v["art"] == "kompetenz_beruehrt"
                else None
            )
            if ziel is not None:
                ziel.setdefault(v["ziel_id"], []).append(zeile["eintrag"])
    return [
        Erwartungszeile(
            erwartung=k,
            als_schwerpunkt=schwerpunkt.get(k.pk, []),
            nur_beruehrt=beruehrt.get(k.pk, []) if k.pk not in schwerpunkt else [],
        )
        for k in Kompetenzerwartung.objects.filter(fach=fach).order_by(
            "bereich", "schwerpunkt_nr", "id"
        )
    ]


def pdf_rendern(kontext):
    from weasyprint import HTML

    def keine_ressourcen(url, *args, **kwargs):
        # Der Export braucht keine externen Bilder, URLs oder lokalen Dateien.
        raise ValueError("Externe Ressourcen sind im PDF nicht vorgesehen.")

    quelle = render_to_string("kern/export_pdf.html", kontext)
    return HTML(string=quelle, url_fetcher=keine_ressourcen).write_pdf()


def dokument_pdf(dokument):
    zeilen = beschlossener_stand(dokument)
    return pdf_rendern(
        {
            "titel": dokument.titel,
            "dokument": dokument,
            "zeilen": zeilen,
            "matrix": abdeckung_des_stands(zeilen, dokument.fach or "deutsch")
            if dokument.ist_arbeitsplan
            else [],
        }
    )
