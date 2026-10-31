"""Ansichten rund um Beschlüsse, Fassungen und Änderungen (SPEC.md §8)."""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from kern import beschluesse, rechte, vergleich, views
from kern.models import Anhang, Beschluss, Eintrag, Eintragsversion, Gremium
from kern.staende import sichtbare_anhaenge, sichtbare_beschlussmetadaten


class BeschlussFormular(forms.ModelForm):
    class Meta:
        model = Beschluss
        fields = ["datum", "gremium", "titel", "text", "protokoll_eintrag", "protokoll_anhang"]
        widgets = {
            "datum": forms.DateInput(attrs={"type": "date"}),
            "text": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {"text": "Beschlusstext"}
        help_texts = {
            "titel": "Worum ging es? Zum Beispiel „Arbeitsplan Deutsch, Kapitel 2.1 bis 2.5“.",
            "text": "Der Wortlaut aus dem Protokoll.",
        }

    def __init__(self, *args, nutzer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gremium"].queryset = Gremium.objects.all()
        self.fields["protokoll_eintrag"].queryset = rechte.sichtbare_eintraege(
            nutzer, Eintrag.objects.all()
        ).filter(dokument__dokumenttyp__schluessel="protokoll")
        self.fields["protokoll_anhang"].required = False
        self.fields["protokoll_anhang"].queryset = sichtbare_anhaenge(nutzer, Anhang.objects.all())


@login_required
def beschluesse_liste(request):
    return render(
        request,
        "kern/beschluesse.html",
        {
            "beschluesse": rechte.sichtbare_beschluesse(request.user)
            .select_related("gremium")
            .annotate(
                anzahl=Count(
                    "beschlossene_versionen",
                    filter=Q(
                        beschlossene_versionen__in=rechte.sichtbare_versionen(
                            request.user, Eintragsversion.objects.all()
                        )
                    ),
                )
            ),
            "darf_beschliessen": rechte.darf_beschliessen(request.user),
        },
    )


@login_required
def beschluss_ansehen(request, beschluss_id: int):
    beschluss = get_object_or_404(
        rechte.sichtbare_beschluesse(request.user).select_related("gremium"), pk=beschluss_id
    )
    versionen = (
        rechte.sichtbare_versionen(request.user, beschluss.beschlossene_versionen.all())
        .select_related("eintrag", "eintrag__dokument")
        .order_by("eintrag__kennung")
    )

    return render(
        request,
        "kern/beschluss.html",
        {
            "beschluss": beschluss,
            "versionen": versionen,
            "protokoll_anhang": sichtbare_anhaenge(
                request.user, Anhang.objects.filter(pk=beschluss.protokoll_anhang_id)
            ).first()
            if beschluss.protokoll_anhang_id
            else None,
            "darf_beschliessen": rechte.darf_beschluss_zuruecknehmen(request.user, beschluss),
        },
    )


@login_required
def beschlussvorlage(request, schluessel: str = ""):
    """Was könnte in die nächste Konferenz? (SPEC.md §8.3)"""
    if not rechte.darf_vorlage(request.user):
        raise PermissionDenied(
            "Beschlussvorlagen stellt die Redaktion oder die Administration zusammen."
        )
    dokument = (
        get_object_or_404(rechte.sichtbare_dokumente(request.user), schluessel=schluessel)
        if schluessel
        else None
    )
    if dokument and not rechte.darf_vorlage(request.user, dokument):
        raise PermissionDenied("Für dieses Dokument fehlt die redaktionelle Berechtigung.")
    kandidaten = beschluesse.vorlage_kandidaten(dokument).filter(
        dokument__in=rechte.vorlagen_dokumente(request.user)
    )

    return render(
        request,
        "kern/beschlussvorlage.html",
        {
            "dokument": dokument,
            "kandidaten": kandidaten,
            "dokumente": rechte.vorlagen_dokumente(request.user).order_by("titel"),
            "darf_beschliessen": rechte.darf_beschliessen(request.user),
        },
    )


@login_required
@transaction.atomic
def beschluss_anlegen(request):
    """Beschluss eintragen und Fassungen freischalten (SPEC.md §8.4)."""
    if not rechte.darf_beschliessen(request.user):
        raise PermissionDenied("Beschlüsse trägt die Administration ein.")

    ausgewaehlt = request.POST.getlist("eintrag") or request.GET.getlist("eintrag")
    if any(not wert.isdecimal() for wert in ausgewaehlt):
        raise PermissionDenied("Ungültige Auswahl.")
    eintraege = list(
        Eintrag.objects.filter(
            pk__in=ausgewaehlt, dokument__in=rechte.berechtigte_dokumente(request.user, "freigeben")
        )
        .select_related("dokument")
        .order_by("kennung")
    )

    if {str(e.pk) for e in eintraege} != set(ausgewaehlt):
        raise PermissionDenied("Für die Auswahl fehlt die Freigabeberechtigung.")

    if request.method == "POST" and request.POST.get("speichern"):
        formular = BeschlussFormular(request.POST, nutzer=request.user)
        if not eintraege:
            formular.add_error(None, "Bitte mindestens einen Eintrag auswählen.")
        if formular.is_valid():
            beschluss = formular.save(commit=False)
            beschluss.erstellt_von = request.user
            try:
                with transaction.atomic():
                    beschluss.save()
                    bericht = beschluesse.beschluss_fassen(
                        beschluss, eintraege, nutzer=request.user
                    )
            except ValidationError as fehler:
                formular.add_error(None, " ".join(fehler.messages))
            else:
                messages.success(
                    request,
                    f"Beschluss eingetragen: {bericht.beschlossen} Fassungen sind jetzt gültig, "
                    f"{bericht.archiviert} ältere wurden archiviert.",
                )
                for hinweis in bericht.uebersprungen:
                    messages.warning(request, hinweis)
                return redirect("kern:beschluss", beschluss_id=beschluss.pk)
    else:
        formular = BeschlussFormular(nutzer=request.user)

    return render(
        request,
        "kern/beschluss_anlegen.html",
        {"formular": formular, "eintraege": eintraege},
    )


@login_required
@require_POST
def beschluss_zuruecknehmen(request, beschluss_id: int):
    if not rechte.darf_beschliessen(request.user):
        raise PermissionDenied("Beschlüsse nimmt nur die Administration zurück.")
    beschluss = get_object_or_404(rechte.sichtbare_beschluesse(request.user), pk=beschluss_id)

    if not rechte.darf_beschluss_zuruecknehmen(request.user, beschluss):
        raise PermissionDenied("Für diesen Beschluss fehlt die Freigabeberechtigung.")
    anzahl = beschluesse.beschluss_zuruecknehmen(beschluss, nutzer=request.user)
    messages.success(
        request,
        f"Der Beschluss wurde zurückgenommen, {anzahl} Fassungen sind wieder "
        "„abgestimmt in Gruppe“. Der Beschluss selbst bleibt als Eintrag erhalten.",
    )
    return redirect("kern:beschluss", beschluss_id=beschluss.pk)


@login_required
def fassungen_vergleichen(request, schluessel: str, kennung: str):
    """Zwei Fassungen gegenüberstellen (SPEC.md §6, Diff-Ansicht)."""
    eintrag = get_object_or_404(
        Eintrag.objects.select_related("dokument"),
        dokument__schluessel=schluessel,
        kennung=kennung,
    )
    if not rechte.darf_lesen(request.user, eintrag):
        raise PermissionDenied("Dieser Eintrag ist noch nicht freigegeben.")

    sichtbare = rechte.sichtbare_versionen(
        request.user, eintrag.versionen.select_related("autor", "beschluss")
    )
    # Auch gezielt angefragte Entwurfsnummern werden nicht stillschweigend ersetzt.
    for name in ("alt", "neu"):
        nummer = request.GET.get(name)
        if nummer and not rechte.zeigt_entwurf(request.user):
            get_object_or_404(sichtbare, versionsnummer=nummer if nummer.isdigit() else -1)
    alle = list(sichtbare.order_by("versionsnummer"))
    if len(alle) < 2:
        messages.info(request, "Für einen Vergleich braucht es mindestens zwei Fassungen.")
        return redirect("kern:fassungen", schluessel=schluessel, kennung=kennung)

    def version_holen(name, vorgabe):
        nummer = request.GET.get(name)
        if nummer and nummer.isdigit():
            treffer = next((v for v in alle if v.versionsnummer == int(nummer)), None)
            if treffer is not None:
                return treffer
        return vorgabe

    # Vorgabe: die beschlossene Fassung gegen den aktuellen Stand – das ist die
    # Frage, die vor einer Konferenz zählt.
    beschlossen = eintrag.beschlossene_version()
    vorgabe_alt = (beschlossen or alle[-2]) if rechte.zeigt_entwurf(request.user) else alle[-2]
    alt = version_holen("alt", vorgabe_alt)
    neu = version_holen("neu", alle[-1])

    return render(
        request,
        "kern/vergleich.html",
        {
            "dokument": eintrag.dokument,
            "eintrag": eintrag,
            "versionen": list(reversed(alle)),
            "alt": alt,
            "neu": neu,
            "vergleich": vergleich.vergleichen(alt, neu, request.user),
        },
    )


@login_required
def aenderungen(request, schluessel: str):
    """Was hat sich seit dem letzten Beschluss getan? (SPEC.md §8.6)"""
    if not rechte.darf_arbeitsstand_lesen(request.user):
        raise PermissionDenied("Änderungen am Arbeitsstand sind dem Kollegium vorbehalten.")
    dokument = get_object_or_404(rechte.sichtbare_dokumente(request.user), schluessel=schluessel)
    uebersicht = beschluesse.aenderungen_seit_beschluss(dokument)

    return render(
        request,
        "kern/aenderungen.html",
        {
            "dokument": dokument,
            "neu": uebersicht["neu"],
            "geaendert": uebersicht["geaendert"],
            "unveraendert": uebersicht["unveraendert"],
            "darf_beschliessen": rechte.darf_beschliessen(request.user),
        },
    )


@login_required
def version_ansehen(request, schluessel: str, kennung: str, nummer: int):
    """Eine einzelne, alte Fassung im Wortlaut."""
    eintrag = get_object_or_404(
        Eintrag.objects.select_related("dokument"),
        dokument__schluessel=schluessel,
        kennung=kennung,
    )
    if not rechte.darf_lesen(request.user, eintrag):
        raise PermissionDenied("Dieser Eintrag ist noch nicht freigegeben.")
    version = get_object_or_404(
        rechte.sichtbare_versionen(request.user, eintrag.versionen.all()), versionsnummer=nummer
    )

    version = sichtbare_beschlussmetadaten(request.user, version)
    verweise = views.verweise_aus_schnappschuss(version, request.user)
    bloecke = list(views.bloecke_zum_lesen(eintrag.typ, version.daten, verweise))
    prozess = None
    if eintrag.eintragstyp == "prozess":
        from kern import prozesslesen

        prozess = prozesslesen.aufbereiten(eintrag, version.daten, request.user, version)
        bloecke = prozesslesen.ohne_ablauf(bloecke)

    return render(
        request,
        "kern/version.html",
        {
            "dokument": eintrag.dokument,
            "eintrag": eintrag,
            "version": version,
            "typ": eintrag.typ,
            "bloecke": bloecke,
            "prozess": prozess,
        },
    )
