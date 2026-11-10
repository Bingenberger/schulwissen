"""Formulare aus den Feldschemata der Registry bauen.

Es gibt kein handgeschriebenes Formular je Eintragstyp: die Maske entsteht aus
derselben Feldliste, die auch Prüfung und Import steuern. Ein neues Feld in
``deutsch/eintragstypen.py`` erscheint damit automatisch in der Maske – mit
Hilfetext, im richtigen Block und mit Pflichtmarkierung.
"""

from __future__ import annotations

from django import forms
from django.core import signing

from eintragstypen import html
from eintragstypen.dienste import Rohsatz
from eintragstypen.registry import Feldtyp, registry
from kern.models import Status

#: Prefix der Datenfelder im Formular.
DATEN = "f_"
#: Prefix der Verweisfelder (Kompetenzen, Bezüge).
VERWEIS = "v_"


class MehrdateiWidget(forms.ClearableFileInput):
    allow_multiple_selected = True


class MehrdateiFeld(forms.FileField):
    widget = MehrdateiWidget

    def clean(self, data, initial=None):
        if not data:
            return []
        dateien = data if isinstance(data, (list, tuple)) else [data]
        bereinigen = super().clean
        return [bereinigen(datei, initial) for datei in dateien]


class RichtextFeld(forms.CharField):
    """Formatierter Text. Der Editor im Browser hängt sich an das Textfeld."""

    widget = forms.Textarea

    def __init__(self, *args, zeilen: int = 8, **kwargs):
        kwargs.setdefault(
            "widget",
            forms.Textarea(attrs={"rows": zeilen, "data-editor": "richtext"}),
        )
        super().__init__(*args, **kwargs)

    def clean(self, wert):
        wert = super().clean(wert)
        if not wert:
            return ""
        gesaeubert = html.saeubern(wert)
        return "" if html.ist_leer(gesaeubert) else gesaeubert


class VerweisFeld(forms.CharField):
    """Versteckte Liste von Ziel-Kennungen, gefüllt durch das Auswahl-Widget."""

    widget = forms.HiddenInput

    def clean(self, wert) -> list[str]:
        wert = super().clean(wert) or ""
        gesehen: list[str] = []
        for teil in wert.replace("\n", ",").replace(";", ",").split(","):
            kennung = teil.strip()
            if kennung and kennung not in gesehen:
                gesehen.append(kennung)
        return gesehen


def _formularfeld(feld):
    """Baut aus einem ``Feld`` der Registry ein Django-Formularfeld."""
    gemeinsam = {
        "label": feld.label,
        "help_text": feld.hilfe,
        # Pflichtfelder sind markiert, blockieren aber das Speichern nicht:
        # als Entwurf sichern muss immer gehen (SPEC.md §7.4).
        "required": False,
    }

    if feld.typ == Feldtyp.PROZESSGRAPH:
        from kern.prozesseditor import ProzessFeld

        return ProzessFeld(**gemeinsam)
    if feld.typ == Feldtyp.DATUM:
        return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **gemeinsam)

    if feld.typ == Feldtyp.RICHTEXT:
        return RichtextFeld(zeilen=max(feld.zeilen, 6), **gemeinsam)

    if feld.typ == Feldtyp.LANGTEXT:
        return forms.CharField(widget=forms.Textarea(attrs={"rows": feld.zeilen}), **gemeinsam)

    if feld.typ == Feldtyp.ZAHL:
        attrs = {"inputmode": "numeric"}
        if feld.min_wert is not None:
            attrs["min"] = feld.min_wert
        if feld.max_wert is not None:
            attrs["max"] = feld.max_wert
        klasse = forms.IntegerField if feld.ganzzahl else forms.FloatField
        return klasse(
            min_value=feld.min_wert,
            max_value=feld.max_wert,
            widget=forms.NumberInput(attrs=attrs),
            **gemeinsam,
        )

    if feld.typ == Feldtyp.AUSWAHL:
        return forms.ChoiceField(choices=[("", "– bitte wählen –"), *feld.auswahl], **gemeinsam)

    if feld.typ == Feldtyp.JANEIN:
        return forms.ChoiceField(
            choices=[("", "– bitte wählen –"), ("ja", "ja"), ("nein", "nein")], **gemeinsam
        )

    return forms.CharField(**gemeinsam)


