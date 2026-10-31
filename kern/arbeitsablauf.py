"""Löschen unbeschlossener Einträge und gemeinsame Genehmigung eines Protokolls."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from eintragstypen import dienste
from kern import beschluesse, rechte
from kern.beschluss_views import BeschlussFormular
from kern.models import (
    Eintrag,
    Eintragsversion,
    Gremium,
    ReservierteKennung,
    Status,
    Verlinkung,
    Zieltyp,
)


def loeschhindernisse(eintrag):
    gruende = []
    if (
        eintrag.status in rechte.OEFFENTLICHE_STATUS
        or eintrag.versionen.filter(
            Q(beschluss__isnull=False) | Q(status__in=rechte.OEFFENTLICHE_STATUS)
        ).exists()
        or eintrag.protokollierte_beschluesse.exists()
    ):
        gruende.append("Dieser Eintrag gehört zu einer Freigabe. Seine Fassungen bleiben erhalten.")
    if eintrag.kinder.exists():
        gruende.append(
            "Dieser Eintrag enthält untergeordnete Einträge. Entferne oder verschiebe diese zuerst."
        )
    if (
        Verlinkung.objects.filter(ziel_typ=Zieltyp.EINTRAG, ziel_id=str(eintrag.pk))
        .exclude(von_eintrag=eintrag)
        .exists()
        or Eintragsversion.objects.exclude(eintrag=eintrag)
        .filter(verlinkungen__contains=[{"ziel_typ": Zieltyp.EINTRAG, "ziel_id": str(eintrag.pk)}])
        .exists()
    ):
        gruende.append("Andere Einträge oder gespeicherte Fassungen verweisen hierher.")
    if eintrag.fortschritt.exists():
        gruende.append("Dieser Eintrag wird bereits in persönlichen Planungen verwendet.")
    if eintrag.kommentare.exists():
        gruende.append(
            "Zu diesem Eintrag gibt es Kommentare. Die gemeinsame Arbeit bleibt erhalten."
        )
    if eintrag.anhaenge.exists():
        gruende.append(
            "An diesem Eintrag hängen Dateien. Damit keine Dateien verloren gehen, "
            "ist das Löschen gesperrt."
        )
    return gruende


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def eintrag_loeschen(request, schluessel, kennung):
    dokument = get_object_or_404(
        rechte.sichtbare_dokumente(request.user).select_for_update(of=("self",)),
        schluessel=schluessel,
    )
    eintrag = get_object_or_404(
        Eintrag.objects.select_for_update(), dokument=dokument, kennung=kennung
    )
    if not rechte.darf_bearbeiten(request.user, eintrag):
        raise PermissionDenied("Diesen Eintrag darfst du nicht löschen.")
    gruende = loeschhindernisse(eintrag)
    if request.method == "POST" and not gruende:
        titel = eintrag.titel
        ReservierteKennung.objects.create(dokument=dokument, kennung=eintrag.kennung)
        eintrag.delete()
        messages.success(request, f"„{titel}“ wurde gelöscht.")
        return redirect("kern:dokument", schluessel=schluessel)
    return render(
        request,
        "kern/eintrag_loeschen.html",
        {"eintrag": eintrag, "dokument": dokument, "gruende": gruende},
        status=409 if request.method == "POST" else 200,
    )


class ProtokollBeschlussFormular(forms.ModelForm):
    class Meta(BeschlussFormular.Meta):
        fields = ["datum", "gremium", "titel", "text"]
        widgets = {
            "datum": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "text": forms.Textarea(attrs={"rows": 5}),
        }


def _stand(dokument, eintraege):
    return {
        "dokument": dokument.pk,
        "eintraege": [
            [
                e.pk,
                e.geaendert_am.isoformat(),
                e.letzte_version().pk if e.letzte_version() else None,
            ]
            for e in eintraege
        ],
    }


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def protokoll_beschliessen(request, schluessel):
    if not rechte.darf_beschliessen(request.user):
        raise PermissionDenied(
            "Protokolle genehmigt die Administration nach dem Konferenzbeschluss."
        )
    dokument = get_object_or_404(
        rechte.sichtbare_dokumente(request.user).select_for_update(of=("self",)),
        schluessel=schluessel,
        dokumenttyp__schluessel="protokoll",
    )
    if not rechte.darf_beschliessen(request.user, dokument):
        raise PermissionDenied("Für dieses Protokoll fehlt die Freigabeberechtigung.")
    eintraege = list(
        dokument.eintraege.select_for_update()
        .exclude(status=Status.ARCHIVIERT)
        .order_by("position", "kennung")
    )
    kopf = next((e for e in eintraege if e.eintragstyp == "protokollkopf"), None)
    vorgaben = {
        "datum": timezone.localdate(),
        "titel": f"Genehmigung des Protokolls: {dokument.titel}"[:250],
    }
    if kopf:
        vorgaben["gremium"] = Gremium.objects.filter(
            name__iexact=kopf.daten.get("gremium", "")
        ).first()
    formular = ProtokollBeschlussFormular(
        request.POST if request.method == "POST" else None, initial=vorgaben
    )
    hindernisse = []
    if not kopf:
        hindernisse.append("Bitte lege zuerst einen Protokollkopf mit Datum und Gremium an.")
    if not any(e.status != Status.BESCHLOSSEN for e in eintraege):
        hindernisse.append("Alle aktiven Einträge dieses Protokolls sind bereits beschlossen.")
    for e in eintraege:
        befund = dienste.pruefen(
            dokument,
            dienste.Rohsatz(
                kennung=e.kennung,
                eintragstyp=e.eintragstyp,
                titel=e.titel,
                daten=e.daten,
                status=Status.ABGESTIMMT,
            ),
        )
        for fehler in befund.fehler:
            hindernisse.append(f"{e.kennung} · {e.titel}: {fehler.text}")
        for feld in befund.fehlende_pflichtfelder:
            hindernisse.append(f"{e.kennung} · {e.titel}: Bitte „{feld.label}“ ausfüllen.")
        version = e.letzte_version()
        if version is None or version.titel != e.titel or version.daten != e.daten:
            hindernisse.append(
                f"{e.kennung}: Bitte den aktuellen Stand über die Bearbeitungsmaske speichern."
            )
    stand = _stand(dokument, eintraege)
    if request.method == "POST":
        gueltig = formular.is_valid()
        try:
            unveraendert = (
                signing.loads(
                    request.POST.get("stand", ""), salt="protokoll-beschluss", max_age=3600
                )
                == stand
            )
        except signing.BadSignature:
            unveraendert = False
        if not unveraendert:
            formular.add_error(
                None,
                "Das Protokoll wurde inzwischen geändert oder die Vorschau ist abgelaufen. "
                "Bitte prüfe die aktuelle Liste und bestätige erneut.",
            )
        if gueltig and unveraendert and not hindernisse:
            beschluss = formular.save(commit=False)
            beschluss.erstellt_von = request.user
            beschluss.protokoll_eintrag = kopf
            beschluss.save()
            for e in eintraege:
                if e.letzte_version().status == Status.BESCHLOSSEN:
                    e.status = Status.ABGESTIMMT
                    e.version_anlegen(autor=request.user)
            bericht = beschluesse.beschluss_fassen(beschluss, eintraege, nutzer=request.user)
            if bericht.beschlossen != len(eintraege):
                # Keine Teilfreigabe: alle Vorbedingungen wurden unter Sperre geprüft.
                raise RuntimeError("Das Protokoll konnte nicht vollständig freigegeben werden.")
            messages.success(
                request,
                f"Das gesamte Protokoll ist beschlossen: {bericht.beschlossen} Einträge "
                "sind jetzt gültig.",
            )
            return redirect("kern:beschluss", beschluss_id=beschluss.pk)
    return render(
        request,
        "kern/protokoll_beschliessen.html",
        {
            "dokument": dokument,
            "eintraege": eintraege,
            "formular": formular,
            "hindernisse": hindernisse,
            "stand": signing.dumps(stand, salt="protokoll-beschluss"),
        },
    )
