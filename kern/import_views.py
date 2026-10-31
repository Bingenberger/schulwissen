"""JSON-Import mit Vorschau und erneut geprüfter, ausdrücklicher Übernahme."""

import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from eintragstypen.import_json import pruefen_json, uebernehmen_json
from kern import rechte
from kern.models import Dokument
from kern.schreibschutz import Schreibkonflikt, token_fuer_import, token_lesen


class ImportFormular(forms.Form):
    ausgangsstand = forms.CharField(required=False, widget=forms.HiddenInput)
    datei = forms.FileField(label="JSON-Datei", required=False)
    inhalt = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean(self):
        daten = super().clean()
        datei = daten.get("datei")
        if datei:
            if datei.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Die JSON-Datei darf höchstens 5 MB groß sein.")
            try:
                text = datei.read().decode("utf-8")
            except UnicodeError as fehler:
                raise forms.ValidationError("Bitte eine UTF-8-Datei verwenden.") from fehler
        else:
            text = daten.get("inhalt", "")
        if len(text.encode("utf-8")) > 5 * 1024 * 1024:
            raise forms.ValidationError("Der JSON-Inhalt darf höchstens 5 MB groß sein.")
        try:
            daten["json"] = json.loads(text)
        except ValueError as fehler:
            raise forms.ValidationError("Die Datei enthält kein gültiges JSON.") from fehler
        daten["inhalt"] = text
        return daten


@login_required
@transaction.atomic
def json_import(request, schluessel):
    if not rechte.darf_importieren(request.user):
        raise PermissionDenied("Importe führt die Administration durch.")
    dokument = get_object_or_404(Dokument.objects.select_for_update(), schluessel=schluessel)
    formular = ImportFormular(request.POST or None, request.FILES or None)
    bericht = None
    konflikt = None
    if request.method == "POST" and formular.is_valid():
        inhalt = formular.cleaned_data["json"]
        # Ein neuer Upload muss zunächst in die Vorschau.
        uebernehmen = request.POST.get("aktion") == "uebernehmen" and not request.FILES
        try:
            if uebernehmen:
                stand = token_lesen(
                    formular.cleaned_data.get("ausgangsstand"),
                    request.user,
                    dokument,
                    inhalt=inhalt,
                )
                bericht = uebernehmen_json(
                    inhalt, dokument, nutzer=request.user, erwarteter_stand=stand["stand"]
                )
            else:
                bericht = pruefen_json(inhalt, dokument)
        except Schreibkonflikt as fehler:
            konflikt = str(fehler)
            bericht = pruefen_json(inhalt, dokument)
        if uebernehmen and bericht.ok and not konflikt:
            messages.success(request, f"{bericht.geschrieben} Einträge importiert.")
            return redirect("kern:dokument", schluessel=schluessel)
        formular = ImportFormular(
            initial={
                "inhalt": formular.cleaned_data["inhalt"],
                "ausgangsstand": token_fuer_import(request.user, dokument, inhalt),
            }
        )
    return render(
        request,
        "kern/json_import.html",
        {
            "dokument": dokument,
            "formular": formular,
            "bericht": bericht,
            "konflikt": konflikt,
        },
        status=409 if konflikt else 200,
    )
