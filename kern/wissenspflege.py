"""Versionierte Gültigkeitsangaben, laufende Funktionsbesetzung und Pflegeübersicht."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import BigIntegerField, Case, F, OuterRef, Q, Subquery, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from eintragstypen import dienste
from kern import funktionen, rechte
from kern.models import PFLEGE_FELDER, Anhang, Eintrag, Kommentar, Schulfunktion, Status
from kern.schreibschutz import Schreibkonflikt, token_fuer_eintrag, token_lesen
from kern.staende import Eintragsstand, gueltige_versionen, mit_lesefassungen


class PflegeFormular(forms.ModelForm):
    stand = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = Eintrag
        fields = list(PFLEGE_FELDER)
        widgets = {
            f: forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
            for f in ["wirksam_ab", "wirksam_bis", "geprueft_am", "pruefen_am"]
        }
        widgets["kurzantwort"] = forms.Textarea(attrs={"rows": 3})
        help_texts = {
            "aufgabe": "Ordne den Inhalt einem Einstieg im Schulhandbuch zu.",
            "kurzantwort": "Was muss ich wissen? Bei Formularen: Wofür ist die Vorlage?",
            "suchbegriffe": (
                "Gebräuchliche Wörter und alternative Bezeichnungen, "
                "zum Beispiel IT-Störung, Computer, Support."
            ),
            "pruefen_am": "Ein fälliger Prüftermin setzt einen Inhalt nicht außer Kraft.",
            "quelle": (
                "Maßgebliche Quellen und überprüfbare Versionsnachweise; keine "
                "personenbezogenen Fallakten."
            ),
            "ersetzt_durch": (
                "Ein Verweis allein beendet keine Gültigkeit. Setze bei Ablösung "
                "auch das Ende der Wirksamkeit."
            ),
        }

    def __init__(self, *args, nutzer, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["pflege_funktion", "pflege_vertretung"]:
            self.fields[name].queryset = Schulfunktion.objects.filter(archiviert=False)
        self.fields["ersetzt_durch"].queryset = rechte.sichtbare_eintraege(
            nutzer, Eintrag.objects.exclude(pk=self.instance.pk)
        ).select_related("dokument")


@login_required
@require_http_methods(["GET", "POST"])
def bearbeiten(request, schluessel, kennung):
    from kern.views import _eintrag_holen

    e = _eintrag_holen(request, schluessel, kennung)
    if not rechte.darf_bearbeiten(request.user, e):
        raise PermissionDenied
    formular = PflegeFormular(
        request.POST if request.method == "POST" else None,
        instance=e,
        nutzer=request.user,
        initial={"stand": token_fuer_eintrag(request.user, e)},
    )
    status = 200
    if request.method == "POST" and formular.is_valid():
        try:
            token = token_lesen(formular.cleaned_data["stand"], request.user, e.dokument, eintrag=e)
            roh = dienste.Rohsatz(
                kennung=e.kennung,
                eintragstyp=e.eintragstyp,
                titel=e.titel,
                status=Status.ENTWURF
                if e.status in (Status.BESCHLOSSEN, Status.ARCHIVIERT)
                else e.status,
                daten=e.daten,
            )
            befund = dienste.pruefen(e.dokument, roh, nutzer=request.user)
            if not befund.ok:
                raise ValidationError([b.text for b in befund.fehler])
            dienste.speichern(
                e.dokument,
                befund,
                nutzer=request.user,
                metadaten={name: formular.cleaned_data[name] for name in PFLEGE_FELDER},
                erwarteter_stand=token["stand"],
            )
        except Schreibkonflikt as fehler:
            formular.add_error(None, str(fehler))
            status = 409
        except ValidationError as fehler:
            formular.add_error(None, " ".join(fehler.messages))
        else:
            messages.success(
                request,
                (
                    "Wissensangaben als neue Arbeitsfassung gespeichert. Die gültige "
                    "Freigabe bleibt erhalten."
                ),
            )
            return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)
    return render(
        request,
        "kern/wissenspflege_formular.html",
        {"eintrag": e, "dokument": e.dokument, "formular": formular},
        status=status,
    )


def kontakt(funktion):
    if not funktion:
        return None
    a = funktionen.aufloesen(funktion)
    return {
        "name": funktion.name,
        "status": a.status_text,
        "personen": [
            b.person.anzeigename or b.person.kuerzel or "Kontoname ergänzen" for b in a.zustaendige
        ],
    }


def kontext(nutzer, stand):
    quelle = stand.version if hasattr(stand, "version") and stand.version else stand
    heute = timezone.localdate()
    zeitraum = "Ohne festgelegten Wirksamkeitszeitraum"
    if quelle.wirksam_ab or quelle.wirksam_bis:
        zeitraum = (
            f"Wirksam ab {quelle.wirksam_ab:%d.%m.%Y}"
            if quelle.wirksam_ab
            else "Wirksam ohne festgelegten Beginn"
        ) + (f" bis einschließlich {quelle.wirksam_bis:%d.%m.%Y}" if quelle.wirksam_bis else "")
    status = ""
    if quelle.wirksam_ab and quelle.wirksam_ab > heute:
        status = "Künftig wirksam – diese Fassung gilt heute noch nicht."
    if quelle.wirksam_bis and quelle.wirksam_bis < heute:
        status = "Wirksamkeitszeitraum beendet – diese Fassung gilt nicht mehr."
    ersetzt = None
    if quelle.ersetzt_durch_id:
        e = (
            rechte.sichtbare_eintraege(nutzer, Eintrag.objects.select_related("dokument"))
            .filter(pk=quelle.ersetzt_durch_id)
            .first()
        )
        if e:
            v = e.beschlossene_version()
            if v:
                ersetzt = {
                    "titel": v.titel,
                    "url": reverse(
                        "kern:version", args=[e.dokument.schluessel, e.kennung, v.versionsnummer]
                    ),
                }
    if hasattr(quelle, "dateifassungen") and not status and quelle.status == Status.BESCHLOSSEN:
        aktuell = quelle.eintrag.beschlossene_version()
        if aktuell and aktuell.pk != quelle.pk:
            status = "Diese Fassung ist durch eine neuere wirksame Freigabe abgelöst."
    kopien = []
    if hasattr(quelle, "dateifassungen"):
        from kern.dateifassungen import karte

        kopien = [
            karte(k, nutzer)
            for k in quelle.dateifassungen.select_related(
                "original__dokument", "original__eintrag__dokument"
            )
        ]
    return {
        "quelle": quelle,
        "zeitraum": zeitraum,
        "status": status,
        "pflege": kontakt(quelle.pflege_funktion),
        "vertretung": kontakt(quelle.pflege_vertretung),
        "ueberfaellig": bool(quelle.pruefen_am and quelle.pruefen_am < heute),
        "ersetzt": ersetzt,
        "kopien": kopien,
    }


@login_required
def uebersicht(request):
    if not rechte.ist_lehrkraft(request.user):
        raise PermissionDenied
    begriff = (request.GET.get("q") or "").strip()[:200]
    art = request.GET.get("ansicht", "faellig")
    menge = rechte.sichtbare_eintraege(
        request.user, Eintrag.objects.exclude(status=Status.ARCHIVIERT)
    ).select_related("dokument", "pflege_funktion", "pflege_vertretung")
    aktuell = gueltige_versionen().filter(eintrag_id=OuterRef("pk"))
    menge = mit_lesefassungen(menge).annotate(_pflegeversion=Subquery(aktuell.values("pk")[:1]))
    menge = menge.annotate(
        **{
            "pflege_" + name: Case(
                When(_pflegeversion__isnull=False, then=Subquery(aktuell.values(name)[:1])),
                default=F(name),
                output_field=BigIntegerField()
                if name.endswith("_id")
                else Eintrag._meta.get_field(name),
            )
            for name in ("pruefen_am", "titel", "pflege_funktion_id", "pflege_vertretung_id")
        }
    )
    if art == "fehler":
        menge = menge.filter(
            pk__in=Kommentar.objects.filter(fehlerhinweis=True, erledigt=False).values("eintrag_id")
        )
    elif art == "alle":
        pass
    else:
        art = "faellig"
        menge = menge.filter(pflege_pruefen_am__lt=timezone.localdate())
    if begriff:
        menge = menge.filter(
            Q(pflege_titel__icontains=begriff)
            | Q(dokument__titel__icontains=begriff)
            | Q(
                pflege_pflege_funktion_id__in=Schulfunktion.objects.filter(
                    name__icontains=begriff
                ).values("pk")
            )
            | Q(
                pflege_pflege_vertretung_id__in=Schulfunktion.objects.filter(
                    name__icontains=begriff
                ).values("pk")
            )
        )
    seite = Paginator(menge.order_by("pflege_pruefen_am", "pflege_titel", "pk"), 12).get_page(
        request.GET.get("seite")
    )
    karten = [
        {
            "eintrag": Eintragsstand(e, e.beschlossene_version()),
            "pflege": kontakt((e.beschlossene_version() or e).pflege_funktion),
            "vertretung": kontakt((e.beschlossene_version() or e).pflege_vertretung),
            "fehler": e.kommentare.filter(fehlerhinweis=True, erledigt=False).count(),
        }
        for e in seite
    ]
    return render(
        request,
        "kern/wissenspflege.html",
        {"karten": karten, "seite": seite, "begriff": begriff, "ansicht": art},
    )


class AnlagenFormular(forms.ModelForm):
    stand = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = Anhang
        fields = ["verwendung", "dateiversion", "datei"]
        labels = {"datei": "Geprüfte Dateikopie hochladen"}
        help_texts = {
            "dateiversion": "Externe Quelle: Bitte die nachprüfbare Dateifassung benennen.",
            "datei": (
                "Eine verbindliche externe Anlage benötigt eine geprüfte lokale "
                "Kopie. Frühere Freigabekopien bleiben unverändert."
            ),
        }

    def clean(self):
        daten = super().clean()
        if daten.get("verwendung") == "verbindlich":
            if not daten.get("datei"):
                self.add_error(
                    "datei", "Für eine verbindliche Dateifassung fehlt die geprüfte Kopie."
                )
            if (self.instance.nextcloud_link or self.instance.nextcloud_pfad) and not daten.get(
                "dateiversion"
            ):
                self.add_error("dateiversion", "Bitte den überprüfbaren Versionsnachweis ergänzen.")
        return daten


@login_required
@require_http_methods(["GET", "POST"])
def anlage(request, schluessel, kennung, pk):
    from django.core import signing
    from django.db import transaction

    from kern import dateifassungen
    from kern.models import Dokument
    from kern.views import _eintrag_holen

    e = _eintrag_holen(request, schluessel, kennung)
    if not rechte.darf_bearbeiten(request.user, e):
        raise PermissionDenied
    a = get_object_or_404(Anhang, pk=pk, eintrag=e)
    token = signing.dumps(
        {"a": a.pk, "user": request.user.pk, "stand": dateifassungen.originalstand(a)},
        salt="anlagestand",
    )
    formular = AnlagenFormular(
        request.POST if request.method == "POST" else None,
        request.FILES or None,
        instance=a,
        initial={"stand": token},
    )
    status = 200
    if request.method == "POST" and formular.is_valid():
        try:
            with transaction.atomic():
                Dokument.objects.select_for_update().get(pk=e.dokument_id)
                aktuell = Anhang.objects.select_for_update().get(pk=a.pk)
                daten = signing.loads(formular.cleaned_data["stand"], salt="anlagestand")
                if daten != {
                    "a": a.pk,
                    "user": request.user.pk,
                    "stand": dateifassungen.originalstand(aktuell),
                }:
                    raise Schreibkonflikt(
                        "Anlage inzwischen geändert. Bitte den aktuellen Stand erneut prüfen."
                    )
                e.refresh_from_db()
                if not rechte.darf_bearbeiten(request.user, e):
                    raise PermissionDenied
                formular.save()
        except (signing.BadSignature, Schreibkonflikt) as fehler:
            formular.add_error(None, str(fehler))
            status = 409
        else:
            messages.success(
                request,
                (
                    "Materialverwendung gespeichert. Bestehende Freigabekopien "
                    "bleiben erhalten; neue Kopien entstehen erst bei erneuter "
                    "Freigabe."
                ),
            )
            return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)
    return render(
        request,
        "kern/wissenspflege_formular.html",
        {"eintrag": e, "dokument": e.dokument, "formular": formular, "anlage": a},
        status=status,
    )


def serialisieren(objekt):
    ergebnis = {}
    for name in PFLEGE_FELDER:
        wert = getattr(objekt, name)
        if name in ("pflege_funktion", "pflege_vertretung"):
            wert = wert.schluessel if wert else None
        elif name == "ersetzt_durch":
            wert = {"dokument": wert.dokument.schluessel, "kennung": wert.kennung} if wert else None
        elif hasattr(wert, "isoformat"):
            wert = wert.isoformat()
        ergebnis[name] = wert
    return ergebnis


def einlesen(daten, nutzer=None):
    from datetime import date

    if not isinstance(daten, dict) or set(daten) - set(PFLEGE_FELDER):
        raise ValidationError("Unbekannte oder ungültige Wissensangaben.")
    ergebnis = {}
    for name, wert in daten.items():
        if name in ("pflege_funktion", "pflege_vertretung"):
            if wert is None:
                ergebnis[name] = None
                continue
            f = (
                Schulfunktion.objects.filter(schluessel=wert, archiviert=False).first()
                if isinstance(wert, str)
                else None
            )
            if not f:
                raise ValidationError("Eine Pflegefunktion ist nicht verfügbar.")
            ergebnis[name] = f
        elif name == "ersetzt_durch":
            if wert is None:
                ergebnis[name] = None
                continue
            if (
                not isinstance(wert, dict)
                or set(wert) != {"dokument", "kennung"}
                or not all(isinstance(v, str) for v in wert.values())
            ):
                raise ValidationError("Ungültiger Verweis auf den nachfolgenden Eintrag.")
            menge = Eintrag.objects.all()
            if nutzer is not None:
                menge = rechte.sichtbare_eintraege(nutzer, menge)
            e = menge.filter(dokument__schluessel=wert["dokument"], kennung=wert["kennung"]).first()
            if e is None:
                raise ValidationError("Der nachfolgende Eintrag ist nicht verfügbar.")
            ergebnis[name] = e
        elif name in ("wirksam_ab", "wirksam_bis", "geprueft_am", "pruefen_am"):
            if wert is not None and not isinstance(wert, str):
                raise ValidationError("Ein Wissensdatum ist ungültig.")
            try:
                ergebnis[name] = date.fromisoformat(wert) if wert else None
            except (ValueError, TypeError):
                raise ValidationError("Ein Wissensdatum ist ungültig.") from None
        else:
            feld = Eintrag._meta.get_field(name)
            ergebnis[name] = feld.clean(wert, None)
    test = Eintrag(**ergebnis)
    # Nur die fachlichen Angaben prüfen; Importtyp und Dokument werden separat geprüft.
    from kern.models import Wissensangaben

    Wissensangaben.clean(test)
    return ergebnis
