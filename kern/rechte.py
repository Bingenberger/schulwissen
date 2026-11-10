"""Alle Zugriffsentscheidungen an einer Stelle.

Views und Vorlagen fragen hier nach und bauen keine eigene Logik. Wer die
Rechte ändern will, ändert nur diese Datei.

Grundlage ist die Rollentabelle aus SPEC.md §5:

* **Administration** darf alles.
* **Redaktion** bearbeitet zugewiesene Dokumente/Bereiche bis „abgestimmt“.
* **Lehrkraft** liest zugängliche Dokumente, legt Entwürfe an und bearbeitet die eigenen und
  die ihrer Arbeitsgruppe, kommentiert und plant für sich.
* **Lesend** liest ausschließlich zugängliche beschlossene Inhalte.
* Fachliche Freigaben benötigen eine getrennte dokument-/bereichsbezogene Regel.
"""

from __future__ import annotations

from kern.models import (
    ROLLE_ADMINISTRATION,
    ROLLE_LEHRKRAFT,
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
    return ist_administration(nutzer) or (_angemeldet(nutzer) and nutzer.hat_rolle(ROLLE_REDAKTION))


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
    return True


# --- Dokument- und Bereichszugänge -----------------------------------------


def _regeln(nutzer, recht):
    from django.db.models import Q

    from kern.models import Zugangsregel

    if not _angemeldet(nutzer):
        return Zugangsregel.objects.none()
    return Zugangsregel.objects.filter(
        Q(nutzer=nutzer) | Q(gruppe__in=nutzer.groups.all()), **{recht: True}
    )


def sichtbare_dokumente(nutzer, menge=None):
    from django.db.models import Q

    from kern.models import Dokument

    menge = Dokument.objects.all() if menge is None else menge
    if not _angemeldet(nutzer):
        return menge.none()
    if ist_administration(nutzer):
        return menge
    regeln = _regeln(nutzer, "lesen")
    # Eine Dokumentregel umgeht keine Bereichsgrenze und umgekehrt.
    return menge.filter(
        Q(bereich__isnull=True)
        | Q(bereich__kollegiumsweit=True)
        | Q(bereich__in=regeln.values("bereich_id"))
    ).filter(Q(kollegiumsweit=True) | Q(pk__in=regeln.values("dokument_id")))


def darf_dokument_lesen(nutzer, dokument):
    return bool(dokument and sichtbare_dokumente(nutzer).filter(pk=dokument.pk).exists())


def sichtbare_nextcloud_ordner(nutzer):
    from django.db.models import Q

    from kern.models import NextcloudOrdner

    menge = NextcloudOrdner.objects.filter(aktiv=True)
    if not _angemeldet(nutzer):
        return menge.none()
    if ist_administration(nutzer):
        return menge
    return menge.filter(Q(kollegiumsweit=True) | Q(gruppen__in=nutzer.groups.all())).distinct()


def berechtigte_dokumente(nutzer, recht):
    from django.db.models import Q

    menge = sichtbare_dokumente(nutzer)
    if ist_administration(nutzer):
        return menge
    if not ist_lehrkraft(nutzer):
        return menge.none()
    regeln = _regeln(nutzer, recht)
    return menge.filter(
        Q(pk__in=regeln.values("dokument_id")) | Q(bereich__in=regeln.values("bereich_id"))
    )


def darf_redigieren(nutzer, dokument=None):
    menge = berechtigte_dokumente(nutzer, "bearbeiten")
    return (
        menge.filter(pk=dokument.pk).exists()
        if dokument
        else ist_administration(nutzer) or menge.exists()
    )


def vorlagen_dokumente(nutzer):
    from django.db.models import Q

    return sichtbare_dokumente(nutzer).filter(
        Q(pk__in=berechtigte_dokumente(nutzer, "bearbeiten"))
        | Q(pk__in=berechtigte_dokumente(nutzer, "freigeben"))
    )


def darf_vorlage(nutzer, dokument=None):
    menge = vorlagen_dokumente(nutzer)
    return (
        menge.filter(pk=dokument.pk).exists()
        if dokument
        else ist_administration(nutzer) or menge.exists()
    )


def sichtbare_beschluesse(nutzer, menge=None):
    from django.db.models import Q

    from kern.models import Beschluss, Dokument

    menge = Beschluss.objects.all() if menge is None else menge
    if not _angemeldet(nutzer):
        return menge.none()
    if ist_administration(nutzer):
        return menge
    verboten = Dokument.objects.exclude(pk__in=sichtbare_dokumente(nutzer))
    # Beschlusstext kann mehrere Dokumente betreffen: keine Teilfreigabe des Texts.
    return menge.exclude(
        Q(dokumente__in=verboten)
        | Q(beschlossene_versionen__eintrag__dokument__in=verboten)
        | Q(protokoll_eintrag__dokument__in=verboten)
        | Q(protokoll_anhang__dokument__in=verboten)
        | Q(protokoll_anhang__eintrag__dokument__in=verboten)
    ).distinct()


def darf_beschluss_zuruecknehmen(nutzer, beschluss):
    if ist_administration(nutzer):
        return True
    dokumente = beschluss.dokumente.all()
    return bool(
        dokumente.exists()
        and sichtbare_beschluesse(nutzer).filter(pk=beschluss.pk).exists()
        and all(darf_beschliessen(nutzer, d) for d in dokumente)
    )


# --- Lesen -----------------------------------------------------------------


def darf_lesen(nutzer, eintrag) -> bool:
    if not _angemeldet(nutzer) or not darf_dokument_lesen(nutzer, eintrag.dokument):
        return False
    if not ist_nur_lesend(nutzer):
        return True
    if eintrag.status == Status.ARCHIVIERT:
        return True
    if eintrag.beschlossene_version() is not None:
        return True
    # Bestehende Statusfreigaben ohne Versionsnachweis behalten ihren bisherigen
    # Zugang. Datierte Freigaben dürfen auf diesen Altbestandsweg nicht fallen.
    return bool(
        eintrag.status == Status.BESCHLOSSEN
        and not eintrag.wirksam_ab
        and not eintrag.wirksam_bis
        and not eintrag.versionen.filter(beschluss__isnull=False).exists()
    )


def zeigt_entwurf(nutzer, eintrag=None) -> bool:
    """Sieht dieser Nutzer den Arbeitsstand oder die beschlossene Fassung?

    Lesende bekommen immer die zuletzt beschlossene Fassung zu sehen, alle
    anderen den aktuellen Stand (SPEC.md Paragraf 6).
    """
    return not ist_nur_lesend(nutzer)


def sichtbare_eintraege(nutzer, menge):
    """Schränkt ein QuerySet auf das ein, was ``nutzer`` sehen darf."""
    if not _angemeldet(nutzer):
        return menge.none()
    menge = menge.filter(dokument__in=sichtbare_dokumente(nutzer))
    if ist_nur_lesend(nutzer):
        from django.db.models import Exists, OuterRef, Q

        from kern.models import Eintragsversion
        from kern.staende import gueltige_versionen

        nachweis = Eintragsversion.objects.filter(
            eintrag_id=OuterRef("pk"), beschluss__isnull=False
        )
        return (
            menge.annotate(_hat_freigabenachweis=Exists(nachweis))
            .filter(
                Q(status=Status.ARCHIVIERT)
                | Q(
                    status=Status.BESCHLOSSEN,
                    wirksam_ab__isnull=True,
                    wirksam_bis__isnull=True,
                    _hat_freigabenachweis=False,
                )
                | Q(pk__in=gueltige_versionen().values("eintrag_id"))
            )
            .distinct()
        )
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
    if not darf_dokument_lesen(nutzer, eintrag.dokument):
        return False
    if darf_redigieren(nutzer, eintrag.dokument):
        return True
    # Lehrkraft: nur Entwürfe, und nur eigene oder die der Arbeitsgruppe.
    if eintrag.status not in STATUS_VOR_BESCHLUSS:
        return False
    return gehoert_zum_arbeitsbereich(nutzer, eintrag)


def darf_anlegen(nutzer, dokument=None) -> bool:
    """Neue Einträge anlegen darf jede Lehrkraft."""
    return ist_lehrkraft(nutzer) and (dokument is None or darf_dokument_lesen(nutzer, dokument))


def darf_status_setzen(nutzer, eintrag, neuer_status: str) -> bool:
    if not _angemeldet(nutzer):
        return False
    if neuer_status in OEFFENTLICHE_STATUS:
        # „beschlossen“ und „archiviert“ entstehen ausschließlich über einen
        # Beschluss, den die Administration einträgt (SPEC.md §8.4).
        return (
            darf_beschliessen(nutzer, eintrag.dokument) if eintrag else ist_administration(nutzer)
        )
    if neuer_status == Status.ABGESTIMMT:
        return bool(eintrag and darf_redigieren(nutzer, eintrag.dokument))
    return darf_bearbeiten(nutzer, eintrag)


def darf_kommentieren(nutzer, eintrag) -> bool:
    return ist_lehrkraft(nutzer) and darf_lesen(nutzer, eintrag)


def darf_kommentar_erledigen(nutzer, kommentar) -> bool:
    if not darf_kommentieren(nutzer, kommentar.eintrag):
        return False
    return darf_redigieren(nutzer, kommentar.eintrag.dokument) or kommentar.autor_id == nutzer.pk


# --- Verwaltung ------------------------------------------------------------


def darf_dokument_anlegen(nutzer) -> bool:
    return ist_administration(nutzer)


def darf_beschliessen(nutzer, dokument=None) -> bool:
    menge = berechtigte_dokumente(nutzer, "freigeben")
    return (
        menge.filter(pk=dokument.pk).exists()
        if dokument
        else ist_administration(nutzer) or menge.exists()
    )


def darf_importieren(nutzer) -> bool:
    return ist_administration(nutzer)


def darf_schulische_festlegung_bearbeiten(nutzer, fach=None) -> bool:
    """Kompetenzen sind nur auswählbar – außer diesem einen Feld (SPEC.md §7.3)."""
    if ist_administration(nutzer):
        return True
    menge = berechtigte_dokumente(nutzer, "bearbeiten")
    return menge.filter(fach=fach).exists() if fach else menge.exists()


def darf_eigene_planung(nutzer) -> bool:
    return ist_lehrkraft(nutzer)


def sichtbare_versionen(nutzer, menge):
    """Lesende sehen ausschließlich tatsächlich freigegebene Fassungen."""
    if not _angemeldet(nutzer):
        return menge.none()
    menge = menge.filter(eintrag__dokument__in=sichtbare_dokumente(nutzer))
    if ist_nur_lesend(nutzer):
        return menge.filter(status__in=OEFFENTLICHE_STATUS, beschluss__isnull=False)
    return menge


def darf_arbeitsstand_lesen(nutzer):
    """Arbeitsvergleiche und Änderungen gehören zum internen Arbeitsstand."""
    return _angemeldet(nutzer) and not ist_nur_lesend(nutzer)
