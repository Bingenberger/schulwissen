"""Rollen und Gremien anlegen. Läuft bei jedem Start des Containers."""

from __future__ import annotations

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from kern.models import ROLLEN, Gremium, Gruppenart, Gruppenprofil

#: Gremien, die es an einer Grundschule in NRW gibt. Weitere trägt die
#: Administration in der Verwaltung nach.
GREMIEN = (
    ("Lehrerkonferenz", 10),
    ("Fachkonferenz Deutsch", 20),
    ("Schulkonferenz", 30),
    ("Steuergruppe", 40),
)


class Command(BaseCommand):
    help = "Legt die vier Rollen und die Standard-Gremien an (idempotent)."

    def handle(self, *args, **optionen) -> None:
        for name, beschreibung in ROLLEN:
            gruppe, neu = Group.objects.get_or_create(name=name)
            Gruppenprofil.objects.update_or_create(
                gruppe=gruppe,
                defaults={"art": Gruppenart.ROLLE, "beschreibung": beschreibung},
            )
            if neu:
                self.stdout.write(f"Rolle „{name}“ angelegt.")

        for name, reihenfolge in GREMIEN:
            _, neu = Gremium.objects.get_or_create(name=name, defaults={"reihenfolge": reihenfolge})
            if neu:
                self.stdout.write(f"Gremium „{name}“ angelegt.")

        self.stdout.write(self.style.SUCCESS("Rollen und Gremien sind eingerichtet."))
