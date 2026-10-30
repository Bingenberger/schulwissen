"""Vollständige, durchsuchbare Listen hinter den begrenzten Startseitenbereichen."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from kern import rechte
from kern.models import Dokument, Eintrag, Status


@login_required
def dokumente(request):
    begriff = (request.GET.get("q") or "").strip()
    menge = Dokument.objects.select_related("dokumenttyp").annotate(anzahl=Count("eintraege"))
    if begriff:
        menge = menge.filter(Q(titel__icontains=begriff) | Q(beschreibung__icontains=begriff))
    seite = Paginator(menge.order_by("titel", "pk"), 12).get_page(request.GET.get("seite"))
    return render(request, "kern/dokumentliste.html", {"seite": seite, "begriff": begriff})


@login_required
def eigene_entwuerfe(request):
    if not rechte.ist_lehrkraft(request.user):
        raise PermissionDenied
    begriff = (request.GET.get("q") or "").strip()
    menge = (
        Eintrag.objects.filter(status__in=[Status.IDEE, Status.ENTWURF])
        .filter(Q(erstellt_von=request.user) | Q(verantwortlich_person=request.user))
        .select_related("dokument")
    )
    if begriff:
        menge = menge.filter(Q(titel__icontains=begriff) | Q(dokument__titel__icontains=begriff))
    seite = Paginator(menge.order_by("-geaendert_am", "pk"), 20).get_page(request.GET.get("seite"))
    return render(request, "kern/entwurfsliste.html", {"seite": seite, "begriff": begriff})
