"""Text aus Anhängen holen und in den Suchindex schreiben.

Läuft im Hintergrund, nicht beim Hochladen: ein großes PDF soll das Kollegium
nicht warten lassen (SPEC.md §9, „Anhang-Extraktion asynchron“).

Einrichtung als systemd-Timer steht in DEPLOYMENT.md.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from eintragstypen.dienste import suchtext_aktualisieren
from kern.extraktion import NichtLesbar, ist_lesbar, text_holen
from kern.models import Anhang


class Command(BaseCommand):
    help = (
        "Liest den Text aus hochgeladenen Anhängen (PDF, DOCX, ODT, TXT) und "
        "macht ihn durchsuchbar. Bearbeitet nur, was noch nicht indexiert ist."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--alle",
            action="store_true",
            help="Auch schon indexierte Anhänge erneut lesen.",
        )
        parser.add_argument(
            "--anzahl",
            type=int,
            default=50,
            help="Höchstens so viele Anhänge je Lauf (Vorgabe: 50).",
        )

    def handle(self, *args, **optionen) -> None:
        anhaenge = Anhang.objects.exclude(datei="")
        if not optionen["alle"]:
            anhaenge = anhaenge.filter(Q(index_stand__isnull=True))
        anhaenge = anhaenge.select_related("eintrag")[: optionen["anzahl"]]

        gelesen = uebersprungen = fehlgeschlagen = 0
        betroffene_eintraege = set()

        for anhang in anhaenge:
            if not ist_lesbar(anhang.dateiname):
                # Trotzdem als bearbeitet merken, sonst versucht es der nächste
                # Lauf wieder.
                anhang.extrahierter_text = ""
                anhang.index_stand = timezone.now()
                anhang.save(update_fields=["extrahierter_text", "index_stand"])
                uebersprungen += 1
                continue

            pfad = Path(anhang.datei.path)
            if not pfad.exists():
                self.stderr.write(f"  fehlt auf der Platte: {anhang.dateiname}")
                fehlgeschlagen += 1
                continue

            try:
                text = text_holen(pfad, anhang.dateiname)
            except NichtLesbar as fehler:
                self.stdout.write(f"  nicht lesbar: {anhang.dateiname} – {fehler}")
                anhang.extrahierter_text = ""
                anhang.index_stand = timezone.now()
                anhang.save(update_fields=["extrahierter_text", "index_stand"])
                fehlgeschlagen += 1
                continue

            anhang.extrahierter_text = text
            anhang.index_stand = timezone.now()
            anhang.save(update_fields=["extrahierter_text", "index_stand"])
            gelesen += 1
            self.stdout.write(f"  gelesen: {anhang.dateiname} ({len(text)} Zeichen)")
            if anhang.eintrag_id:
                betroffene_eintraege.add(anhang.eintrag)

        # Der Suchtext des Eintrags enthält den Text seiner Anhänge – also muss
        # er nach der Extraktion neu gebaut werden.
        for eintrag in betroffene_eintraege:
            suchtext_aktualisieren(eintrag)

        self.stdout.write(
            self.style.SUCCESS(
                f"{gelesen} gelesen, {uebersprungen} übersprungen, "
                f"{fehlgeschlagen} ohne Text. "
                f"{len(betroffene_eintraege)} Einträge neu indexiert."
            )
        )
