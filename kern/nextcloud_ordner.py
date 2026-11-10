"""Vollständige Ordnerinventur; erst danach fehlende Dateien aus der Suche nehmen."""

from time import monotonic

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.utils import timezone

from kern import nextcloud
from kern.models import Anhang, NextcloudOrdner
from kern.suchindex import KONFIGURATION

MAX_ORDNER = 500
MAX_DATEIEN = 10000
MAX_SEKUNDEN = 60


def konfiguration(quelle):
    return quelle.pfad, quelle.unterordner, quelle.aktiv, quelle.geaendert_am


def inventur(quelle):
    """Ein Ausfall in einem Unterordner darf keine teilweise Löschung auslösen."""
    start = monotonic()
    wartend, besucht, dateien, unzugaenglich = [quelle.pfad], set(), {}, 0
    while wartend:
        if len(besucht) >= MAX_ORDNER or monotonic() - start > MAX_SEKUNDEN:
            raise nextcloud.NextcloudFehler("Die Ordnerinventur überschreitet die Laufgrenze.")
        pfad = wartend.pop()
        if pfad in besucht:
            continue
        besucht.add(pfad)
        try:
            kinder = nextcloud.auflisten(pfad)
        except nextcloud.NextcloudFehler as fehler:
            if fehler.status in (403, 404, 410):
                unzugaenglich += 1
                continue
            raise
        for datei in kinder:
            if (
                nextcloud._pfad_saeubern(datei.pfad) != datei.pfad
                or datei.pfad.rsplit("/", 1)[0] != pfad
                or len(datei.pfad) > 500 or len(datei.name) > 300
                or len(nextcloud.weblink(datei.pfad)) > 500
            ):
                raise nextcloud.NextcloudFehler("Die Nextcloud meldet einen ungültigen Dateipfad.")
            if datei.ist_ordner:
                if quelle.unterordner:
                    wartend.append(datei.pfad)
            else:
                dateien[datei.pfad] = datei
                if len(dateien) > MAX_DATEIEN:
                    raise nextcloud.NextcloudFehler("Der Suchordner enthält zu viele Dateien.")
    return dateien, unzugaenglich


def ordner_einlesen(quelle):
    stand, jetzt = konfiguration(quelle), timezone.now()
    fehler, dateien, unzugaenglich = "", None, 0
    try:
        dateien, unzugaenglich = inventur(quelle)
    except nextcloud.NextcloudFehler as problem:
        fehler = str(problem)[:500]
    with transaction.atomic():
        aktuell = NextcloudOrdner.objects.select_for_update().filter(pk=quelle.pk).first()
        if aktuell is None or not aktuell.aktiv or konfiguration(aktuell) != stand:
            return "Konfiguration geändert"
        aktuell.geprueft_am = jetzt
        aktuell.index_fehler = fehler
        if dateien is not None:
            bestand = {a.nextcloud_pfad: a for a in aktuell.dateien.all()}
            neu, geaendert = [], []
            for pfad, datei in dateien.items():
                vorhanden = bestand.get(pfad)
                daten = {
                    "dateiname": datei.name,
                    "groesse": datei.groesse or (vorhanden.groesse if vorhanden else 0),
                    "mimetype": (datei.mimetype or (vorhanden.mimetype if vorhanden else ""))[:120],
                    "nextcloud_link": nextcloud.weblink(pfad),
                    "beschreibung": f"{aktuell.name} › {pfad.rsplit('/', 1)[0]}"[:300],
                    "nextcloud_verfuegbar": True,
                    "nextcloud_inventur_etag": datei.etag[:500],
                }
                if (
                    vorhanden is None or not vorhanden.nextcloud_verfuegbar
                    or datei.etag != vorhanden.nextcloud_inventur_etag
                    or (datei.groesse and datei.groesse != vorhanden.groesse)
                ):
                    daten["nextcloud_geprueft_am"] = None
                if vorhanden is None:
                    neu.append(Anhang(nextcloud_ordner=aktuell, nextcloud_pfad=pfad, **daten))
                elif any(getattr(vorhanden, feld) != wert for feld, wert in daten.items()):
                    for feld, wert in daten.items():
                        setattr(vorhanden, feld, wert)
                    vorhanden.geaendert_am = jetzt
                    geaendert.append(vorhanden)
            Anhang.objects.bulk_create(neu, batch_size=500)
            Anhang.objects.bulk_update(geaendert, [
                "dateiname", "groesse", "mimetype", "nextcloud_link", "beschreibung",
                "nextcloud_verfuegbar", "nextcloud_inventur_etag", "nextcloud_geprueft_am",
                "geaendert_am",
            ], batch_size=500)
            Anhang.objects.filter(pk__in=[a.pk for a in neu + geaendert]).update(
                suchvektor=(
                    SearchVector("dateiname", weight="A", config=KONFIGURATION)
                    + SearchVector("beschreibung", weight="A", config=KONFIGURATION)
                    + SearchVector("extrahierter_text", weight="C", config=KONFIGURATION)
                ),
            )
            aktuell.dateien.exclude(nextcloud_pfad__in=dateien).update(
                nextcloud_verfuegbar=False, extrahierter_text="",
                suchvektor=None, nextcloud_etag="",
            )
            aktuell.index_stand = jetzt
            if unzugaenglich:
                aktuell.index_fehler = (
                    f"{unzugaenglich} Ordner nicht mehr zugänglich; "
                    "zugehörige Dateien ausgeblendet."
                )
        aktuell.save(update_fields=["geprueft_am", "index_stand", "index_fehler"])
    if dateien is None:
        return fehler or "Inventur fehlgeschlagen"
    return f"{len(dateien)} Dateien erfasst"
