"""JSON-Import mit Vorschau und erneut geprüfter, ausdrücklicher Übernahme."""

import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from eintragstypen.import_json import pruefen_json, uebernehmen_json
from kern import rechte
from kern.models import Dokument


class ImportFormular(forms.Form):
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
def json_import(request, schluessel):
    if not rechte.darf_importieren(request.user):
        raise PermissionDenied("Importe führt die Administration durch.")
    dokument = get_object_or_404(Dokument, schluessel=schluessel)
    formular = ImportFormular(request.POST or None, request.FILES or None)
    bericht = None
    if request.method == "POST" and formular.is_valid():
        inhalt = formular.cleaned_data["json"]
        # Ein neuer Upload muss zunächst in die Vorschau.
        uebernehmen = request.POST.get("aktion") == "uebernehmen" and not request.FILES
        bericht = (uebernehmen_json if uebernehmen else pruefen_json)(
            inhalt, dokument, **({"nutzer": request.user} if uebernehmen else {})
        )
        if uebernehmen and bericht.ok:
            messages.success(request, f"{bericht.geschrieben} Einträge importiert.")
            return redirect("kern:dokument", schluessel=schluessel)
        formular = ImportFormular(initial={"inhalt": formular.cleaned_data["inhalt"]})
    return render(
        request,
        "kern/json_import.html",
        {
            "dokument": dokument,
            "formular": formular,
            "bericht": bericht,
        },
    )
