"""Beschlüsse fassen und zurücknehmen (SPEC.md §8).

Der Ablauf:

1. Die Redaktion stellt eine **Beschlussvorlage** zusammen: abgestimmte
   Einträge, die in die Konferenz sollen.
2. Die Administration trägt den **Beschluss** ein und verknüpft die Fassungen.
3. Beim Speichern werden die verknüpften Fassungen auf ``beschlossen`` gesetzt;
   ältere beschlossene Fassungen derselben Einträge auf ``archiviert``.

Ab dann gilt: Lesende sehen die beschlossene Fassung, Bearbeitende arbeiten an
einem neuen Entwurf weiter, und über jedem Eintrag steht, durch welchen
Beschluss er gilt.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q

from kern.models import Beschluss, Dokument, Eintrag, Eintragsversion, Status


@dataclass
class Beschlussbericht:
    beschlossen: int = 0
    archiviert: int = 0
    uebersprungen: list[str] = None

    def __post_init__(self) -> None:
        if self.uebersprungen is None:
            self.uebersprungen = []


def vorlage_kandidaten(dokument=None):
    """Einträge, die in eine Beschlussvorlage gehören.

    Das sind die abgestimmten Fassungen: die Gruppe ist sich einig, die
    Konferenz muss noch zustimmen (SPEC.md §8.2 und §8.3).
    """
    menge = Eintrag.objects.filter(status=Status.ABGESTIMMT).select_related("dokument", "eltern")
    if dokument is not None:
        menge = menge.filter(dokument=dokument)
    return menge.order_by("dokument", "position", "kennung")


@transaction.atomic
def beschluss_fassen(beschluss: Beschluss, eintraege, nutzer=None) -> Beschlussbericht:
    """Macht die aktuellen Fassungen der Einträge durch diesen Beschluss gültig."""
    from kern import rechte

    eintraege = list(eintraege)
    auswahl = {e.pk for e in eintraege}
    dokument_ids = sorted({e.dokument_id for e in eintraege})
    list(Dokument.objects.select_for_update().filter(pk__in=dokument_ids).order_by("pk"))
    eintraege = list(Eintrag.objects.select_for_update().filter(pk__in=auswahl).order_by("pk"))
    if {e.pk for e in eintraege} != auswahl:
        raise PermissionDenied(
            "Die Freigabeauswahl ist nicht mehr vollständig. Bitte prüfe sie erneut."
        )
    if nutzer is not None and any(
        not rechte.darf_beschliessen(nutzer, e.dokument) for e in eintraege
    ):
        raise PermissionDenied("Für mindestens ein Dokument fehlt die Freigabeberechtigung.")
    # Der Rahmen bleibt auch erhalten, wenn später eine Freigabe zurückgenommen wird.
    dokument_ids = {e.dokument_id for e in eintraege}
    if beschluss.protokoll_eintrag_id:
        dokument_ids.add(beschluss.protokoll_eintrag.dokument_id)
    if beschluss.protokoll_anhang_id:
        anhang = beschluss.protokoll_anhang
        if anhang.dokument_id:
            dokument_ids.add(anhang.dokument_id)
        if anhang.eintrag_id:
            dokument_ids.add(anhang.eintrag.dokument_id)
    if nutzer is not None and rechte.sichtbare_dokumente(nutzer).filter(
        pk__in=dokument_ids
    ).count() != len(dokument_ids):
        raise PermissionDenied("Der Protokollnachweis ist nicht zugänglich.")
    beschluss.dokumente.add(*dokument_ids)
    bericht = Beschlussbericht()

    for eintrag in eintraege:
        version = eintrag.letzte_version()
        if version is None:
            bericht.uebersprungen.append(
                f"{eintrag.kennung}: hat noch keine Fassung und wird übergangen."
            )
            continue
        if version.status == Status.BESCHLOSSEN:
            bericht.uebersprungen.append(
                f"{eintrag.kennung}: Fassung {version.versionsnummer} ist schon beschlossen."
            )
            continue

        # Ältere beschlossene Fassungen desselben Eintrags abhängen.
        # Hier steht bewusst „update" und nicht „save": der Schutz in
        # Eintragsversion.save() verbietet jede Änderung an einer beschlossenen
        # Fassung. Das Archivieren ändert aber keinen Inhalt – es hält nur
        # fest, dass ein neuerer Beschluss sie abgelöst hat.
        bericht.archiviert += (
            Eintragsversion.objects.filter(eintrag=eintrag, status=Status.BESCHLOSSEN)
            .exclude(pk=version.pk)
            .update(status=Status.ARCHIVIERT)
        )

        version.status = Status.BESCHLOSSEN
        version.beschluss = beschluss
        version.save()

        eintrag.status = Status.BESCHLOSSEN
        eintrag.save(update_fields=["status", "geaendert_am"])
        bericht.beschlossen += 1

    return bericht


@transaction.atomic
def beschluss_zuruecknehmen(beschluss: Beschluss, nutzer=None) -> int:
    """Hebt einen irrtümlich eingetragenen Beschluss auf.

    Die Fassungen werden wieder „abgestimmt in Gruppe“; die zuvor gültige
    Fassung wird reaktiviert. Gedacht für Tippfehler beim Eintragen, nicht für
    eine inhaltliche Rücknahme – die ist ein neuer Beschluss.
    """
    from kern import rechte

    betroffen = Dokument.objects.filter(
        Q(pk__in=beschluss.dokumente.values("pk")) | Q(eintraege__versionen__beschluss=beschluss)
    ).values("pk")
    list(Dokument.objects.select_for_update().filter(pk__in=betroffen).order_by("pk"))
    list(Eintrag.objects.select_for_update().filter(versionen__beschluss=beschluss).order_by("pk"))

    if nutzer is not None and not rechte.darf_beschluss_zuruecknehmen(nutzer, beschluss):
        raise PermissionDenied("Für diesen Beschluss fehlt die Freigabeberechtigung.")
    anzahl = 0
    for version in list(beschluss.beschlossene_versionen.all()):
        eintrag = version.eintrag
        Eintragsversion.objects.filter(pk=version.pk).update(
            status=Status.ABGESTIMMT, beschluss=None
        )

        vorherige = (
            Eintragsversion.objects.filter(eintrag=eintrag, status=Status.ARCHIVIERT)
            .exclude(beschluss=None)
            .order_by("-versionsnummer")
            .first()
        )
        if vorherige is not None:
            Eintragsversion.objects.filter(pk=vorherige.pk).update(status=Status.BESCHLOSSEN)
            eintrag.status = Status.BESCHLOSSEN
        else:
            eintrag.status = Status.ABGESTIMMT
        eintrag.save(update_fields=["status", "geaendert_am"])
        anzahl += 1
    return anzahl


def aenderungen_seit_beschluss(dokument):
    """Was hat sich seit dem letzten Beschluss getan? (SPEC.md §8.6)

    Gibt drei Listen zurück: neue Einträge ohne Beschluss, geänderte Einträge
    mit beschlossener Vorfassung, und unveränderte.
    """
    neu, geaendert, unveraendert = [], [], []

    for eintrag in dokument.eintraege.select_related("eltern").order_by("position", "kennung"):
        beschlossen = eintrag.beschlossene_version()
        if beschlossen is None:
            neu.append(eintrag)
            continue
        aktuell = eintrag.letzte_version()
        if aktuell is None or aktuell.pk == beschlossen.pk:
            unveraendert.append(eintrag)
            continue
        if aktuell.titel != beschlossen.titel or aktuell.daten != beschlossen.daten:
            geaendert.append((eintrag, beschlossen, aktuell))
        else:
            unveraendert.append(eintrag)

    return {"neu": neu, "geaendert": geaendert, "unveraendert": unveraendert}
