"""Verbindliche Anlagen als unveränderliche Freigabekopien, keine Live-Link-Freigabe."""

import hashlib
import io
import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse

from kern import rechte
from kern.models import Anhang, Eintragsversion, FreigegebeneDatei

MAX_BYTES = 20 * 1024 * 1024
MAX_GESAMT = 100 * 1024 * 1024


def originalstand(a):
    return hashlib.sha256(
        json.dumps(
            {
                "datei": a.datei.name,
                "name": a.dateiname,
                "beschreibung": a.beschreibung,
                "mimetype": a.mimetype,
                "fassung": a.dateiversion,
                "pfad": a.nextcloud_pfad,
                "link": a.nextcloud_link,
                "etag": a.nextcloud_etag,
                "verwendung": a.verwendung,
                "dokument": a.dokument_id,
                "eintrag": a.eintrag_id,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def lesen(a):
    if not a.datei:
        raise ValidationError(
            "Eine verbindliche Anlage benötigt eine hochgeladene, geprüfte Dateikopie. "
            "Ein veränderlicher Nextcloud-Link allein genügt nicht."
        )
    try:
        with a.datei.open("rb") as datei:
            inhalt = datei.read(MAX_BYTES + 1)
    except (OSError, ValueError) as fehler:
        raise ValidationError("Die verbindliche Dateifassung ist nicht lesbar.") from fehler
    if len(inhalt) > MAX_BYTES:
        raise ValidationError("Eine verbindliche Dateifassung darf höchstens 20 MiB groß sein.")
    return inhalt


def anhaenge(version):
    ids = set()
    for v in version.verlinkungen or []:
        if v.get("ziel_typ") == "anhang" and str(v.get("ziel_id", "")).isdigit():
            ids.add(int(v["ziel_id"]))
    if version.eintrag.eintragstyp == "prozess":
        from kern.prozessdaten import normalisieren

        try:
            graph = normalisieren(version.daten.get("ablauf"))
        except ValidationError:
            graph = {"knoten": []}
        ids.update(v["id"] for k in graph["knoten"] for v in k["verweise"] if v["typ"] == "anhang")
    return Anhang.objects.filter(Q(eintrag=version.eintrag) | Q(pk__in=ids)).order_by("pk")


def zugang(nutzer, a):
    # Die Quelle bleibt rechtsgebunden, auch wenn ihre Arbeitsdatei geändert wurde.
    return (not a.dokument_id or rechte.darf_dokument_lesen(nutzer, a.dokument)) and (
        not a.eintrag_id or rechte.darf_dokument_lesen(nutzer, a.eintrag.dokument)
    )


def pruefen(version, nutzer=None):
    gesamt = 0
    for a in anhaenge(version).filter(verwendung="verbindlich"):
        if nutzer is not None and not zugang(nutzer, a):
            raise PermissionDenied("Eine verbindliche Anlage ist nicht zugänglich.")
        if (a.nextcloud_link or a.nextcloud_pfad) and not a.dateiversion:
            raise ValidationError(
                "Für eine externe verbindliche Anlage fehlt der Versionsnachweis."
            )
        gesamt += len(lesen(a))
        if gesamt > MAX_GESAMT:
            raise ValidationError("Die verbindlichen Anlagen überschreiten zusammen 100 MiB.")


def sichern(version):
    gesamt = 0
    for a in anhaenge(version).filter(verwendung="verbindlich"):
        if version.dateifassungen.filter(original=a).exists():
            continue
        inhalt = lesen(a)
        gesamt += len(inhalt)
        if gesamt > MAX_GESAMT:
            raise ValidationError("Die verbindlichen Anlagen überschreiten zusammen 100 MiB.")
        if (a.nextcloud_link or a.nextcloud_pfad) and not a.dateiversion:
            raise ValidationError(
                "Für eine externe verbindliche Anlage fehlt der Versionsnachweis."
            )
        FreigegebeneDatei.objects.create(
            version=version,
            original=a,
            dateiname=a.dateiname,
            dateiversion=a.dateiversion,
            mimetype=a.mimetype,
            inhalt=inhalt,
            sha256=hashlib.sha256(inhalt).hexdigest(),
            originalstand=originalstand(a),
        )


def karte(kopie, nutzer):
    a = kopie.original
    if not zugang(nutzer, a):
        return {"label": "Dateifassung derzeit nicht zugänglich", "url": ""}
    geaendert = originalstand(a) != kopie.originalstand
    try:
        geaendert = geaendert or hashlib.sha256(lesen(a)).hexdigest() != kopie.sha256
    except ValidationError:
        geaendert = True
    return {
        "label": kopie.dateiname,
        "url": reverse("kern:dateifassung", args=[kopie.pk]),
        "art": "Verbindliche Freigabekopie",
        "sha256": kopie.sha256,
        "pruefhinweis": (
            (
                "Das Original hat sich geändert oder ist nicht verfügbar. Du "
                "öffnest die gesicherte Freigabefassung."
            )
            if geaendert
            else (
                "Du öffnest die gesicherte Freigabefassung; spätere Änderungen "
                "der Quelle ändern diese Kopie nicht."
            )
        )
        + (f" Versionsnachweis: {kopie.dateiversion}" if kopie.dateiversion else ""),
    }


@login_required
def download(request, pk):
    kopie = get_object_or_404(
        FreigegebeneDatei.objects.select_related(
            "version__eintrag__dokument", "original__dokument", "original__eintrag__dokument"
        ),
        pk=pk,
        version__in=rechte.sichtbare_versionen(request.user, Eintragsversion.objects.all()),
    )
    if not zugang(request.user, kopie.original):
        raise PermissionDenied
    inhalt = bytes(kopie.inhalt)
    if hashlib.sha256(inhalt).hexdigest() != kopie.sha256:
        raise PermissionDenied("Die Integritätsprüfung der Freigabekopie ist fehlgeschlagen.")
    r = FileResponse(
        io.BytesIO(inhalt),
        as_attachment=True,
        filename=kopie.dateiname,
        content_type="application/octet-stream",
    )
    r["Cache-Control"] = "private, no-store"
    r["X-Content-Type-Options"] = "nosniff"
    return r
