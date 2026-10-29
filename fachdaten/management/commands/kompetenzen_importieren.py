"""Kompetenzerwartungen aus einer JSON-Datei importieren."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from fachdaten.importe import importieren


class Command(BaseCommand):
    help = (
        "Importiert die Kompetenzerwartungen des Lehrplans aus einer JSON-Datei. "
        "Der Import ist idempotent und lässt die schulischen Festlegungen unberührt."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("datei", help="z. B. kompetenzerwartungen_lp2021.json")
        parser.add_argument(
            "--fach", default="deutsch", help="Fach, dem die Erwartungen zugeordnet werden."
        )
        parser.add_argument(
            "--vorschau",
            action="store_true",
            help="Nur prüfen und berichten, nichts in die Datenbank schreiben.",
        )

    def handle(self, *args, **optionen) -> None:
        pfad = Path(optionen["datei"])
        if not pfad.exists():
            raise CommandError(f"Die Datei {pfad} gibt es nicht.")

        bericht = importieren(pfad, fach=optionen["fach"], nur_pruefen=optionen["vorschau"])

        if bericht.fehler:
            self.stderr.write(self.style.ERROR(bericht.als_text()))
            raise CommandError(
                "Der Import wurde abgebrochen, es wurde nichts geschrieben. "
                "Bitte die Datei korrigieren."
            )

        if optionen["vorschau"]:
            self.stdout.write(self.style.WARNING("Vorschau – es wurde nichts geschrieben."))
        self.stdout.write(self.style.SUCCESS(bericht.als_text()))
