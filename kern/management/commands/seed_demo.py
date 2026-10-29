"""Beispieldaten zum Ausprobieren anlegen (SPEC.md §15).

Legt Rollen, Arbeitsgruppen, vier Demo-Konten, den Arbeitsplan Deutsch mit
Gliederung und – falls die Dateien vorhanden sind – die Kompetenz-Stammdaten
samt den beiden Beispielzeilen der Arbeitsmappe an.

Alle Demo-Konten haben dasselbe Passwort. Das Kommando verweigert den Dienst,
wenn SW_DEBUG nicht gesetzt ist – Demo-Konten gehören nicht in den Echtbetrieb.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from deutsch import gliederung
from kern.models import (
    ROLLE_ADMINISTRATION,
    ROLLE_LEHRKRAFT,
    ROLLE_LESEND,
    ROLLE_REDAKTION,
    Gruppenart,
    Gruppenprofil,
    Nutzer,
)

DEMO_PASSWORT = "schulwissen-demo-2026"

ARBEITSGRUPPEN = ("Jahrgang 1", "Jahrgang 2", "Jahrgang 3", "Jahrgang 4", "Steuergruppe")

#: E-Mail, Anzeigename, Kürzel, Rolle, Arbeitsgruppen
KONTEN = (
    ("leitung@example.org", "Schulleitung (Demo)", "SL", ROLLE_ADMINISTRATION, ()),
    (
        "fachvorsitz@example.org",
        "Fachkonferenzvorsitz (Demo)",
        "FKV",
        ROLLE_REDAKTION,
        ("Steuergruppe",),
    ),
    (
        "lehrkraft@example.org",
        "Lehrkraft Jahrgang 3 (Demo)",
        "LK3",
        ROLLE_LEHRKRAFT,
        ("Jahrgang 3",),
    ),
    ("ogs@example.org", "OGS-Leitung (Demo)", "OGS", ROLLE_LESEND, ()),
)


class Command(BaseCommand):
    help = "Legt Beispieldaten zum Ausprobieren an. Nur mit SW_DEBUG=true."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--trotzdem",
            action="store_true",
            help="Auch ohne SW_DEBUG ausführen. Nur bewusst verwenden.",
        )

    @transaction.atomic
    def handle(self, *args, **optionen) -> None:
        if not settings.DEBUG and not optionen["trotzdem"]:
            raise CommandError(
                "seed_demo legt Konten mit einem allgemein bekannten Passwort an. "
                "Im Echtbetrieb ist das gefährlich. Entweder SW_DEBUG=true setzen "
                "oder --trotzdem angeben, wenn das wirklich gewollt ist."
            )

        call_command("rollen_einrichten", verbosity=0)

        for name in ARBEITSGRUPPEN:
            gruppe, neu = Group.objects.get_or_create(name=name)
            Gruppenprofil.objects.update_or_create(
                gruppe=gruppe,
                defaults={
                    "art": Gruppenart.ARBEITSGRUPPE,
                    "beschreibung": f"Arbeitsgruppe {name}",
                },
            )
            if neu:
                self.stdout.write(f"Arbeitsgruppe „{name}“ angelegt.")

        for email, name, kuerzel, rolle, gruppen in KONTEN:
            nutzer = Nutzer.objects.filter(email=email).first()
            if nutzer is None:
                nutzer = Nutzer.objects.create_user(
                    email=email, password=DEMO_PASSWORT, anzeigename=name, kuerzel=kuerzel
                )
                self.stdout.write(f"Konto {email} angelegt ({rolle}).")
            if rolle == ROLLE_ADMINISTRATION:
                nutzer.is_staff = True
                nutzer.is_superuser = True
                nutzer.save(update_fields=["is_staff", "is_superuser"])
            elif rolle == ROLLE_REDAKTION:
                # Die Redaktion pflegt die schulischen Festlegungen in der Verwaltung.
                nutzer.is_staff = True
                nutzer.save(update_fields=["is_staff"])
            nutzer.groups.add(Group.objects.get(name=rolle))
            for gruppenname in gruppen:
                nutzer.groups.add(Group.objects.get(name=gruppenname))

        dokument, neu, angelegt = gliederung.dokument_anlegen()
        self.stdout.write(
            f"Dokument „{dokument.titel}“ {'angelegt' if neu else 'vorhanden'}, "
            f"{angelegt} Kapitel ergänzt."
        )

        self._stammdaten(dokument)

        self.stdout.write(self.style.SUCCESS("\nBeispieldaten sind angelegt."))
        self.stdout.write(f"Passwort aller Demo-Konten: {DEMO_PASSWORT}")
        for email, name, _, rolle, _ in KONTEN:
            self.stdout.write(f"  {email:<28} {rolle:<16} {name}")

    def _stammdaten(self, dokument) -> None:
        """Kompetenzen und Arbeitsmappe importieren, falls die Dateien da sind."""
        from deutsch import import_xlsx
        from fachdaten.importe import importieren
        from fachdaten.models import Kompetenzerwartung

        basis = Path(settings.BASIS)

        kompetenzen = basis / "kompetenzerwartungen_lp2021.json"
        if Kompetenzerwartung.objects.exists():
            self.stdout.write(
                f"{Kompetenzerwartung.objects.count()} Kompetenzerwartungen sind schon da."
            )
        elif kompetenzen.exists():
            bericht = importieren(kompetenzen)
            self.stdout.write(f"{bericht.angelegt} Kompetenzerwartungen importiert.")
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"{kompetenzen.name} nicht gefunden – ohne Stammdaten lassen sich "
                    "keine Kompetenzen verlinken."
                )
            )
            return

        mappe = basis / "Datenmodell_Arbeitsplan_Deutsch.xlsx"
        if not mappe.exists():
            self.stdout.write(
                self.style.WARNING(f"{mappe.name} nicht gefunden – keine Beispielzeilen.")
            )
            return
        if dokument.eintraege.filter(eintragstyp__in=("ritual", "vorhaben")).exists():
            self.stdout.write("Rituale und Vorhaben sind schon da.")
            return

        bericht = import_xlsx.uebernehmen(mappe, dokument, mit_beispielen=True)
        if bericht.ok:
            self.stdout.write(
                f"{bericht.geschrieben} Rituale/Vorhaben aus der Arbeitsmappe importiert."
            )
        else:
            self.stdout.write(self.style.ERROR(bericht.als_text()))
