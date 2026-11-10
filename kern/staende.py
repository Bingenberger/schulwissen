"""Nur lesbare Eintragsstände für Auswertungen, getrennt vom Arbeitsmodell."""

from dataclasses import dataclass

from django.db.models import Case, Exists, F, OuterRef, Prefetch, Q, Subquery, When
from django.utils import timezone

from kern.models import Eintrag, Eintragsversion, Status, Zieltyp


def gueltige_versionen():
    """Jüngste bereits wirksame Freigabe; Fristablauf reaktiviert keine alte Regel."""
    heute = timezone.localdate()
    begonnen = Eintragsversion.objects.filter(
        status=Status.BESCHLOSSEN,
        beschluss__isnull=False,
    ).filter(Q(wirksam_ab__isnull=True) | Q(wirksam_ab__lte=heute))
    neuere = begonnen.filter(
        eintrag_id=OuterRef("eintrag_id"), versionsnummer__gt=OuterRef("versionsnummer")
    )
    return (
        begonnen.annotate(_neuere_wirksame=Exists(neuere))
        .filter(
            Q(wirksam_bis__isnull=True) | Q(wirksam_bis__gte=heute),
            _neuere_wirksame=False,
        )
        .order_by("-versionsnummer")
    )


def mit_lesefassungen(menge):
    return menge.prefetch_related(
        Prefetch("versionen", queryset=gueltige_versionen(), to_attr="_gueltige_fassungen")
    )


def sichtbare_beschlussmetadaten(nutzer, version):
    """Die gültige Fassung bleibt lesbar, geschützte Beschlusstexte bleiben verborgen."""
    from copy import copy

    from kern import rechte

    if (
        version
        and version.beschluss_id
        and not rechte.sichtbare_beschluesse(nutzer).filter(pk=version.beschluss_id).exists()
    ):
        version = copy(version)
        version.beschluss = None
    return version


def lesestand(nutzer, eintrag):
    """Gemeinsame Fassungswahl; niemals den schreibbaren Eintrag verändern."""
    from kern import rechte

    if not rechte.darf_lesen(nutzer, eintrag):
        return None
    version = None
    if rechte.ist_nur_lesend(nutzer) or eintrag.status == Status.BESCHLOSSEN:
        version = eintrag.beschlossene_version()
        if version is None and not rechte.ist_nur_lesend(nutzer):
            version = eintrag.letzte_version()
    return Eintragsstand(eintrag, version)


def lesemenge(nutzer, menge, *, nur_beschlossene=False):
    """SQL-Projektion derselben Lesefassung, vor Suche, Filterung und Zählung."""
    from kern import rechte

    menge = rechte.sichtbare_eintraege(nutzer, menge)
    versionen = gueltige_versionen().filter(eintrag_id=OuterRef("pk"))
    felder = (
        "titel",
        "daten",
        "status",
        "suchtext",
        "suchvektor",
        "aufgabe",
        "kurzantwort",
        "suchbegriffe",
        "inhaltsart",
    )
    if nur_beschlossene:
        menge = menge.exclude(status=Status.ARCHIVIERT).filter(
            pk__in=gueltige_versionen().values("eintrag_id")
        )
    return (
        mit_lesefassungen(menge)
        .annotate(_leseversion=Subquery(versionen.values("pk")[:1]))
        .annotate(
            **{
                f"lese_{feld}": (
                    Case(
                        When(_leseversion__isnull=False, then=Subquery(versionen.values(feld)[:1])),
                        default=F(feld),
                    )
                    if nur_beschlossene or rechte.ist_nur_lesend(nutzer)
                    else Case(
                        When(
                            status=Status.BESCHLOSSEN,
                            _leseversion__isnull=False,
                            then=Subquery(versionen.values(feld)[:1]),
                        ),
                        default=F(feld),
                    )
                )
                for feld in felder
            }
        )
    )


def lesekontext(nutzer, eintrag):
    teile = [eintrag.dokument.titel]
    for eltern in eintrag.pfad:
        stand = lesestand(nutzer, eltern)
        titel = stand.titel if stand else "Noch nicht freigegeben"
        teile.append(f"{eltern.anzeige_nummer} {titel}")
    return " › ".join(teile)


