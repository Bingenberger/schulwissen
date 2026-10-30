"""Verlinkte Nextcloud-Dateien regelmäßig prüfen und indexieren."""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from kern import nextcloud
from kern.models import Anhang
from kern.nextcloud_index import indexieren


class Command(BaseCommand):
    help = "Aktualisiert den Suchtext verlinkter Nextcloud-Dateien anhand ihres ETags."

    def add_arguments(self, parser):
        parser.add_argument("--anzahl", type=int, default=50)
        parser.add_argument("--alle", action="store_true", help="ETags ignorieren, erneut lesen.")

    def handle(self, *args, **optionen):
        if not nextcloud.ist_eingerichtet():
            raise CommandError("Bitte zuerst den technischen Nextcloud-Zugang einrichten.")
        if optionen["anzahl"] < 1:
            raise CommandError("--anzahl muss mindestens 1 sein.")
        menge = (
            Anhang.objects.filter(datei="")
            .exclude(nextcloud_pfad="")
            .select_related("eintrag", "eintrag__dokument")
            .order_by(F("nextcloud_geprueft_am").asc(nulls_first=True), "pk")
        )
        zaehler = Counter()
        for anhang in menge[: optionen["anzahl"]]:
            ergebnis = indexieren(anhang, erzwingen=optionen["alle"])
            zaehler[ergebnis] += 1
            self.stdout.write(f"{anhang.dateiname}: {ergebnis}")
        self.stdout.write(
            ", ".join(f"{anzahl} {art}" for art, anzahl in zaehler.items())
            or "Keine verlinkten Nextcloud-Dateien vorhanden."
        )
