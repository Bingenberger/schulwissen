"""Einträge mit unbekanntem Eintragstyp finden und richtigstellen.

Eintragstypen stehen im Code (Leitprinzip 3), nicht in der Datenbank. Darum
kann die Datenbank sie nicht erzwingen. Wird ein Modul entfernt oder ein
Eintrag von Hand mit einem falschen Typ angelegt, findet dieses Kommando ihn.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from eintragstypen.registry import registry
from kern.models import Eintrag


class Command(BaseCommand):
    help = (
        "Sucht Einträge, deren Eintragstyp die App nicht kennt. "
        "Mit --setzen lassen sie sich auf einen gültigen Typ umstellen."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--setzen",
            default="",
            help="Gültiger Eintragstyp, auf den die gefundenen Einträge gesetzt werden.",
        )
        parser.add_argument(
            "--nur",
            default="",
            help="Nur Einträge mit genau diesem (falschen) Typ anfassen.",
        )

    def handle(self, *args, **optionen) -> None:
        bekannt = {schluessel for schluessel, _ in registry.auswahl()}
        self.stdout.write(f"Bekannte Eintragstypen: {', '.join(sorted(bekannt))}")

        betroffen = [
            e for e in Eintrag.objects.select_related("dokument") if e.eintragstyp not in bekannt
        ]
        if optionen["nur"]:
            betroffen = [e for e in betroffen if e.eintragstyp == optionen["nur"]]

        if not betroffen:
            self.stdout.write(self.style.SUCCESS("Alle Einträge haben einen gültigen Typ."))
            return

        self.stdout.write(f"\n{len(betroffen)} Eintrag/Einträge mit unbekanntem Typ:")
        for eintrag in betroffen:
            self.stdout.write(
                f"  {eintrag.dokument.schluessel} · {eintrag.kennung} "
                f"„{eintrag.titel}“ → Typ {eintrag.eintragstyp!r}"
            )

        ziel = optionen["setzen"]
        if not ziel:
            self.stdout.write(
                "\nZum Richtigstellen das Kommando mit --setzen <typ> erneut aufrufen, "
                "zum Beispiel:\n"
                "  manage.py eintraege_pruefen --setzen grundlagenkapitel"
            )
            return

        if ziel not in bekannt:
            raise CommandError(
                f"„{ziel}“ ist kein Eintragstyp. Möglich sind: {', '.join(sorted(bekannt))}."
            )

        for eintrag in betroffen:
            eintrag.eintragstyp = ziel
            eintrag.save(update_fields=["eintragstyp", "geaendert_am"])
            self.stdout.write(f"  {eintrag.kennung}: Typ auf „{ziel}“ gesetzt.")

        self.stdout.write(
            self.style.SUCCESS(f"\n{len(betroffen)} Eintrag/Einträge richtiggestellt.")
        )
        self.stdout.write(
            "Die Felder des alten Typs stehen weiter in „daten“ und werden nun "
            "ignoriert. Bitte die Einträge einmal öffnen und prüfen."
        )
