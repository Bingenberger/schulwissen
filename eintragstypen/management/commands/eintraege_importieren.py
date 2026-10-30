"""Einträge beliebiger Dokumenttypen aus JSON importieren."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from eintragstypen.import_json import pruefen_json, uebernehmen_json
from kern.models import Dokument


class Command(BaseCommand):
    help = "Importiert JSON-Einträge. --vorschau prüft, ohne etwas zu schreiben."

    def add_arguments(self, parser):
        parser.add_argument("datei")
        parser.add_argument("--vorschau", action="store_true")

    def handle(self, *args, **optionen):
        try:
            inhalt = json.loads(Path(optionen["datei"]).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as fehler:
            raise CommandError(f"Die JSON-Datei lässt sich nicht lesen: {fehler}") from fehler
        if not isinstance(inhalt, dict) or not isinstance(inhalt.get("dokument"), str):
            raise CommandError("Ein JSON-Objekt wird erwartet.")
        dokument = Dokument.objects.filter(schluessel=inhalt.get("dokument")).first()
        if dokument is None:
            raise CommandError("Bitte zuerst das Zieldokument in der App anlegen.")
        funktion = pruefen_json if optionen["vorschau"] else uebernehmen_json
        bericht = funktion(inhalt, dokument)
        self.stdout.write(bericht.als_text())
        if not bericht.ok:
            raise CommandError("Fehler im Import – nichts übernommen.")
        if optionen["vorschau"]:
            self.stdout.write("Vorschau – es wurde nichts geschrieben.")
