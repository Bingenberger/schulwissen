"""Kompetenzerwartungen aus einer Datei oder aus ``lehrplan/`` importieren."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from fachdaten import lehrplan
from fachdaten.importe import MODI, MODUS_LEHRPLAN, importieren


class Command(BaseCommand):
    help = (
        "Importiert Kompetenzerwartungen aus JSON, XLSX oder CSV. Der Import ist "
        "idempotent und lässt die schulischen Festlegungen unberührt. Ohne Datei "
        "werden alle Fächer aus dem Verzeichnis „lehrplan/“ eingelesen."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "datei",
            nargs="?",
            help="z. B. lehrplan/kompetenzerwartungen_mathematik.json. "
            "Ohne Angabe: alle Fächer aus „lehrplan/“.",
        )
        parser.add_argument(
            "--fach",
            default=None,
            help="Fach, dem die Erwartungen zugeordnet werden (Standard: deutsch).",
        )
        parser.add_argument(
            "--modus",
            default=MODUS_LEHRPLAN,
            choices=[wert for wert, _ in MODI],
            help="„lehrplan“ schreibt die amtlichen Angaben, "
            "„festlegungen“ nur die Spalte „Schulische Festlegung“.",
        )
        parser.add_argument(
            "--vorschau",
            action="store_true",
            help="Nur prüfen und berichten, nichts in die Datenbank schreiben.",
        )

    def handle(self, *args, **optionen) -> None:
        if optionen["datei"]:
            auftraege = [(optionen["fach"] or "deutsch", Path(optionen["datei"]))]
            if not auftraege[0][1].exists():
                raise CommandError(f"Die Datei {auftraege[0][1]} gibt es nicht.")
        else:
            auftraege = lehrplan.vorhandene_dateien()
            if optionen["fach"]:
                auftraege = [a for a in auftraege if a[0] == optionen["fach"]]
            if not auftraege:
                raise CommandError(
                    f"In {lehrplan.verzeichnis()} liegen keine Kompetenzdateien. "
                    "Bitte eine Datei angeben."
                )

        fehlerhaft = []
        for fach, pfad in auftraege:
            bericht = importieren(
                pfad,
                fach=fach,
                nur_pruefen=optionen["vorschau"],
                modus=optionen["modus"],
            )
            kopf = f"{fach} ({pfad.name})"
            if bericht.fehler:
                self.stderr.write(self.style.ERROR(f"{kopf}\n{bericht.als_text()}"))
                fehlerhaft.append(fach)
                continue
            self.stdout.write(self.style.SUCCESS(f"{kopf}\n{bericht.als_text()}"))

        if fehlerhaft:
            raise CommandError(
                "Für diese Fächer wurde nichts geschrieben: "
                f"{', '.join(fehlerhaft)}. Bitte die Dateien korrigieren."
            )
        if optionen["vorschau"]:
            self.stdout.write(self.style.WARNING("Vorschau – es wurde nichts geschrieben."))