class EintragFormular(forms.Form):
    """Maske eines Eintrags – Felder und Blöcke kommen aus der Registry."""

    ausgangsstand = forms.CharField(required=False, widget=forms.HiddenInput)
    anhang_dateien = MehrdateiFeld(label="Dateien vom Gerät", required=False)
    anhang_link = forms.URLField(
        label="Nextcloud-Link", required=False, max_length=500, assume_scheme="https"
    )
    anhang_nextcloud = forms.Field(required=False, widget=forms.MultipleHiddenInput)

    titel = forms.CharField(
        label="Titel",
        max_length=300,
        help_text="Prägnanter Titel, gern mit Untertitel.",
        widget=forms.TextInput(attrs={"autofocus": "autofocus"}),
    )

    def __init__(self, *args, eintragstyp: str, eintrag=None, nutzer=None, dokument=None, **kwargs):
        self.typ = registry.holen(eintragstyp)
        self.eintrag = eintrag
        self.nutzer = nutzer
        self.dokument = dokument or (eintrag.dokument if eintrag else None)
        super().__init__(*args, **kwargs)

        for feld in self.typ.felder:
            if feld.ist_verlinkung:
                self.fields[VERWEIS + feld.schluessel] = VerweisFeld(
                    label=feld.label, help_text=feld.hilfe, required=False
                )
            elif not feld.ist_berechnet:
                self.fields[DATEN + feld.schluessel] = _formularfeld(feld)

        if "f_ablauf" in self.fields:
            from kern.prozesseditor import LEER

            feld = self.fields["f_ablauf"]
            feld.initial = LEER
            feld.widget.nutzer = nutzer
            feld.widget.dokument = dokument or (eintrag.dokument if eintrag else None)
            feld.widget.eintrag = eintrag

        self.fields["status"] = forms.ChoiceField(
            label="Status",
            choices=[(s.value, s.label) for s in Status if s != Status.ARCHIVIERT],
            help_text="„beschlossen“ wird nur über einen Beschluss gesetzt.",
            required=False,
        )

        if eintrag is not None:
            self._vorbelegen(eintrag)
        else:
            # Ein neuer Eintrag ist ein Entwurf. Ohne diese Vorgabe stünde
            # „Idee" im Auswahlfeld, nur weil das der erste Wert der Liste ist.
            self.fields["status"].initial = Status.ENTWURF

    def _nextcloud_lesen(self, token):
        try:
            daten = signing.loads(token, salt="anhang-erfassung")
        except signing.BadSignature as fehler:
            raise forms.ValidationError("Bitte wähle die Nextcloud-Datei erneut aus.") from fehler
        if daten["nutzer"] != self.nutzer.pk or daten["dokument"] != self.dokument.pk:
            raise forms.ValidationError("Die Nextcloud-Auswahl gehört zu einem anderen Dokument.")
        return daten

    def clean_anhang_nextcloud(self):
        tokens = self.cleaned_data["anhang_nextcloud"] or []
        return [self._nextcloud_lesen(token) for token in dict.fromkeys(tokens)]

    def nextcloud_auswahl(self):
        for token in self["anhang_nextcloud"].value() or []:
            try:
                yield {"token": token, **self._nextcloud_lesen(token)}
            except forms.ValidationError:
                continue

    def _vorbelegen(self, eintrag) -> None:
        self.fields["titel"].initial = eintrag.titel
        self.fields["status"].initial = eintrag.status
        for feld in self.typ.datenfelder:
            if feld.ist_berechnet:
                continue
            wert = eintrag.daten.get(feld.schluessel)
            if feld.typ == Feldtyp.JANEIN and isinstance(wert, bool):
                wert = "ja" if wert else "nein"
            self.fields[DATEN + feld.schluessel].initial = (
                {"schema_version": 1, "knoten": [], "verbindungen": []}
                if feld.typ == Feldtyp.PROZESSGRAPH and wert is None
                else wert
            )
        for feld in self.typ.verlinkungsfelder:
            ziele = eintrag.verlinkungen.filter(art=feld.verlinkungsart, feld=feld.schluessel)
            kennungen = [
                z.beschriftung.split(" ", 1)[0] if feld.zieltyp == "eintrag" else z.ziel_id
                for z in ziele
            ]
            self.fields[VERWEIS + feld.schluessel].initial = ", ".join(kennungen)

    # --- Zugriff für die Vorlage -----------------------------------------

    def bloecke(self):
        """Die Blöcke der Maske mit ihren Formularfeldern."""
        daten = self._daten_aus_eingabe()
        # alle=True: bedingte Felder stehen im Formular, auch wenn ihre
        # Bedingung noch nicht erfüllt ist. Ein- und ausgeblendet werden sie
        # im Browser; geprüft wird weiter serverseitig über „gilt_fuer“.
        for block, felder in self.typ.bloecke_mit_feldern(daten, alle=True):
            eintraege = []
            for feld in felder:
                if feld.ist_berechnet:
                    eintraege.append({"feld": feld, "berechnet": feld.berechnet(daten)})
                    continue
                name = (VERWEIS if feld.ist_verlinkung else DATEN) + feld.schluessel
                if name in self.fields:
                    zeile = {"feld": feld, "gebunden": self[name]}
                    if feld.ist_verlinkung and feld.zieltyp == "kompetenz":
                        from fachdaten.models import Kompetenzerwartung

                        kennungen = VerweisFeld(required=False).clean(self[name].value() or "")
                        klartexte = Kompetenzerwartung.objects.in_bulk(kennungen)
                        zeile["marken"] = [
                            {"kennung": k, "text": klartexte[k].text if k in klartexte else ""}
                            for k in kennungen
                        ]
                    eintraege.append(zeile)
            if eintraege:
                yield {"name": block, "felder": eintraege}

    def _daten_aus_eingabe(self) -> dict:
        """Grobe Rohwerte – nur für Sichtbarkeit und berechnete Anzeige."""
        if self.is_bound:
            quelle = self.data
            return {
                feld.schluessel: quelle.get(DATEN + feld.schluessel)
                for feld in self.typ.datenfelder
                if quelle.get(DATEN + feld.schluessel) not in (None, "")
            }
        if self.eintrag is not None:
            return dict(self.eintrag.daten)
        return {}

    # --- Ergebnis ---------------------------------------------------------

    def als_rohsatz(self, kennung: str) -> Rohsatz:
        """Das Formularergebnis als Rohsatz für ``dienste.pruefen``."""
        daten = {}
        for feld in self.typ.datenfelder:
            if feld.ist_berechnet:
                continue
            wert = self.cleaned_data.get(DATEN + feld.schluessel)
            if wert in (None, "", []):
                continue
            daten[feld.schluessel] = wert

        verweise = {
            feld.schluessel: self.cleaned_data.get(VERWEIS + feld.schluessel) or []
            for feld in self.typ.verlinkungsfelder
        }

        return Rohsatz(
            kennung=kennung,
            eintragstyp=self.typ.schluessel,
            titel=self.cleaned_data["titel"],
            status=self.cleaned_data.get("status") or Status.ENTWURF,
            daten=daten,
            verweise=verweise,
            quelle="Eingabemaske",
        )


class KommentarFormular(forms.Form):
    text = forms.CharField(
        label="Kommentar",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Frage oder Hinweis …"}),
    )
    feld = forms.CharField(required=False, widget=forms.HiddenInput)


class AnhangFormular(forms.Form):
    datei = forms.FileField(label="Datei", required=False)
    nextcloud_link = forms.URLField(
        label="Nextcloud-Link",
        required=False,
        assume_scheme="https",
        help_text="Alternativ: Freigabe-Link aus der Nextcloud einfügen.",
    )
    beschreibung = forms.CharField(label="Beschreibung", max_length=300, required=False)

    def clean(self):
        daten = super().clean()
        if not daten.get("datei") and not daten.get("nextcloud_link"):
            raise forms.ValidationError(
                "Bitte eine Datei auswählen oder einen Nextcloud-Link einfügen."
            )
        return daten
