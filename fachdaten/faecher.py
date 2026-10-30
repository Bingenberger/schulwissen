"""Gemeinsame Fachauswahl und fachabhängige Kompetenzbereiche."""

from fachdaten.models import Bereich, Fach


def bereiche_fuer(fach="deutsch"):
    eintrag = Fach.objects.filter(schluessel=fach).first()
    if eintrag:
        return list(eintrag.bereiche.items())
    return list(Bereich.choices) if fach == "deutsch" else []
