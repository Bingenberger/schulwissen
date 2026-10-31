"""Einträge auch in der Verwaltung über dieselbe fachliche Prüfung speichern."""

import json

from django import forms
from django.urls import reverse
from django.utils.html import format_html

from eintragstypen import dienste
from eintragstypen.registry import registry
from kern import rechte
from kern.models import Eintrag, Status
from kern.schreibschutz import Schreibkonflikt, pruefe_stand, token_fuer_eintrag, token_lesen


class EintragAdminFormular(forms.ModelForm):
    ausgangsstand = forms.CharField(required=False, widget=forms.HiddenInput)
    aktueller_stand = forms.CharField(required=False, widget=forms.HiddenInput)
    konflikt_geprueft = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput,
        label="Ich habe meine Eingabe mit dem aktuellen Stand verglichen.",
    )

    class Meta:
        model = Eintrag
        fields = [
            "dokument",
            "kennung",
            "eintragstyp",
            "titel",
            "status",
            "daten",
            "eltern",
            "position",
            "verantwortlich_gruppe",
            "verantwortlich_person",
            "verantwortlich_text",
            "fassung_stand",
        ]

    def __init__(self, *args, nutzer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.nutzer = nutzer
        self.befundsatz = None
        self.vorher = Eintrag.objects.filter(pk=self.instance.pk).first()
        self.erwarteter_stand = None
        if self.vorher and not self.is_bound:
            self.initial["ausgangsstand"] = token_fuer_eintrag(nutzer, self.vorher)
        if self.is_bound and self.data.get("aktueller_stand"):
            self.fields["konflikt_geprueft"].widget = forms.CheckboxInput()
        self.fields["status"].help_text = (
            "Freigaben erfolgen über die Beschlussvorlage. "
            "Das Bearbeiten eines beschlossenen Eintrags erzeugt einen Entwurf."
        )

    def clean(self):
        daten = super().clean()
        dokument = daten.get("dokument")
        if dokument is None and self.instance.dokument_id:
            dokument = self.instance.dokument
        typ = daten.get("eintragstyp", self.instance.eintragstyp)
        if not dokument or not registry.bekannt(typ):
            return daten
        if self.vorher:
            try:
                token = (
                    daten.get("aktueller_stand")
                    if daten.get("konflikt_geprueft")
                    else daten.get("ausgangsstand")
                )
                self.erwarteter_stand = token_lesen(token, self.nutzer, dokument, self.vorher)[
                    "stand"
                ]
                pruefe_stand(self.vorher, self.erwarteter_stand)
            except Schreibkonflikt as fehler:
                self.data = self.data.copy()
                self.data["aktueller_stand"] = token_fuer_eintrag(self.nutzer, self.vorher)
                self.data["konflikt_geprueft"] = ""
                self.fields["konflikt_geprueft"].widget = forms.CheckboxInput()
                self.add_error(
                    None,
                    format_html(
                        '{} Deine Eingabe bleibt im Formular. <a href="{}" target="_blank" '
                        'rel="noopener">Aktuelle Verwaltungsfassung zum Vergleichen öffnen</a>. '
                        "<details><summary>Aktuell gespeicherter Text</summary>"
                        '<p>{}</p><pre class="schreibkonflikt-json">{}</pre></details>'
                        "Übernimm die Änderungen, die erhalten bleiben sollen, "
                        "und bestätige den Vergleich vor dem Sichern.",
                        str(fehler),
                        reverse("admin:kern_eintrag_change", args=[self.vorher.pk]),
                        self.vorher.titel,
                        json.dumps(self.vorher.daten, ensure_ascii=False, indent=2),
                    ),
                )
                return daten
        inhalt = daten.get("daten")
        if inhalt is None:
            inhalt = {}
        if not isinstance(inhalt, dict):
            self.add_error("daten", "Die Daten müssen ein JSON-Objekt sein.")
            return daten
        status = daten.get("status")
        if not status:
            return daten
        vorher_status = self.vorher.status if self.vorher else Status.ENTWURF
        if status in rechte.OEFFENTLICHE_STATUS and status != vorher_status:
            self.add_error(
                "status", "Freigabe und Archivierung erfolgen ausschließlich über einen Beschluss."
            )
            return daten
        if status != vorher_status and not rechte.darf_status_setzen(
            self.nutzer, self.vorher or Eintrag(dokument=dokument, erstellt_von=self.nutzer), status
        ):
            self.add_error("status", "Für diesen Status fehlt die Berechtigung.")
            return daten
        if vorher_status in rechte.OEFFENTLICHE_STATUS:
            status = Status.ENTWURF
        roh = dienste.Rohsatz(
            kennung=daten.get("kennung", self.instance.kennung),
            eintragstyp=typ,
            titel=daten.get("titel", ""),
            status=status,
            daten=inhalt,
            verantwortlich_text=daten.get("verantwortlich_text", ""),
            fassung_stand=daten.get("fassung_stand"),
            quelle="Verwaltung",
        )
        self.befundsatz = dienste.pruefen(dokument, roh)
        for befund in self.befundsatz.fehler:
            self.add_error("daten", befund.text)
        if status == Status.ABGESTIMMT and self.befundsatz.fehlende_pflichtfelder:
            namen = ", ".join(f.label for f in self.befundsatz.fehlende_pflichtfelder)
            self.add_error("status", f"Zum Abstimmen fehlen Pflichtfelder: {namen}.")
        eltern = daten.get("eltern")
        gesehen = {self.instance.pk} if self.instance.pk else set()
        while eltern:
            if eltern.dokument_id != dokument.pk or eltern.pk in gesehen:
                self.add_error(
                    "eltern",
                    "Das Kapitel muss im selben Dokument liegen und darf keinen Kreis bilden.",
                )
                break
            gesehen.add(eltern.pk)
            eltern = eltern.eltern
        return daten
