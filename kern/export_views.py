"""Downloads mit den Rollenrechten für Dokumentexport und Beschlussvorlagen."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from kern import beschluesse, exporte, rechte, vergleich
from kern.models import Dokument


def download(inhalt, mimetype, name):
    antwort = HttpResponse(inhalt, content_type=mimetype)
    antwort["Content-Disposition"] = f'attachment; filename="{name}"'
    return antwort


@login_required
def export(request, schluessel, format):
    if not rechte.ist_administration(request.user):
        raise PermissionDenied("Dokumente exportiert die Administration.")
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    if format == "json":
        return download(exporte.dokument_json(dokument), "application/json", f"{schluessel}.json")
    if format == "pdf":
        return download(exporte.dokument_pdf(dokument), "application/pdf", f"{schluessel}.pdf")
    if format == "xlsx" and dokument.dokumenttyp.schluessel == "arbeitsplan_deutsch":
        return download(
            exporte.dokument_xlsx(dokument),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{schluessel}.xlsx",
        )
    raise Http404("Dieses Exportformat ist für das Dokument nicht verfügbar.")


@login_required
def vorlage_pdf(request):
    if not rechte.ist_redaktion(request.user):
        raise PermissionDenied("Beschlussvorlagen stellt die Redaktion zusammen.")
    kandidaten = beschluesse.vorlage_kandidaten()
    auswahl = (request.POST if request.method == "POST" else request.GET).getlist("eintrag")
    if not auswahl or any(not wert.isdigit() for wert in auswahl):
        return HttpResponse("Bitte mindestens einen abgestimmten Eintrag auswählen.", status=400)
    kandidaten = list(kandidaten.filter(pk__in=auswahl))
    if {str(e.pk) for e in kandidaten} != set(auswahl):
        return HttpResponse("Die Auswahl enthält nicht abgestimmte Einträge.", status=400)
    zeilen = []
    for e in kandidaten:
        zeile = exporte.pdf_zeile(e)
        alt, neu = e.beschlossene_version(), e.letzte_version()
        if alt and neu:
            zeile["vergleich"] = vergleich.vergleichen(alt, neu)
        zeilen.append(zeile)
    return download(
        exporte.pdf_rendern(
            {
                "titel": "Beschlussvorlage",
                "zeilen": zeilen,
                "ist_vorlage": True,
            }
        ),
        "application/pdf",
        "beschlussvorlage.pdf",
    )
