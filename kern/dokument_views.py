"""Dokumente über die gemeinsame Oberfläche anlegen."""

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render

from deutsch import gliederung
from kern import rechte
from kern.dokumenttypen import typen_sichern
from kern.models import Dokument, Dokumenttyp


class DokumentFormular(forms.ModelForm):
    class Meta:
        model = Dokument
        fields = ["titel", "schluessel", "dokumenttyp", "beschreibung", "gueltig_ab_schuljahr"]
        help_texts = {"schluessel": "Dauerhafter Kurzname, z. B. medienkonzept."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dokumenttyp"].queryset = Dokumenttyp.objects.filter(
            schluessel__in=["arbeitsplan_deutsch", "konzept", "protokoll"]
        )


@login_required
def dokument_neu(request):
    if not rechte.darf_dokument_anlegen(request.user):
        raise PermissionDenied("Dokumente legt die Administration an.")
    typen_sichern()
    gliederung.dokumenttyp_sichern()
    formular = DokumentFormular(request.POST or None)
    if request.method == "POST" and formular.is_valid():
        with transaction.atomic():
            dokument = formular.save(commit=False)
            dokument.erstellt_von = request.user
            if dokument.dokumenttyp.schluessel == "arbeitsplan_deutsch":
                dokument.fach = "deutsch"
                dokument.einstellungen = {
                    "deutschstunden_pro_woche": {"1": 6, "2": 6, "3": 5, "4": 5}
                }
            dokument.save()
            if dokument.dokumenttyp.schluessel == "arbeitsplan_deutsch":
                gliederung.dokument_anlegen(schluessel=dokument.schluessel, nutzer=request.user)
            elif dokument.dokumenttyp.schluessel == "protokoll":
                from eintragstypen.dienste import Rohsatz, pruefen, speichern

                speichern(
                    dokument,
                    pruefen(
                        dokument,
                        Rohsatz(
                            kennung="P-01",
                            eintragstyp="protokollkopf",
                            titel="Konferenz",
                        ),
                    ),
                    nutzer=request.user,
                )
        return redirect("kern:dokument", schluessel=dokument.schluessel)
    return render(request, "kern/dokument_neu.html", {"formular": formular})
