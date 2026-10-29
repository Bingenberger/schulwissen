"""Ein Konto mit der Rolle „Administration“ anlegen."""

from __future__ import annotations

import secrets

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from kern.models import ROLLE_ADMINISTRATION, Nutzer


class Command(BaseCommand):
    help = (
        "Legt ein Konto mit der Rolle „Administration“ an und gibt ein "
        "Startpasswort aus. Ist das Konto vorhanden, wird nur die Rolle ergänzt."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("email")
        parser.add_argument("--name", default="", help="Anzeigename, z. B. „Florian Förster“.")
        parser.add_argument("--kuerzel", default="")
        parser.add_argument(
            "--passwort",
            default="",
            help="Wird sonst zufällig erzeugt und hier ausgegeben.",
        )

    def handle(self, *args, **optionen) -> None:
        email = optionen["email"].strip().lower()
        if "@" not in email:
            raise CommandError(f"„{email}“ sieht nicht wie eine E-Mail-Adresse aus.")

        passwort = optionen["passwort"] or secrets.token_urlsafe(12)
        nutzer = Nutzer.objects.filter(email=email).first()

        if nutzer is None:
            nutzer = Nutzer.objects.create_user(
                email=email,
                password=passwort,
                anzeigename=optionen["name"] or email.split("@")[0],
                kuerzel=optionen["kuerzel"],
                is_staff=True,
                is_superuser=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Konto {email} angelegt."))
            if not optionen["passwort"]:
                self.stdout.write(f"Startpasswort: {passwort}")
                self.stdout.write("Bitte nach der ersten Anmeldung ändern.")
        else:
            nutzer.is_staff = True
            nutzer.is_superuser = True
            nutzer.save(update_fields=["is_staff", "is_superuser"])
            self.stdout.write(f"Konto {email} war vorhanden – Rechte ergänzt.")

        gruppe = Group.objects.filter(name=ROLLE_ADMINISTRATION).first()
        if gruppe is None:
            raise CommandError(
                "Die Rolle „Administration“ fehlt. Bitte zuerst "
                "„manage.py rollen_einrichten“ ausführen."
            )
        nutzer.groups.add(gruppe)
        self.stdout.write(self.style.SUCCESS(f"Rolle „{ROLLE_ADMINISTRATION}“ zugewiesen."))
