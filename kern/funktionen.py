"""Schulische Zuständigkeiten auflösen und Besetzungen nachvollziehbar wechseln."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from kern import rechte
from kern.models import Besetzungsart, Besetzungsmodus, Funktionsbesetzung, Nutzer, Schulfunktion


@dataclass(frozen=True)
class Funktionsauskunft:
    funktion: Schulfunktion
    bereich: object = None
    stichtag: date = field(default_factory=timezone.localdate)
    zustaendige: tuple = ()
    hauptbesetzungen: tuple = ()
    vertretungen: tuple = ()
    status: str = "unbesetzt"
    status_text: str = "Derzeit nicht besetzt"
    hinweis: str = ""


def aufloesen(funktion, bereich=None, stichtag=None, besetzungen=None):
    """Datum und exakter Funktionsbereich; keine Rechteprüfung oder implizite Ersatzperson.

    Die Gültigkeitsgrenzen sind einschließlich. Für die Erreichbarkeit zählen die
    aktuell aktiven Konten. Damals gespeicherte Konfigurationen stehen in der Historie.
    Eine numerische Kennung lädt die Funktion frisch; Aufrufer dürfen Objekte nicht cachen.
    """
    if not isinstance(funktion, Schulfunktion):
        funktion = Schulfunktion.objects.get(pk=funktion)
    stichtag = stichtag or timezone.localdate()
    basis = {"funktion": funktion, "bereich": bereich, "stichtag": stichtag}
    if funktion.archiviert:
        return Funktionsauskunft(**basis, status="archiviert", status_text="Funktion archiviert")
    alle = (
        list(besetzungen)
        if besetzungen is not None
        else list(
            funktion.besetzungen.select_related("person", "bereich").order_by(
                "person__anzeigename", "pk"
            )
        )
    )
    bereich_id = getattr(bereich, "pk", bereich)
    passend = [
        b
        for b in alle
        if b.bereich_id == bereich_id
        and not b.storniert
        and b.gueltig_ab <= stichtag
        and (b.gueltig_bis is None or b.gueltig_bis >= stichtag)
    ]
    aktiv = [b for b in passend if b.person.is_active]
    haupt = tuple(b for b in aktiv if b.art == Besetzungsart.HAUPT)
    vertretungen = tuple(b for b in aktiv if b.art == Besetzungsart.VERTRETUNG)
    uebernehmen = tuple(b for b in vertretungen if b.vertretung_aktiv)
    einzel = funktion.besetzungsmodus == Besetzungsmodus.EINZEL
    if einzel and (len(haupt) > 1 or len(vertretungen) > 1):
        return Funktionsauskunft(
            **basis,
            status="pruefen",
            status_text="Besetzung bitte prüfen",
            hinweis=(
                "Mehrere Einzelbesetzungen widersprechen sich. Bitte die Administration ansprechen."
            ),
        )
    kontakt = (
        (uebernehmen or haupt)
        if einzel
        else tuple({b.person_id: b for b in (*haupt, *uebernehmen)}.values())
    )
    hinweis = (
        "Eine zugeordnete Person hat kein aktives Konto. Bitte die Besetzung prüfen."
        if len(aktiv) != len(passend)
        else ""
    )
    if uebernehmen:
        status, text = (
            "vertretung",
            "Vertretung übernimmt" if einzel else "Team mit aktiver Vertretung",
        )
    elif kontakt:
        status, text = "besetzt", "Team zuständig" if not einzel else "Besetzt"
    elif hinweis:
        status, text = "pruefen", "Besetzung bitte prüfen"
    else:
        status, text = "unbesetzt", "Derzeit nicht besetzt"
        zeitlich = [b for b in alle if b.bereich_id == bereich_id and not b.storniert]
        if any(b.gueltig_ab > stichtag for b in zeitlich):
            status, text = "geplant", "Besetzung erst künftig vorgesehen"
        elif any(b.gueltig_bis and b.gueltig_bis < stichtag for b in zeitlich):
            status, text = "abgelaufen", "Bisherige Besetzung abgelaufen"
    return Funktionsauskunft(
        **basis,
        zustaendige=kontakt,
        hauptbesetzungen=haupt,
        vertretungen=vertretungen,
        status=status,
        status_text=text,
        hinweis=hinweis,
    )


def auskuenfte(funktion):
    """Allgemeine und benannte Zuständigkeiten getrennt aus derselben Quelle."""
    besetzungen = list(
        funktion.besetzungen.select_related("person", "bereich").order_by(
            "person__anzeigename", "pk"
        )
    )
    bereiche = {b.bereich_id: b.bereich for b in besetzungen if b.bereich_id and not b.storniert}
    return [aufloesen(funktion, besetzungen=besetzungen)] + [
        aufloesen(funktion, bereich=bereich, besetzungen=besetzungen)
        for bereich in sorted(bereiche.values(), key=lambda b: (b.name, b.pk))
    ]


@transaction.atomic
def wechseln(besetzung, neue_person, wechsel_ab, autor=None, erwartete_revision=None):
    if autor is not None and not rechte.ist_administration(autor):
        raise PermissionDenied("Besetzungen wechselt die Administration.")
    Schulfunktion.objects.select_for_update(of=("self",)).get(pk=besetzung.funktion_id)
    alt = Funktionsbesetzung.objects.select_for_update(of=("self",)).get(pk=besetzung.pk)
    erwartet = besetzung.revision if erwartete_revision is None else erwartete_revision
    if alt.revision != erwartet:
        raise ValidationError(
            "Die Besetzung wurde inzwischen geändert. Bitte prüfe den aktuellen Stand erneut."
        )
    if alt.storniert or alt.funktion.archiviert:
        raise ValidationError(
            "Stornierte Besetzungen oder archivierte Funktionen werden nicht umbesetzt."
        )
    neue_person = Nutzer.objects.get(pk=neue_person.pk)
    if not neue_person.is_active:
        raise ValidationError("Bitte ein aktives vorhandenes Nutzerkonto auswählen.")
    if neue_person.pk == alt.person_id:
        raise ValidationError("Diese Person besetzt die Funktion bereits.")
    if wechsel_ab < alt.gueltig_ab or (alt.gueltig_bis and wechsel_ab > alt.gueltig_bis):
        raise ValidationError(
            "Der Wechsel muss innerhalb des bisherigen Gültigkeitszeitraums liegen."
        )
    ende = alt.gueltig_bis
    if wechsel_ab == alt.gueltig_ab:
        alt.storniert = True
    else:
        alt.gueltig_bis = wechsel_ab - timedelta(days=1)
    alt.save(autor=autor)
    return _neue_besetzung(alt, neue_person, wechsel_ab, ende, autor)


def _neue_besetzung(alt, person, ab, bis, autor):
    neu = Funktionsbesetzung(
        funktion=alt.funktion,
        person=person,
        bereich=alt.bereich,
        art=alt.art,
        vertretung_aktiv=alt.vertretung_aktiv,
        gueltig_ab=ab,
        gueltig_bis=bis,
    )
    neu.save(autor=autor)
    return neu


@login_required
def verzeichnis(request):
    if not rechte._angemeldet(request.user):
        raise PermissionDenied("Bitte melde dich mit einem aktiven Konto an.")
    begriff = (request.GET.get("q") or "").strip()[:200]
    menge = Schulfunktion.objects.filter(archiviert=False)
    if begriff:
        heute = timezone.localdate()
        personen = Funktionsbesetzung.objects.filter(
            person__is_active=True,
            person__anzeigename__icontains=begriff,
            storniert=False,
            gueltig_ab__lte=heute,
        ).filter(Q(gueltig_bis__isnull=True) | Q(gueltig_bis__gte=heute))
        menge = menge.filter(
            Q(name__icontains=begriff)
            | Q(aufgabe__icontains=begriff)
            | Q(schluessel__icontains=begriff)
            | Q(pk__in=personen.values("funktion_id"))
        )
    seite = Paginator(menge.order_by("name", "pk"), 12).get_page(request.GET.get("seite"))
    return render(
        request,
        "kern/funktionen.html",
        {
            "seite": seite,
            "begriff": begriff,
            "karten": [{"funktion": f, "auskuenfte": auskuenfte(f)} for f in seite],
            "stichtag": timezone.localdate(),
        },
    )


@login_required
def detail(request, schluessel):
    if not rechte._angemeldet(request.user):
        raise PermissionDenied("Bitte melde dich mit einem aktiven Konto an.")
    funktion = get_object_or_404(Schulfunktion, schluessel=schluessel)
    return render(
        request,
        "kern/funktionen.html",
        {
            "funktion": funktion,
            "karten": [{"funktion": funktion, "auskuenfte": auskuenfte(funktion)}],
            "stichtag": timezone.localdate(),
        },
    )
