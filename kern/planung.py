"""Persönliche Planung: ausschließlich der Fortschritt des angemeldeten Kontos."""

from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from kern import rechte
from kern.models import Dokument, PersoenlicherFortschritt, Status


class Planwahl(forms.Form):
    dokument = forms.ModelChoiceField(
        label="Arbeitsplan",
        queryset=Dokument.objects.filter(dokumenttyp__schluessel="arbeitsplan_deutsch"),
        to_field_name="schluessel",
    )
    schuljahr = forms.RegexField(
        r"^\d{4}/\d{2}$",
        label="Schuljahr",
        max_length=7,
        help_text="Zum Beispiel 2026/27.",
    )
    klasse = forms.CharField(label="Klasse", max_length=10, help_text="Zum Beispiel 3b.")
    jahrgang = forms.TypedChoiceField(
        label="Jahrgang",
        required=False,
        coerce=int,
        choices=[("", "Aus dem Klassennamen übernehmen"), *[(j, str(j)) for j in range(1, 5)]],
    )

    def clean(self):
        daten = super().clean()
        if not daten.get("jahrgang"):
            klasse = daten.get("klasse", "")
            if klasse and klasse[0] in "1234":
                daten["jahrgang"] = int(klasse[0])
            else:
                self.add_error("jahrgang", "Bitte den Jahrgang auswählen.")
        return daten

    def clean_klasse(self):
        return self.cleaned_data["klasse"].lower()

    def clean_schuljahr(self):
        wert = self.cleaned_data["schuljahr"]
        if int(wert[-2:]) != (int(wert[:4]) + 1) % 100:
            raise forms.ValidationError("Bitte aufeinanderfolgende Jahre angeben, z. B. 2026/27.")
        return wert


class FortschrittFormular(forms.Form):
    eintrag = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    erledigt = forms.BooleanField(required=False, label="Erledigt")
    notiz = forms.CharField(
        required=False,
        max_length=10000,
        label="Meine Notiz",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


@login_required
@require_http_methods(["GET", "POST"])
def planung(request):
    if not rechte.darf_eigene_planung(request.user):
        raise PermissionDenied("Die persönliche Planung steht dem Kollegium zur Verfügung.")
    heute = timezone.localdate()
    jahr = heute.year if heute.month >= 8 else heute.year - 1
    vorgaben = {"schuljahr": f"{jahr}/{(jahr + 1) % 100:02d}"}
    erstes = Planwahl.base_fields["dokument"].queryset.first()
    if erstes:
        vorgaben["dokument"] = erstes.schluessel
    quelle = request.POST if request.method == "POST" else request.GET
    auswahl = Planwahl(quelle if quelle else None, initial=vorgaben)
    gruppen = []
    if auswahl.is_bound and auswahl.is_valid():
        daten = auswahl.cleaned_data
        dokument = daten["dokument"]
        jahrgang = daten["jahrgang"]
        eintraege = [
            e
            for e in dokument.eintraege.exclude(status=Status.ARCHIVIERT)
            if e.eintragstyp == "ritual"
            or (e.eintragstyp == "vorhaben" and e.daten.get("jahrgang") == jahrgang)
        ]
        formular = None
        if request.method == "POST":
            formular = FortschrittFormular(request.POST)
            if formular.is_valid():
                eintrag = get_object_or_404(dokument.eintraege, pk=formular.cleaned_data["eintrag"])
                if eintrag.pk not in {e.pk for e in eintraege}:
                    raise PermissionDenied("Dieser Eintrag gehört nicht zu diesem Fahrplan.")
                fortschritt, _ = PersoenlicherFortschritt.objects.get_or_create(
                    nutzer=request.user,
                    eintrag=eintrag,
                    schuljahr=daten["schuljahr"],
                    klasse=daten["klasse"],
                    defaults={"erstellt_von": request.user},
                )
                erledigt = formular.cleaned_data["erledigt"]
                fortschritt.erledigt_am = (
                    (fortschritt.erledigt_am or timezone.now()) if erledigt else None
                )
                fortschritt.erledigt = erledigt
                fortschritt.notiz = formular.cleaned_data["notiz"]
                fortschritt.save()
                messages.success(request, "Deine Planung wurde gespeichert.")
                return redirect(
                    request.path
                    + "?"
                    + urlencode(
                        {
                            "dokument": dokument.schluessel,
                            "schuljahr": daten["schuljahr"],
                            "klasse": daten["klasse"],
                            "jahrgang": jahrgang,
                        }
                    )
                )
            else:
                return HttpResponseBadRequest(
                    "Bitte einen gültigen Eintrag und eine Notiz "
                    "mit höchstens 10000 Zeichen angeben."
                )
        fortschritte = {
            f.eintrag_id: f
            for f in PersoenlicherFortschritt.objects.filter(
                nutzer=request.user,
                schuljahr=daten["schuljahr"],
                klasse=daten["klasse"],
                eintrag__dokument=dokument,
            )
        }
        from deutsch.eintragstypen import QUARTALE

        for schluessel, name in [("ritual", "Rituale"), *QUARTALE]:
            zeilen = []
            for e in eintraege:
                if (schluessel == "ritual" and e.eintragstyp == "ritual") or (
                    e.eintragstyp == "vorhaben" and e.daten.get("quartal") == schluessel
                ):
                    f = fortschritte.get(e.pk)
                    zeilen.append(
                        {
                            "eintrag": e,
                            "auspraegung": e.daten.get(f"auspraegung_jg{jahrgang}", ""),
                            "formular": formular
                            if formular and str(e.pk) == request.POST.get("eintrag")
                            else FortschrittFormular(
                                auto_id=f"id_{e.pk}_%s",
                                initial={
                                    "eintrag": e.pk,
                                    "erledigt": f.erledigt if f else False,
                                    "notiz": f.notiz if f else "",
                                },
                            ),
                        }
                    )
            gruppen.append({"name": name, "zeilen": zeilen})
    return render(request, "kern/planung.html", {"auswahl": auswahl, "gruppen": gruppen})
