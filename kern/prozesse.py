"""Veröffentlichte Abläufe finden und den konkret geprüften Arbeitsstand freigeben."""

import hashlib
import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from kern import beschluesse, prozessdaten, rechte
from kern.models import Anhang, Beschluss, Dokument, Eintrag, Gremium, Schulfunktion, Status
from kern.schreibschutz import Schreibkonflikt, schreibstand, token_fuer_eintrag, token_lesen
from kern.staende import lesemenge


def menge(nutzer, arbeitsstand=False):
    return lesemenge(
        nutzer,
        Eintrag.objects.filter(eintragstyp="prozess").exclude(status=Status.ARCHIVIERT),
        nur_beschlossene=not arbeitsstand,
    ).select_related("dokument")


def suchen(menge, begriff):
    """Aktuelle Funktionsnamen ohne neue Prozessversion berücksichtigen."""
    if not begriff:
        return menge
    treffer = (
        Q(lese_titel__icontains=begriff)
        | Q(kennung__icontains=begriff)
        | Q(lese_suchtext__icontains=begriff)
        | Q(lese_suchvektor=SearchQuery(begriff, config="german", search_type="websearch"))
    )
    for key in Schulfunktion.objects.filter(name__icontains=begriff).values_list(
        "schluessel", flat=True
    ):
        treffer |= Q(lese_daten__ablauf__knoten__contains=[{"funktion": key}])
    return menge.filter(treffer)


def leselink(e, arbeitsstand=False):
    if arbeitsstand:
        return reverse("kern:eintrag", args=[e.dokument.schluessel, e.kennung])
    version = e.beschlossene_version()
    return reverse("kern:version", args=[e.dokument.schluessel, e.kennung, version.versionsnummer])


@login_required
def verzeichnis(request):
    arbeit = request.GET.get("stand") == "arbeit"
    if arbeit and not rechte.darf_arbeitsstand_lesen(request.user):
        raise PermissionDenied("Arbeitsstände sind dem Kollegium vorbehalten.")
    begriff = (request.GET.get("q") or "").strip()[:200]
    treffer = suchen(menge(request.user, arbeit), begriff).order_by("lese_titel", "pk")
    seite = Paginator(treffer, 12).get_page(request.GET.get("seite"))
    karten = [
        {
            "titel": e.lese_titel,
            "anlass": e.lese_daten.get("anlass", ""),
            "dokument": e.dokument.titel,
            "kennung": e.kennung,
            "status": e.lese_status,
            "status_text": Status(e.lese_status).label,
            "url": leselink(e, arbeit),
        }
        for e in seite
    ]
    dokumente = (
        rechte.sichtbare_dokumente(request.user)
        .filter(dokumenttyp__eintragstypen__contains=["prozess"])
        .order_by("titel")
        if rechte.darf_anlegen(request.user)
        else []
    )
    return render(
        request,
        "kern/prozesse.html",
        {
            "karten": karten,
            "seite": seite,
            "begriff": begriff,
            "arbeit": arbeit,
            "prozess_dokumente": dokumente,
        },
    )


def materialstand(e):
    try:
        graph = prozessdaten.normalisieren(e.daten.get("ablauf"))
    except ValidationError:
        return ""
    ids = {v["id"] for k in graph["knoten"] for v in k["verweise"] if v["typ"] == "anhang"}
    daten = list(
        Anhang.objects.filter(pk__in=ids)
        .order_by("pk")
        .values(
            "pk",
            "geaendert_am",
            "datei",
            "nextcloud_link",
            "nextcloud_pfad",
            "dokument_id",
            "eintrag_id",
        )
    )
    return hashlib.sha256(
        json.dumps(daten, cls=DjangoJSONEncoder, sort_keys=True).encode()
    ).hexdigest()


def freigabetoken(nutzer, e):
    return signing.dumps(
        {"eintrag": token_fuer_eintrag(nutzer, e), "material": materialstand(e)},
        salt="prozessfreigabe-v1",
    )


def freigabe_stand_pruefen(token, nutzer, e):
    try:
        daten = signing.loads(token, salt="prozessfreigabe-v1")
        stand = token_lesen(daten["eintrag"], nutzer, e.dokument, eintrag=e)
        if stand["stand"] != schreibstand(e) or daten["material"] != materialstand(e):
            raise Schreibkonflikt(
                "Der Arbeitsstand oder ein Material wurde inzwischen geändert. "
                "Bitte prüfe die aktuelle Fassung erneut."
            )
    except (signing.BadSignature, KeyError, TypeError) as fehler:
        raise Schreibkonflikt(
            "Der Freigabestand fehlt oder ist ungültig. Bitte öffne die Freigabe neu."
        ) from fehler