def sichtbare_verweise(nutzer, verweise):
    """Automatische Zielbeschriftungen dürfen keine fremden Entwürfe verraten."""
    from kern import rechte

    ziel_ids = {str(v.get("ziel_id")) for v in verweise if v.get("ziel_typ") == Zieltyp.EINTRAG}
    ziele = {
        str(e.pk): lesestand(nutzer, e)
        for e in mit_lesefassungen(
            rechte.sichtbare_eintraege(
                nutzer, Eintrag.objects.filter(pk__in=[z for z in ziel_ids if z.isdigit()])
            )
        )
    }
    from kern.models import Anhang

    anhang_ids = [
        str(v.get("ziel_id"))
        for v in verweise
        if v.get("ziel_typ") == Zieltyp.ANHANG and str(v.get("ziel_id")).isdigit()
    ]
    anhaenge = (
        {str(a.pk): a for a in sichtbare_anhaenge(nutzer, Anhang.objects.filter(pk__in=anhang_ids))}
        if anhang_ids
        else {}
    )
    ergebnis = []
    for v in verweise:
        if v.get("ziel_typ") == Zieltyp.EINTRAG:
            ziel = ziele.get(str(v.get("ziel_id")))
            if ziel is None:
                continue
            v = {**v, "beschriftung": f"{ziel.kennung} {ziel.titel}"}
        if v.get("ziel_typ") == Zieltyp.ANHANG:
            ziel = anhaenge.get(str(v.get("ziel_id")))
            if ziel is None:
                continue
            v = {**v, "beschriftung": ziel.dateiname}
        ergebnis.append(v)
    return ergebnis


def sichtbare_anhaenge(nutzer, menge):
    """Neue oder seit der Freigabe geänderte Anlagen gehören zum Arbeitsstand.

    Das ist ein Zugriffsfilter, keine Fixierung externer Dateiversionen (AP09).
    Unveränderte Anlagen bleiben auch neben einem neuen Textentwurf erreichbar.
    """
    from django.db.models import Q

    from kern import rechte

    if not rechte._angemeldet(nutzer):
        return menge.none()
    dokumente = rechte.sichtbare_dokumente(nutzer)
    sichtbar = rechte.sichtbare_eintraege(nutzer, Eintrag.objects.all())
    menge = menge.filter(Q(dokument__isnull=True) | Q(dokument__in=dokumente)).filter(
        Q(eintrag__isnull=True) | Q(eintrag__in=sichtbar)
    ).filter(
        Q(nextcloud_ordner__isnull=True)
        | Q(nextcloud_ordner__in=rechte.sichtbare_nextcloud_ordner(nutzer), nextcloud_verfuegbar=True)
    )
    if not rechte.ist_nur_lesend(nutzer):
        return menge
    versionen = gueltige_versionen().filter(eintrag_id=OuterRef("eintrag_id"))
    sichtbar = rechte.sichtbare_eintraege(nutzer, Eintrag.objects.all())
    return menge.annotate(_freigabe=Subquery(versionen.values("freigegeben_am")[:1])).filter(
        Q(eintrag__isnull=True) | (Q(eintrag__in=sichtbar) & Q(geaendert_am__lte=F("_freigabe")))
    )


@dataclass(frozen=True)
class Eintragsstand:
    eintrag: Eintrag
    version: Eintragsversion | None = None

    def __getattr__(self, name):
        from kern.models import PFLEGE_FELDER

        if self.version and (name in PFLEGE_FELDER or name.removesuffix("_id") in PFLEGE_FELDER):
            return getattr(self.version, name)
        # Unversionierte Strukturangaben (Kennung, Dokument, Nummer) weiterreichen.
        return getattr(self.eintrag, name)

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
    def geaendert_am(self):
        if self.version:
            return self.version.freigegeben_am or self.version.zeitpunkt
        return self.eintrag.geaendert_am

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
                queryset=gueltige_versionen(),
                to_attr="_gueltige_fassungen",
            )
        )
        return [Eintragsstand(e, e._gueltige_fassungen[0]) for e in menge if e._gueltige_fassungen]
    return [Eintragsstand(e) for e in menge.prefetch_related("verlinkungen")]
