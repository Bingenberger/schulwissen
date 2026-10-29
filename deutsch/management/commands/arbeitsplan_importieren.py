"""Rituale und Vorhaben aus der Arbeitsmappe importieren."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from deutsch import gliederung, import_xlsx
from kern.models import Dokument


class Command(BaseCommand):
    help = (
        "Importiert die Blätter „Rituale“ und „Vorhaben“ aus der Arbeitsmappe. "
        "Mit --vorschau wird nur geprüft und berichtet."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("datei", help="z. B. Datenmodell_Arbeitsplan_Deutsch.xlsx")
        parser.add_argument(
            "--dokument",
            default="arbeitsplan-deutsch",
            help="Schlüssel des Zieldokuments. Wird angelegt, wenn es fehlt.",
        )
        parser.add_argument(
            "--vorschau",
            action="store_true",
            help="Nur prüfen, nichts schreiben.",
        )
        parser.add_argument(
            "--mit-beispielen",
            action="store_true",
            dest="mit_beispielen",
            help="Auch die Beispielzeilen übernehmen; der Zusatz „(Beispiel)“ "
            "wird dabei aus dem Titel entfernt.",
        )

    def handle(self, *args, **optionen) -> None:
        pfad = Path(optionen["datei"])
        if not pfad.exists():
            raise CommandError(f"Die Datei {pfad} gibt es nicht.")

        if optionen["vorschau"]:
            bericht = self._vorschau(pfad, optionen)
            self.stdout.write(bericht.als_text())
            self.stdout.write(self.style.WARNING("\nVorschau – es wurde nichts geschrieben."))
            if not bericht.ok:
                raise CommandError(
                    f"{bericht.anzahl_fehler} Fehler. Ohne --vorschau würde nichts "
                    "übernommen werden."
                )
            return

        dokument = self._dokument_sichern(optionen["dokument"])
        bericht = import_xlsx.uebernehmen(
            pfad, dokument, mit_beispielen=optionen["mit_beispielen"]
        )
        self.stdout.write(bericht.als_text())
        if not bericht.ok:
            raise CommandError(
                f"{bericht.anzahl_fehler} Fehler – es wurde nichts übernommen. "
                "Bitte die Arbeitsmappe korrigieren und erneut versuchen."
            )
        self.stdout.write(self.style.SUCCESS("\nImport abgeschlossen."))

    def _dokument_sichern(self, schluessel: str):
        dokument = Dokument.objects.filter(schluessel=schluessel).first()
        if dokument is not None:
            return dokument
        dokument, _, angelegt = gliederung.dokument_anlegen(schluessel=schluessel)
        self.stdout.write(f"Dokument „{dokument.titel}“ angelegt, {angelegt} Kapitel erzeugt.")
        return dokument

    def _vorschau(self, pfad: Path, optionen: dict):
        """Prüft die Mappe und verwirft danach jede Änderung.

        Die Prüfung braucht ein Zieldokument – fehlt es, wird es nur
        vorübergehend angelegt und mit der Transaktion wieder verworfen.
        Eine Vorschau darf nichts hinterlassen.
        """
        with transaction.atomic():
            vorhanden = Dokument.objects.filter(schluessel=optionen["dokument"]).exists()
            dokument, _, _ = gliederung.dokument_anlegen(schluessel=optionen["dokument"])
            if not vorhanden:
                self.stdout.write(
                    f"Hinweis: Das Dokument „{optionen['dokument']}“ gibt es noch nicht. "
                    "Beim Import würde es mit der vollständigen Gliederung angelegt."
                )
            bericht = import_xlsx.pruefen_mappe(
                pfad, dokument, mit_beispielen=optionen["mit_beispielen"]
            )
            transaction.set_rollback(True)
        return bericht