class FreigabeFormular(forms.Form):
    stand = forms.CharField(widget=forms.HiddenInput)
    datum = forms.DateField(
        label="Datum der Freigabe",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    gremium = forms.ModelChoiceField(
        label="Verantwortliches Gremium / Freigabestelle",
        queryset=Gremium.objects.all(),
        help_text=(
            "Wähle die fachlich zuständige Stelle, "
            "beispielsweise Schulleitung oder Lehrerkonferenz."
        ),
    )
    text = forms.CharField(
        label="Freigabenachweis",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=(
            "Was wurde von wem fachlich geprüft und freigegeben? "
            "Bei Konferenzbeschlüssen den Wortlaut dokumentieren."
        ),
    )
    geprueft = forms.BooleanField(
        label=(
            "Ich bestätige, dass diese Prozessfassung fachlich geprüft ist "
            "und veröffentlicht werden darf."
        )
    )
    material_geprueft = forms.BooleanField(
        label=(
            "Die verlinkten Materialien und deren Fassung wurden geprüft. "
            "Veränderliche externe Links bleiben als solche gekennzeichnet."
        ),
        required=False,
    )

    def clean_datum(self):
        datum = self.cleaned_data["datum"]
        if datum > timezone.localdate():
            raise forms.ValidationError(
                "Eine Veröffentlichung benötigt eine bereits erfolgte Freigabe."
            )
        return datum

    def __init__(self, *args, materialien=False, **kwargs):
        super().__init__(*args, **kwargs)
        if materialien:
            self.fields["material_geprueft"].required = True
        else:
            del self.fields["material_geprueft"]


@login_required
@require_http_methods(["GET", "POST"])
def freigeben(request, schluessel, kennung):
    dokument = get_object_or_404(rechte.sichtbare_dokumente(request.user), schluessel=schluessel)
    if not rechte.darf_beschliessen(request.user, dokument):
        raise PermissionDenied("Für diesen Ablauf fehlt die Freigabeberechtigung.")
    e = get_object_or_404(Eintrag, dokument=dokument, kennung=kennung, eintragstyp="prozess")
    try:
        graph = prozessdaten.normalisieren(e.daten.get("ablauf"))
        materialien = any(k["verweise"] for k in graph["knoten"])
    except ValidationError:
        materialien = False
    formular = FreigabeFormular(
        request.POST if request.method == "POST" else None,
        materialien=materialien,
        initial={"stand": freigabetoken(request.user, e)},
    )
    status = 200
    if request.method == "POST" and formular.is_valid():
        try:
            with transaction.atomic():
                Dokument.objects.select_for_update().get(pk=dokument.pk)
                e = Eintrag.objects.select_for_update().get(pk=e.pk)
                if not rechte.darf_beschliessen(request.user, e.dokument):
                    raise PermissionDenied
                freigabe_stand_pruefen(formular.cleaned_data["stand"], request.user, e)
                if e.status in (Status.ARCHIVIERT, Status.BESCHLOSSEN) or not e.letzte_version():
                    raise ValidationError("Es gibt keinen neuen Arbeitsstand zur Freigabe.")
                prozessdaten.freigabe_pruefen(e.daten, nutzer=request.user)
                text = formular.cleaned_data["text"]
                if materialien:
                    text += (
                        "\n\nMaterialien und deren Fassung wurden bei der Freigabe geprüft. "
                        "Externe Links bleiben veränderlich."
                    )
                beschluss = Beschluss.objects.create(
                    datum=formular.cleaned_data["datum"],
                    gremium=formular.cleaned_data["gremium"],
                    titel=f"Prozessfreigabe: {e.titel}"[:250],
                    text=text,
                    erstellt_von=request.user,
                )
                beschluesse.beschluss_fassen(beschluss, [e], nutzer=request.user)
                nummer = e.letzte_version().versionsnummer
        except Schreibkonflikt as fehler:
            status = 409
            formular.add_error(None, str(fehler))
        except ValidationError as fehler:
            formular.add_error(None, " ".join(fehler.messages))
        else:
            messages.success(
                request,
                "Der Ablauf ist veröffentlicht. Neue Bearbeitungen ändern die gültige Fassung "
                "erst nach erneuter Freigabe.",
            )
            return redirect("kern:version", schluessel=schluessel, kennung=kennung, nummer=nummer)
    return render(
        request,
        "kern/prozess_freigeben.html",
        {"eintrag": e, "dokument": dokument, "formular": formular, "materialien": materialien},
        status=status,
    )
