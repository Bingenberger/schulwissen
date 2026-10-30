"""Kompetenzerwartungen finden – für die Auswahl in der Maske und die Suche.

Beide Wege benutzen dieselbe Funktion, damit sie dieselben Treffer liefern.

**Zur Ähnlichkeitsschwelle.** ``pg_trgm`` vergleicht Buchstabengruppen. Auf
einem langen Text findet es fast immer irgendetwas: „Märchen“ und „Recherchen“
teilen genug Dreiergruppen für einen Wert von 0,5 – obwohl keine einzige
Kompetenzerwartung von Märchen handelt. Bei 0,35 kamen so 68 falsche Treffer
heraus und begruben das eine richtige Ergebnis.

Darum zwei Schwellen: auf dem Volltext muss die Ähnlichkeit hoch sein (0,6 –
das verzeiht „Gesprch“ statt „Gespräch“, lässt aber „Märchen“ gegen
„Recherchen“ durchfallen), auf der Kennung darf sie niedriger liegen, weil dort
kurze Zeichenketten verglichen werden.
"""

from __future__ import annotations

from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models import Q
from django.db.models.functions import Greatest

from fachdaten.models import Kompetenzerwartung

#: Schwelle für die Kennung, z. B. „SC2.02“ gegen „SC2.02D“.
AEHNLICHKEIT_KENNUNG = 0.4

#: Schwelle für den Volltext. Siehe Modulkommentar – niedriger wird es Rauschen.
AEHNLICHKEIT_TEXT = 0.6


def kompetenzen_finden(begriff: str, bereich: str = "", stufe: str = "", fach: str = "deutsch"):
    """Kompetenzerwartungen zu einem Suchbegriff, nach Güte sortiert."""
    menge = Kompetenzerwartung.objects.all()
    if fach:
        menge = menge.filter(fach=fach)
    if bereich:
        menge = menge.filter(bereich=bereich)
    if stufe:
        menge = menge.filter(stufe=stufe)

    begriff = (begriff or "").strip()
    if not begriff:
        return menge.order_by("bereich", "schwerpunkt_nr", "id")

    return (
        menge.annotate(
            naehe_kennung=TrigramWordSimilarity(begriff, "id"),
            naehe_text=TrigramWordSimilarity(begriff, "suchtext"),
        )
        .annotate(naehe=Greatest("naehe_kennung", "naehe_text"))
        .filter(
            Q(id__icontains=begriff)
            | Q(suchtext__icontains=begriff)
            | Q(naehe_kennung__gte=AEHNLICHKEIT_KENNUNG)
            | Q(naehe_text__gte=AEHNLICHKEIT_TEXT)
        )
        .order_by("-naehe", "bereich", "schwerpunkt_nr", "id")
    )
