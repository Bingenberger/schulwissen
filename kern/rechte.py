"""Alle Zugriffsentscheidungen an einer Stelle.

Views und Vorlagen fragen hier nach und bauen keine eigene Logik. Wer die
Rechte ändern will, ändert nur diese Datei.

Grundlage ist die Rollentabelle aus SPEC.md §5:

* **Administration** darf alles.
* **Redaktion** bearbeitet Einträge und setzt den Status bis „abgestimmt“.
* **Lehrkraft** liest alles, legt Entwürfe an und bearbeitet die eigenen und
  die ihrer Arbeitsgruppe, kommentiert und plant für sich.
* **Lesend** liest ausschließlich beschlossene Inhalte.
"""

from __future__ import annotations

from kern.models import (
    ROLLE_ADMINISTRATION,
    ROLLE_LEHRKRAFT,
    ROLLE_LESEND,
    ROLLE_REDAKTION,
    STATUS_VOR_BESCHLUSS,
    Status,
)

#: Status, die auch die Rolle „Lesend“ sehen darf.
OEFFENTLICHE_STATUS = (Status.BESCHLOSSEN, Status.ARCHIVIERT)


def _angemeldet(nutzer) -> bool:
    return bool(nutzer and nutzer.is_authenticated and nutzer.is_active)


def ist_administration(nutzer) -> bool:
    if not _angemeldet(nutzer):
        return False
    return nutzer.is_superuser or nutzer.hat_rolle(ROLLE_ADMINISTRATION)


def ist_redaktion(nutzer) -> bool:
    return ist_administration(nutzer) or (
        _angemeldet(nutzer) and nutzer.hat_rolle(ROLLE_REDAKTION)
    )


def ist_lehrkraft(nutzer) -> bool:
    return ist_redaktion(nutzer) or (_angemeldet(nutzer) and nutzer.hat_rolle(ROLLE_LEHRKRAFT))


def ist_nur_lesend(nutzer) -> bool:
    """Wahr für Konten, die ausschließlich beschlossene Inhalte sehen dürfen.

    Dazu gehören ausdrücklich „Lesend“-Konten und Konten ohne jede Rolle –
    ein neu angelegtes Konto soll nicht versehentlich Entwürfe sehen.
    """
    if not _angemeldet(nutzer):
        return True
    if ist_lehrkraft(nutzer):
        return False
    return nutzer.hat_rolle(ROLLE_LESEND) or not nutzer.rollen


# --- Lesen -----------------------------------------------------------------


def darf_lesen(nutzer, eintrag) -> bool:
    if not _angemeldet(nutzer):
        return False
    if eintrag.status in OEFFENTLICHE_STATUS:
        return True
    # Entwürfe und abgestimmte Fassungen: alles außer „Lesend“.
    return not ist_nur_lesend(nutzer)


def sichtbare_eintraege(nutzer, menge):
    """Schränkt ein QuerySet auf das ein, was ``nutzer`` sehen darf."""
    if not _angemeldet(nutzer):
        return menge.none()
    if ist_nur_lesend(nutzer):
        return menge.filter(status__in=OEFFENTLICHE_STATUS)
    return menge


# --- Bearbeiten ------------------------------------------------------------


def gehoert_zum_arbeitsbereich(nutzer, eintrag) -> bool:
    """Ist der Eintrag „eigener“ oder der der Arbeitsgruppe des Nutzers?"""
    if not _angemeldet(nutzer):
        return False
    if eintrag.erstellt_von_id == nutzer.pk or eintrag.verantwortlich_person_id == nutzer.pk:
        return True
    if eintrag.verantwortlich_gruppe_id is None:
        return False
    return nutzer.groups.filter(pk=eintrag.verantwortlich_gruppe_id).exists()


def darf_bearbeiten(nutzer, eintrag) -> bool:
    if not _angemeldet(nutzer):
        return False
    if ist_administration(nutzer):
        return True
    if ist_nur_lesend(nutzer):
        return False
    if ist_redaktion(nutzer):
        # Die Redaktion darf auch einen beschlossenen Eintrag anfassen – daraus
        # entsteht eine neue Entwurfsfassung, die beschlossene bleibt gültig.
        return True
    # Lehrkraft: nur Entwürfe, und nur eigene oder die der Arbeitsgruppe.
    if eintrag.status not in STATUS_VOR_BESCHLUSS:
        return False
    return gehoert_zum_arbeitsbereich(nutzer, eintrag)


def darf_anlegen(nutzer, dokument=None) -> bool:
    """Neue Einträge anlegen darf jede Lehrkraft."""
    return ist_lehrkraft(nutzer)


def darf_status_setzen(nutzer, eintrag, neuer_status: str) -> bool:
    if not _angemeldet(nutzer):
        return False
    if neuer_status in OEFFENTLICHE_STATUS:
        # „beschlossen“ und „archiviert“ entstehen ausschließlich über einen
        # Beschluss, den die Administration einträgt (SPEC.md §8.4).
        return ist_administration(nutzer)
    if neuer_status == Status.ABGESTIMMT:
        return ist_redaktion(nutzer)
    return darf_bearbeiten(nutzer, eintrag)


def darf_kommentieren(nutzer, eintrag) -> bool:
    return ist_lehrkraft(nutzer) and darf_lesen(nutzer, eintrag)


def darf_kommentar_erledigen(nutzer, kommentar) -> bool:
    if ist_redaktion(nutzer):
        return True
    return _angemeldet(nutzer) and kommentar.autor_id == nutzer.pk


# --- Verwaltung ------------------------------------------------------------


def darf_dokument_anlegen(nutzer) -> bool:
    return ist_administration(nutzer)


def darf_beschliessen(nutzer) -> bool:
    return ist_administration(nutzer)


def darf_importieren(nutzer) -> bool:
    return ist_administration(nutzer)


def darf_schulische_festlegung_bearbeiten(nutzer) -> bool:
    """Kompetenzen sind nur auswählbar – außer diesem einen Feld (SPEC.md §7.3)."""
    return ist_redaktion(nutzer)


def darf_eigene_planung(nutzer) -> bool:
    return ist_lehrkraft(nutzer)
