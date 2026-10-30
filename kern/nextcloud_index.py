"""ETag-basierte Aktualisierung verlinkter Dateien, ohne dauerhafte Kopien."""

from pathlib import Path
from tempfile import TemporaryDirectory

from django.db import transaction
from django.utils import timezone

from eintragstypen.dienste import suchtext_aktualisieren
from kern import extraktion, nextcloud


def indexieren(anhang, erzwingen=False):
    jetzt = timezone.now()
    anhang.nextcloud_geprueft_am = jetzt
    text = None
    ergebnis = "unverändert"
    try:
        with TemporaryDirectory(prefix="schulwissen-nextcloud-") as ordner:
            ziel = Path(ordner) / "download"
            antwort = nextcloud.herunterladen(
                anhang.nextcloud_pfad,
                ziel,
                etag=anhang.nextcloud_etag if anhang.index_stand and not erzwingen else "",
            )
            if antwort.status == 304:
                pass
            elif antwort.status in (403, 404, 410):
                # Gelöschte oder nicht mehr freigegebene Inhalte aus dem Index entfernen.
                text = ""
                anhang.nextcloud_etag = ""
                anhang.index_stand = jetzt
                anhang.index_fehler = "Die Datei fehlt oder ist nicht mehr freigegeben."
                ergebnis = "entfernt"
            else:
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
    except nextcloud.NextcloudFehler as fehler:
        anhang.index_fehler = str(fehler)[:500]
        ergebnis = "fehlgeschlagen"
    with transaction.atomic():
        if text is not None:
            anhang.extrahierter_text = text
        anhang.save(
            update_fields=[
                "nextcloud_geprueft_am",
                "nextcloud_etag",
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
