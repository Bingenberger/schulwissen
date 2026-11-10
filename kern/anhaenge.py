"""Geschützte Dateivorschau und Entfernen unbenutzter Anhänge."""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods

from eintragstypen import dienste
from kern import nextcloud, rechte
from kern.dateifassungen import originalstand
from kern.models import Anhang, Eintrag, Eintragsversion, Verlinkung, Zieltyp
from kern.staende import sichtbare_anhaenge

logger = logging.getLogger(__name__)


def loeschhindernis(anhang):
    if anhang.freigabekopien.exists():
        return "Dieser Anhang gehört zu einer gesicherten Freigabefassung und bleibt erhalten."
    ziel = {"ziel_typ": Zieltyp.ANHANG, "ziel_id": str(anhang.pk)}
    if (
        Verlinkung.objects.filter(**ziel).exists()
        or Eintragsversion.objects.filter(verlinkungen__contains=[ziel]).exists()
    ):
        return "Andere Einträge oder gespeicherte Fassungen verwenden diesen Anhang."
    return ""


def entfernen(anhang):
    grund = loeschhindernis(anhang)
    if grund:
        raise ValidationError(grund)
    name, speicher = anhang.datei.name, anhang.datei.storage
    anhang.delete()
    if name:

        def datei_entfernen():
            if not Anhang.objects.filter(datei=name).exists():
                try:
                    speicher.delete(name)
                except OSError:
                    logger.exception("Entfernte Anhangdatei konnte nicht bereinigt werden.")

        transaction.on_commit(datei_entfernen)


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def loeschen(request, schluessel, kennung, pk):
    dokument = get_object_or_404(
        rechte.sichtbare_dokumente(request.user).select_for_update(of=("self",)),
        schluessel=schluessel,
    )
    eintrag = get_object_or_404(
        Eintrag.objects.select_for_update(), dokument=dokument, kennung=kennung
    )
    if not rechte.darf_bearbeiten(request.user, eintrag):
        raise PermissionDenied("Diesen Anhang darfst du nicht löschen.")
    anhang = get_object_or_404(Anhang.objects.select_for_update(), eintrag=eintrag, pk=pk)
    grund = loeschhindernis(anhang)
    stand = {"nutzer": request.user.pk, "anhang": pk, "stand": originalstand(anhang)}
    if request.method == "POST":
        try:
            bestaetigt = signing.loads(
                request.POST.get("stand", ""), salt="anhang-loeschen", max_age=3600
            )
        except signing.BadSignature:
            bestaetigt = None
        if bestaetigt != stand:
            grund = "Die Datei oder ihre Angaben haben sich geändert. Bitte prüfe erneut."
    if request.method == "POST" and not grund:
        name = anhang.dateiname
        entfernen(anhang)
        dienste.suchtext_aktualisieren(eintrag)
        messages.success(request, f"Der Anhang „{name}“ wurde entfernt.")
        return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)
    return render(request, "kern/anhang_loeschen.html", {
        "dokument": dokument, "eintrag": eintrag, "anhang": anhang, "grund": grund,
        "stand": signing.dumps(stand, salt="anhang-loeschen"),
    }, status=409 if request.method == "POST" else 200)


def _hinweis(request, text):
    antwort = render(request, "kern/anhang_vorschau_hinweis.html", {"text": text})
    antwort["Cache-Control"] = "private, no-store"
    return antwort


def _dateiantwort(request, datei, name):
    """Nur passive Formate einbetten; weder Dateiendung noch fremdem MIME vertrauen."""
    try:
        kopf = datei.read(512)
        datei.seek(0)
    except Exception:
        datei.close()
        raise
    typ = ""
    if kopf.startswith(b"%PDF-"):
        typ = "application/pdf"
    elif kopf.startswith(b"\x89PNG\r\n\x1a\n"):
        typ = "image/png"
    elif kopf.startswith(b"\xff\xd8\xff"):
        typ = "image/jpeg"
    elif kopf.startswith((b"GIF87a", b"GIF89a")):
        typ = "image/gif"
    elif kopf.startswith(b"RIFF") and kopf[8:12] == b"WEBP":
        typ = "image/webp"
    if not typ:
        datei.close()
        return _hinweis(
            request,
            "Für dieses Dateiformat ist keine eingebettete Vorschau verfügbar. "
            "Bitte öffne die Originaldatei. PDF-Dateien und Bilder können angezeigt werden.",
        )
    antwort = FileResponse(datei, content_type=typ, as_attachment=False, filename=name)
    antwort["Cache-Control"] = "private, no-store"
    antwort["X-Content-Type-Options"] = "nosniff"
    antwort["Content-Security-Policy"] = "frame-ancestors 'self'"
    return antwort


def _nextcloud_antwort(request, pfad, name):
    ordner = TemporaryDirectory(prefix="schulwissen-vorschau-")
    try:
        ziel = Path(ordner.name) / "datei"
        ergebnis = nextcloud.herunterladen(pfad, ziel)
        if ergebnis.status != 200:
            ordner.cleanup()
            return _hinweis(request, "Diese Nextcloud-Datei ist derzeit nicht verfügbar.")
        antwort = _dateiantwort(request, ziel.open("rb"), name)
        # Die temporäre Datei lebt nur bis zum Ende der HTTP-Antwort.
        antwort._resource_closers.append(ordner.cleanup)
        return antwort
    except nextcloud.NextcloudFehler:
        ordner.cleanup()
        return _hinweis(request, "Die Nextcloud-Vorschau ist derzeit nicht verfügbar.")
    except Exception:
        ordner.cleanup()
        raise


@login_required
@require_GET
@xframe_options_sameorigin
def vorschau(request, pk):
    anhang = get_object_or_404(sichtbare_anhaenge(request.user, Anhang.objects.all()), pk=pk)
    if anhang.datei:
        try:
            return _dateiantwort(request, anhang.datei.open("rb"), anhang.dateiname)
        except (OSError, ValueError) as fehler:
            raise Http404("Die Datei ist nicht verfügbar.") from fehler
    if anhang.nextcloud_pfad:
        return _nextcloud_antwort(request, anhang.nextcloud_pfad, anhang.dateiname)
    return _hinweis(
        request,
        "Für diesen Freigabe-Link ist keine Vorschau verfügbar. "
        "Bitte öffne die Datei in der Nextcloud.",
    )


@login_required
@require_GET
@xframe_options_sameorigin
def nextcloud_vorschau(request, schluessel):
    dokument = get_object_or_404(rechte.sichtbare_dokumente(request.user), schluessel=schluessel)
    try:
        daten = signing.loads(request.GET.get("auswahl", ""), salt="anhang-erfassung")
    except signing.BadSignature as fehler:
        raise PermissionDenied("Die Dateiauswahl ist ungültig.") from fehler
    if daten["nutzer"] != request.user.pk or daten["dokument"] != dokument.pk:
        raise PermissionDenied("Diese Dateiauswahl ist nicht zugänglich.")
    kennung = request.GET.get("kennung")
    if kennung:
        eintrag = get_object_or_404(Eintrag, dokument=dokument, kennung=kennung)
        erlaubt = rechte.darf_bearbeiten(request.user, eintrag)
    else:
        erlaubt = rechte.darf_anlegen(request.user, dokument)
    if not erlaubt:
        raise PermissionDenied("Die Bearbeitungsberechtigung ist nicht mehr vorhanden.")
    return _nextcloud_antwort(request, daten["pfad"], daten["name"])
