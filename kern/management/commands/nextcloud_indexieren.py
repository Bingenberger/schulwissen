"""Suchordner erfassen und Nextcloud-Dateien regelmäßig prüfen und indexieren."""

from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django.utils import timezone

from kern import nextcloud
from kern.models import Anhang, NextcloudOrdner
from kern.nextcloud_index import indexieren
from kern.nextcloud_ordner import ordner_einlesen


class Command(BaseCommand):
    help = "Erfasst Nextcloud-Suchordner und aktualisiert den Suchtext von Nextcloud-Dateien."

    def add_arguments(self, parser):
        parser.add_argument("--anzahl", type=int, default=50)
        parser.add_argument("--alle", action="store_true", help="ETags ignorieren, erneut lesen.")
        parser.add_argument("--ordner-anzahl", type=int, default=10)

    def handle(self, *args, **optionen):
        if not nextcloud.ist_eingerichtet():
            raise CommandError("Bitte zuerst den technischen Nextcloud-Zugang einrichten.")
        if optionen["anzahl"] < 1:
            raise CommandError("--anzahl muss mindestens 1 sein.")
        if optionen["ordner_anzahl"] < 1:
            raise CommandError("--ordner-anzahl muss mindestens 1 sein.")
        quellen = NextcloudOrdner.objects.filter(aktiv=True)
        if not optionen["alle"]:
            quellen = quellen.filter(
                Q(geprueft_am__isnull=True)
                | Q(geprueft_am__lte=timezone.now() - timedelta(minutes=15))
            )
        quellen = quellen.order_by(F("geprueft_am").asc(nulls_first=True), "pk")
        for quelle in quellen[:optionen["ordner_anzahl"]]:
            self.stdout.write(f"{quelle.name}: {ordner_einlesen(quelle)}")
        menge = (
            Anhang.objects.filter(datei="")
            .exclude(nextcloud_pfad="")
            .filter(
                Q(nextcloud_ordner__isnull=True)
                | Q(nextcloud_ordner__aktiv=True, nextcloud_verfuegbar=True)
            )
            .select_related("eintrag", "eintrag__dokument", "nextcloud_ordner")
            .order_by(F("nextcloud_geprueft_am").asc(nulls_first=True), "pk")
        )
        zaehler = Counter()
        for anhang in menge[: optionen["anzahl"]]:
            ergebnis = indexieren(anhang, erzwingen=optionen["alle"])
            zaehler[ergebnis] += 1
            self.stdout.write(f"{anhang.dateiname}: {ergebnis}")
        self.stdout.write(
            ", ".join(f"{anzahl} {art}" for art, anzahl in zaehler.items())
            or "Keine Nextcloud-Dateien zur Prüfung vorhanden."
        )
