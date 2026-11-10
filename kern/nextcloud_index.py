"""ETag-basierte Aktualisierung verlinkter Dateien, ohne dauerhafte Kopien."""

from pathlib import Path
from tempfile import TemporaryDirectory

from django.db import transaction
from django.utils import timezone

from eintragstypen.dienste import suchtext_aktualisieren
from kern import extraktion, nextcloud
from kern.models import Anhang, NextcloudOrdner
from kern.nextcloud_ordner import konfiguration


def indexieren(anhang, erzwingen=False):
    quelle_stand = konfiguration(anhang.nextcloud_ordner) if anhang.nextcloud_ordner_id else None
    if quelle_stand is not None and (
        not anhang.nextcloud_ordner.aktiv or not anhang.nextcloud_verfuegbar
    ):
        return "übersprungen"
    bisher_geprueft = anhang.nextcloud_geprueft_am
    jetzt = timezone.now()
    anhang.nextcloud_geprueft_am = jetzt
    text = None
    ergebnis = "unverändert"
    try:
        if anhang.nextcloud_ordner_id and not extraktion.ist_lesbar(anhang.dateiname):
            text = ""
            anhang.index_stand = jetzt
            anhang.index_fehler = "Dieses Dateiformat ist nur über den Dateinamen durchsuchbar."
            ergebnis = "ohne Text"
        else:
            text, ergebnis = _inhalt_lesen(anhang, jetzt, erzwingen)
    except nextcloud.NextcloudFehler as fehler:
        anhang.index_fehler = str(fehler)[:500]
        ergebnis = "fehlgeschlagen"
    with transaction.atomic():
        if quelle_stand is not None:
            quelle = (
                NextcloudOrdner.objects.select_for_update()
                .filter(pk=anhang.nextcloud_ordner_id).first()
            )
            if quelle is None or not quelle.aktiv or konfiguration(quelle) != quelle_stand:
                return "übersprungen"
            aktuell = Anhang.objects.select_for_update().filter(pk=anhang.pk).first()
            if (
                aktuell is None or not aktuell.nextcloud_verfuegbar
                or aktuell.nextcloud_geprueft_am != bisher_geprueft
                or aktuell.nextcloud_inventur_etag != anhang.nextcloud_inventur_etag
            ):
                return "übersprungen"
        if text is not None:
            anhang.extrahierter_text = text
        anhang.save(
            update_fields=[
                "nextcloud_geprueft_am",
                "nextcloud_etag",
                "nextcloud_verfuegbar",
                "groesse",
                "mimetype",
                "index_stand",
                "index_fehler",
                "extrahierter_text",
            ]
        )
        if text is not None and anhang.eintrag_id and anhang.eintrag.typ_bekannt:
            suchtext_aktualisieren(anhang.eintrag)
    return ergebnis


def _inhalt_lesen(anhang, jetzt, erzwingen):
    text, ergebnis = None, "unverändert"
    with TemporaryDirectory(prefix="schulwissen-nextcloud-") as ordner:
        ziel = Path(ordner) / "download"
        antwort = nextcloud.herunterladen(
            anhang.nextcloud_pfad,
            ziel,
            etag=anhang.nextcloud_etag if anhang.index_stand and not erzwingen else "",
        )
        if antwort.status == 304:
            anhang.index_fehler = ""
            anhang.nextcloud_verfuegbar = True
        elif antwort.status in (403, 404, 410):
            # Gelöschte oder nicht mehr freigegebene Inhalte aus dem Index entfernen.
            text = ""
            anhang.nextcloud_etag = ""
            anhang.nextcloud_verfuegbar = False
            anhang.index_stand = jetzt
            anhang.index_fehler = "Die Datei fehlt oder ist nicht mehr freigegeben."
            ergebnis = "entfernt"
        else:
            anhang.nextcloud_verfuegbar = True
            anhang.nextcloud_etag = antwort.etag
            anhang.groesse = antwort.groesse
            anhang.mimetype = antwort.mimetype or anhang.mimetype
            try:
                text = extraktion.text_holen(ziel, anhang.dateiname)
                anhang.index_fehler = ""
                ergebnis = "gelesen"
            except extraktion.NichtLesbar:
                text = ""
                anhang.index_fehler = "Die Datei enthält keinen lesbaren Text."
                ergebnis = "ohne Text"
            anhang.index_stand = jetzt
    return text, ergebnis
