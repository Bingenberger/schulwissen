"""Nur lesbare Eintragsstände für Auswertungen, getrennt vom Arbeitsmodell."""

from dataclasses import dataclass

from django.db.models import Prefetch

from kern.models import Eintrag, Eintragsversion, Status


@dataclass(frozen=True)
class Eintragsstand:
    eintrag: Eintrag
    version: Eintragsversion | None = None

    @property
    def pk(self):
        return self.eintrag.pk

    @property
    def kennung(self):
        return self.eintrag.kennung

    @property
    def eintragstyp(self):
        return self.eintrag.eintragstyp

    @property
    def dokument(self):
        return self.eintrag.dokument

    @property
    def titel(self):
        return self.version.titel if self.version else self.eintrag.titel

    @property
    def daten(self):
        return self.version.daten if self.version else self.eintrag.daten

    @property
    def status(self):
        return self.version.status if self.version else self.eintrag.status

    def get_status_display(self):
        return Status(self.status).label

    @property
    def verweise(self):
        if self.version:
            return self.version.verlinkungen or []
        return [v.als_schnappschuss() for v in self.eintrag.verlinkungen.all()]


def auswertungsstaende(dokument, nur_beschlossene=False):
    """Ein gültiger Schnappschuss zählt weiter, wenn ein neuer Entwurf entsteht."""
    menge = dokument.eintraege.exclude(status=Status.ARCHIVIERT).select_related("dokument")
    if nur_beschlossene:
        menge = menge.prefetch_related(
            Prefetch(
                "versionen",
                queryset=Eintragsversion.objects.filter(
                    status=Status.BESCHLOSSEN, beschluss__isnull=False
                ).order_by("-versionsnummer"),
                to_attr="_gueltige_fassungen",
            )
        )
        return [Eintragsstand(e, e._gueltige_fassungen[0]) for e in menge if e._gueltige_fassungen]
    return [Eintragsstand(e) for e in menge.prefetch_related("verlinkungen")]
