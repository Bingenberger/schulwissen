"""Gemeinsame Fachauswahl und fachabhängige Kompetenzbereiche."""

from fachdaten.models import Bereich, Fach


def bereiche_fuer(fach="deutsch"):
    """Die Kompetenzbereiche eines Fachs – in der Reihenfolge des Lehrplans."""
    eintrag = Fach.objects.filter(schluessel=fach).first()
    if eintrag:
        return eintrag.bereichspaare()
    return list(Bereich.choices) if fach == "deutsch" else []
